"""Part A of instrument construction (no outside data needed).

1. Freeway links: interchange to interchange, per freeway and direction.
   Interchanges are located from PeMS ramp stations (OR, FR, FF, CD). Ramps with
   the same street name (ignoring NB/SB, 1/2, AVE/BLVD/ST) within RAMP_GAP miles
   of each other are one interchange, as are any ramps within SAME_SPOT miles;
   otherwise ramps with different names are separate interchanges.
2. Incidents matched to the nearest mainline station on the same freeway and
   direction within 1 mile (straight-line distance), as in Bento et al.
3. Own-link incident flags on the cleaned station-hours: an incident on the
   station's own link in that hour (Bento et al. drop these station-hours).
4. Hourly D7 vehicle-miles travelled from all mainline station-hours,
   including imputed ones (a background control, not an estimation input).

Inputs: data/interim (raw parquet), data/cleaned. Outputs: data/analysis/.
"""
from pathlib import Path

import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
CLEANED = ROOT / "data" / "cleaned"
OUT = ROOT / "data" / "analysis"
OUT.mkdir(parents=True, exist_ok=True)

RAMP_TYPES = ["OR", "FR", "FF", "CD"]
RAMP_GAP = 0.6     # miles: same-name ramps closer than this are one interchange
SAME_SPOT = 0.15   # miles: any ramps closer than this are one interchange
MATCH_MILES = 1.0  # Bento et al.: crash matched to a station less than a mile away


def latest_meta():
    m = pd.read_parquet(INTERIM / "station_meta_d7_2026.parquet")
    return m.sort_values("meta_date").groupby("ID").last().reset_index()


SUFFIX = re.compile(r"\b(NB|SB|EB|WB|N/B|S/B|E/B|W/B|1|2|3|AVE|AV|BLVD|BL|ST|RD|DR|WAY)\b")


def name_stem(name):
    return re.sub(r"\s+", " ", SUFFIX.sub(" ", str(name).upper())).strip()


def interchanges(meta):
    """One row per interchange: freeway, direction, postmile (mean of its ramps)."""
    r = meta[meta.Type.isin(RAMP_TYPES)].sort_values(["Fwy", "Dir", "Abs_PM"]).copy()
    r["stem"] = r.Name.map(name_stem)
    g = r.groupby(["Fwy", "Dir"])
    gap = g.Abs_PM.diff().fillna(np.inf)
    new = (gap > RAMP_GAP) | ((g.stem.shift() != r.stem) & (gap > SAME_SPOT))
    r = r.assign(ic=new.cumsum())
    ic = (r.groupby("ic").agg(fwy=("Fwy", "first"), dir=("Dir", "first"),
                              pm=("Abs_PM", "mean"), n_ramps=("ID", "size"),
                              names=("Name", lambda s: " / ".join(sorted(set(s)))))
          .reset_index(drop=True))
    return ic


def assign_link(df, ic, pm_col):
    """Link id = index of the last interchange at or before the postmile."""
    out = []
    for (fwy, d), g in df.groupby(["fwy", "dir"], observed=True):
        cuts = np.sort(ic.loc[(ic.fwy == fwy) & (ic.dir == d), "pm"].to_numpy())
        k = np.searchsorted(cuts, g[pm_col].to_numpy(), side="right")
        out.append(pd.Series([f"{fwy}{d}-{i:03d}" for i in k], index=g.index))
    return pd.concat(out).reindex(df.index) if out else pd.Series(index=df.index, dtype=object)


def links_table(ic):
    rows = []
    for (fwy, d), g in ic.groupby(["fwy", "dir"]):
        pms = np.sort(g.pm.to_numpy())
        bounds = np.concatenate([[-np.inf], pms, [np.inf]])
        for i in range(len(bounds) - 1):
            rows.append(dict(link=f"{fwy}{d}-{i:03d}", fwy=fwy, dir=d,
                             pm_from=bounds[i], pm_to=bounds[i + 1]))
    t = pd.DataFrame(rows)
    t["length_mi"] = t.pm_to - t.pm_from
    return t


