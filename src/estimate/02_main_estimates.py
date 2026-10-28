"""Main estimates: Bento et al. Tables 2-3 on 2026 D7 data, with our parallel-freeway instrument.

Sample: analysis station-hours, excluding hours with an incident on the station's own
link (as in Bento et al.) and hours with no weather reading.
Split (as in Bento et al.): a station-hour is "above the kink" if the mean density of
its station x day-of-week x hour cell exceeds the breakpoint (19 from our search;
Bento's 21 as a robustness check).
On each side:
  OLS:         log(speed) = beta * density + controls + FE
  First stage: density    = gamma * z + controls + FE
  IV (2SLS):   log(speed) = beta * density + controls + FE, density instrumented by z
FE: station, hour, day of week, month. Controls: temperature, temperature squared,
wind, precipitation, gas price, D7 VMT. SEs clustered two ways by station and date.
First-stage F = (gamma / se)^2 with the clustered SE (one instrument).

Writes output/estimation/main_estimates.csv.
"""
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import pyfixest as pf

warnings.filterwarnings("ignore", message=".*singleton.*")

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "analysis" / "station_hour_d7_2026_analysis.parquet"
OUT = ROOT / "output" / "estimation"
OUT.mkdir(parents=True, exist_ok=True)

BREAK = 19
CONTROLS = "temp_c + temp2 + wind_ms + precip_mm + gas_price + vmt_m"
FE = "station + hour + dow + month"
VCOV = {"CRV1": "station+date"}


def load():
    d = pd.read_parquet(DATA)
    d = d[~d.own_link_incident].dropna(subset=["temp_c", "wind_ms"]).copy()
    d["temp2"] = d.temp_c ** 2
    d["vmt_m"] = d.d7_vmt / 1e6
    d["lspeed"] = np.log(d.speed)
    d["cell_density"] = d.groupby(["station", "dow", "hour"]).density.transform("mean")
    return d


def fit_side(s, z):
    ols = pf.feols(f"lspeed ~ density + {CONTROLS} | {FE}", data=s, vcov=VCOV)
    fs = pf.feols(f"density ~ {z} + {CONTROLS} | {FE}", data=s, vcov=VCOV)
    iv = pf.feols(f"lspeed ~ {CONTROLS} | {FE} | density ~ {z}", data=s, vcov=VCOV)
    g, gse = fs.coef()[z], fs.se()[z]
    return dict(n=ols._N, stations=s.station.nunique(), mean_density=s.density.mean(),
                ols=ols.coef()["density"], ols_se=ols.se()["density"],
                fs=g, fs_se=gse, fs_F=(g / gse) ** 2, treated_share=s[z].mean(),
                iv=iv.coef()["density"], iv_se=iv.se()["density"])


def main():
    d = load()
    variants = [
        ("main", "z_alt_incident", BREAK, np.ones(len(d), bool)),
        ("excl. high-flow rows", "z_alt_incident", BREAK, ~d.flag_high_flow.to_numpy()),
        ("collisions only", "z_alt_collision", BREAK, np.ones(len(d), bool)),
        ("collisions + hit-and-run", "z_alt_collision_hr", BREAK, np.ones(len(d), bool)),
        ("balanced panel (151 stations)", "z_alt_incident", BREAK, d.station_all_months.to_numpy()),
        ("excl. holidays", "z_alt_incident", BREAK, ~d.holiday.to_numpy()),
        ("Bento's breakpoint (21)", "z_alt_incident", 21, np.ones(len(d), bool)),
    ]
    rows = []
    for name, z, b, sel in variants:
        dv = d[sel]
        for side, mask in [("below", dv.cell_density <= b), ("above", dv.cell_density > b)]:
            r = fit_side(dv[mask], z)
            r.update(variant=name, instrument=z, breakpoint=b, side=side)
            rows.append(r)
            print(f"{name:32s} {side:5s} n={r['n']:>9,} OLS {r['ols']:.4f} ({r['ols_se']:.4f}) "
                  f"FS {r['fs']:.3f} ({r['fs_se']:.3f}) F {r['fs_F']:.1f}  IV {r['iv']:.4f} ({r['iv_se']:.4f})", flush=True)
    res = pd.DataFrame(rows)
    cols = ["variant", "side", "instrument", "breakpoint", "n", "stations", "mean_density", "treated_share",
            "ols", "ols_se", "fs", "fs_se", "fs_F", "iv", "iv_se"]
    res[cols].to_csv(OUT / "main_estimates.csv", index=False)


if __name__ == "__main__":
    main()
