"""Parallel-freeway incident instrument (our simplification of Bento et al.).

Bento et al. treat a station-hour when a crash occurs on the non-overlapping part of
a Google-Maps alternative route. Without the Google routes, we define a station's
alternatives as mainline stations that:
  - are on a DIFFERENT freeway,
  - carry traffic in the SAME direction (N, S, E or W), so the roads run parallel,
  - lie between MIN_MI and MAX_MI miles away (straight line). The lower bound
    drops freeway merges and junctions, where an incident on the other freeway
    would block our station directly rather than through rerouting.
A station-hour is treated if any incident (matched to its nearest station, as in
data/analysis/incidents_d7_matched.parquet) starts in that hour at one of the
station's alternatives. Variants: collisions only; collisions plus hit-and-run;
and the number of such incidents.

Adds z_alt_incident, z_alt_collision, z_alt_collision_hr, n_alt_incident to the
analysis station-hours, and writes data/analysis/alternatives_d7.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AN = ROOT / "data" / "analysis"
MIN_MI, MAX_MI = 0.5, 3.0


def haversine_mi(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * np.arcsin(np.sqrt(a))


def alternatives(st):
    a = st[["station", "fwy", "dir", "lat", "lon"]]
    p = a.merge(a, on="dir", suffixes=("", "_alt"))
    p = p[p.fwy != p.fwy_alt]
    p["dist_mi"] = haversine_mi(p.lat, p.lon, p.lat_alt, p.lon_alt)
    p = p[(p.dist_mi >= MIN_MI) & (p.dist_mi <= MAX_MI)]
    return p[["station", "fwy", "dir", "station_alt", "fwy_alt", "dist_mi"]].reset_index(drop=True)


def main():
    st = pd.read_csv(AN / "stations_links_d7.csv")
    alt = alternatives(st)
    alt.to_csv(AN / "alternatives_d7.csv", index=False)

    inc = pd.read_parquet(AN / "incidents_d7_matched.parquet")
    inc = inc.dropna(subset=["matched_station"]).astype({"matched_station": "int64"})

    sh = pd.read_parquet(AN / "station_hour_d7_2026_analysis.parquet")
    sh = sh.drop(columns=[c for c in sh if c.startswith(("z_alt", "n_alt"))])
    sample_st = set(sh.station.unique())
    alt_s = alt[alt.station.isin(sample_st)]

    for name, sel in [("incident", np.ones(len(inc), bool)), ("collision", inc.is_collision.to_numpy()),
                      ("collision_hr", (inc.is_collision | inc.is_hit_run).to_numpy())]:
        e = inc.loc[sel, ["matched_station", "hour_start", "incident_id"]]
        t = alt_s.merge(e, left_on="station_alt", right_on="matched_station")
        cnt = t.groupby(["station", "hour_start"]).incident_id.nunique().rename(f"n_alt_{name}").reset_index()
        cnt = cnt.rename(columns={"hour_start": "ts"})
        sh = sh.merge(cnt, on=["station", "ts"], how="left")
        sh[f"n_alt_{name}"] = sh[f"n_alt_{name}"].fillna(0).astype("int16")
        sh[f"z_alt_{name}"] = (sh[f"n_alt_{name}"] > 0).astype("int8")
    sh = sh.drop(columns=["n_alt_collision", "n_alt_collision_hr"])

    sh.to_parquet(AN / "station_hour_d7_2026_analysis.parquet", index=False, compression="zstd")
    per = alt_s.groupby("station").size()
    print(f"sample stations with at least one alternative: {per.size} of {len(sample_st)}; "
          f"alternatives per station: median {per.median():.0f}")
    for c in ["z_alt_incident", "z_alt_collision", "z_alt_collision_hr"]:
        print(f"{c}: {sh[c].mean():.2%} of station-hours treated ({sh[c].sum():,})")


if __name__ == "__main__":
    main()