def haversine_mi(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * np.arcsin(np.sqrt(a))


def match_incidents(inc, ml):
    """Nearest mainline station on the same freeway and direction, within 1 mile."""
    st = ml[["station", "fwy", "dir", "lat", "lon", "abs_pm", "link"]]
    m = inc[["incident_id", "fwy", "dir", "lat", "lon"]].merge(st, on=["fwy", "dir"], suffixes=("", "_st"))
    m["dist_mi"] = haversine_mi(m.lat, m.lon, m.lat_st, m.lon_st)
    m = m.sort_values("dist_mi").drop_duplicates("incident_id")
    m = m[m.dist_mi < MATCH_MILES]
    return inc.merge(m[["incident_id", "station", "dist_mi", "link"]]
                     .rename(columns={"station": "matched_station", "link": "matched_link"}),
                     on="incident_id", how="left")


def d7_vmt():
    sh = pd.read_parquet(INTERIM / "station_hour_d7_2026.parquet",
                         columns=["ts", "lane_type", "flow", "length"])
    sh = sh[sh.lane_type == "ML"]
    return (sh.assign(vmt=sh.flow * sh.length).groupby("ts").vmt.sum()
            .rename("d7_vmt").reset_index())


def main():
    meta = latest_meta()
    ic = interchanges(meta)
    links = links_table(ic)

    ml = meta[meta.Type == "ML"].rename(columns={"ID": "station", "Fwy": "fwy", "Dir": "dir",
                                                 "Abs_PM": "abs_pm", "Latitude": "lat",
                                                 "Longitude": "lon"})
    ml["link"] = assign_link(ml, ic, "abs_pm")

    inc = pd.read_parquet(CLEANED / "incidents_d7_2026.parquet")
    inc = match_incidents(inc, ml)

    # station-hour flags: any incident whose matched station is on the same link, same hour
    sh = pd.read_parquet(CLEANED / "station_hour_d7_2026_clean.parquet")
    sh = sh.merge(ml[["station", "link"]], on="station", how="left", validate="many_to_one")
    hit = inc.dropna(subset=["matched_link"])
    for name, sel in [("own_link_incident", slice(None)),
                      ("own_link_collision", hit.is_collision),
                      ("own_link_collision_hr", hit.is_collision | hit.is_hit_run)]:
        keys = hit.loc[sel, ["matched_link", "hour_start"]].drop_duplicates()
        keys = keys.rename(columns={"matched_link": "link", "hour_start": "ts"}).assign(**{name: True})
        sh = sh.merge(keys, on=["link", "ts"], how="left")
        sh[name] = sh[name].fillna(False).astype(bool)

    vmt = d7_vmt()
    sh = sh.merge(vmt, on="ts", how="left", validate="many_to_one")

    ic.to_csv(OUT / "interchanges_d7.csv", index=False)
    links.to_csv(OUT / "links_d7.csv", index=False)
    ml[["station", "fwy", "dir", "abs_pm", "lat", "lon", "link"]].to_csv(OUT / "stations_links_d7.csv", index=False)
    inc.to_parquet(OUT / "incidents_d7_matched.parquet", index=False, compression="zstd")
    vmt.to_csv(OUT / "d7_vmt_hourly.csv", index=False)
    sh.to_parquet(OUT / "station_hour_d7_2026_analysis.parquet", index=False, compression="zstd")

    finite = links[np.isfinite(links.length_mi)]
    print(f"interchanges: {len(ic):,}; links: {len(links):,}; "
          f"interior link length (mi) quantiles: {finite.length_mi.quantile([.1, .25, .5, .75, .9, .99]).round(2).to_dict()}")
    print(f"incidents matched within 1 mile: {inc.matched_station.notna().sum():,} of {len(inc):,} "
          f"({inc.matched_station.notna().mean():.1%}); collisions matched: "
          f"{inc.loc[inc.is_collision, 'matched_station'].notna().mean():.1%}")
    for c in ["own_link_incident", "own_link_collision", "own_link_collision_hr"]:
        print(f"station-hours with {c}: {sh[c].sum():,} ({sh[c].mean():.2%})")
    print(f"D7 VMT per hour: median {vmt.d7_vmt.median():,.0f}, max {vmt.d7_vmt.max():,.0f}")


if __name__ == "__main__":
    main()
