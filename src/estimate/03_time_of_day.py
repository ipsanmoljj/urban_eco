"""Does the congestion curve shift by time of day, or does traffic only move along it?

Three pieces, on the estimation sample (own-link incident hours and hours without
weather excluded):
1. Pooled vs bracket slopes: log(speed) on the hinge (density - 19)+ interacted with
   twelve two-hour brackets, plus controls and FE. Wald test that all twelve slopes
   are equal. If they are equal, the curve is the same at every hour.
2. Bracket-specific breakpoints: the hinge breakpoint search run separately in each
   bracket.
3. Koch-style elasticities: sigma_k from log(travel time per mile) on log(density) in
   each bracket, compared with the elasticity a SINGLE pooled curve implies at that
   bracket's densities: mean over station-hours of |beta| * density * 1[density > 19].
   If the two line up, the hourly pattern in sigma is density moving along one curve.
OLS throughout (12 endogenous slopes would need 12 instruments, too weak here);
the main IV estimate is used to scale the comparison in the write-up.

Writes output/estimation/time_of_day_*.csv and time_of_day.png.
"""
from pathlib import Path
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyfixest as pf

warnings.filterwarnings("ignore", message=".*singleton.*")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "estimate"))
from importlib import import_module  # noqa: E402

bp = import_module("01_breakpoint_search")
DATA = ROOT / "data" / "analysis" / "station_hour_d7_2026_analysis.parquet"
OUT = ROOT / "output" / "estimation"

BREAK = 19
CONTROLS = "temp_c + temp2 + wind_ms + precip_mm + gas_price + vmt_m"
FE = "station + hour + dow + month"
VCOV = {"CRV1": "station+date"}
BRACKETS = [f"{h:02d}-{h + 2:02d}" for h in range(0, 24, 2)]


def load():
    d = pd.read_parquet(DATA)
    d = d[~d.own_link_incident].dropna(subset=["temp_c", "wind_ms"]).copy()
    d["temp2"] = d.temp_c ** 2
    d["vmt_m"] = d.d7_vmt / 1e6
    d["lspeed"] = np.log(d.speed)
    d["bracket"] = (d.hour // 2).astype(int)
    d["hinge"] = (d.density - BREAK).clip(lower=0)
    for k in range(12):
        d[f"h{k}"] = d.hinge * (d.bracket == k)
    return d


def slopes(d):
    pooled = pf.feols(f"lspeed ~ hinge + {CONTROLS} | {FE}", data=d, vcov=VCOV)
    terms = " + ".join(f"h{k}" for k in range(12))
    m = pf.feols(f"lspeed ~ {terms} + {CONTROLS} | {FE}", data=d, vcov=VCOV)
    names = list(m.coef().index)
    idx = [names.index(f"h{k}") for k in range(12)]
    R = np.zeros((11, len(names)))
    for r in range(11):
        R[r, idx[r]], R[r, idx[r + 1]] = 1, -1
    wald = m.wald_test(R=R)
    t = pd.DataFrame({"bracket": BRACKETS,
                      "beta": [m.coef()[f"h{k}"] for k in range(12)],
                      "se": [m.se()[f"h{k}"] for k in range(12)],
                      "n_above": [int((d.hinge > 0)[d.bracket == k].sum()) for k in range(12)]})
    return pooled.coef()["hinge"], pooled.se()["hinge"], t, wald


def bracket_breakpoints(d):
    rows = []
    for k in range(12):
        r = bp.search(d[d.bracket == k])
        best = r[r.form == "hinge"].sort_values("aic_rel").iloc[0]
        rows.append(dict(bracket=BRACKETS[k], breakpoint=int(best.breakpoint), beta_at_break=best.beta))
    return pd.DataFrame(rows)


def koch_sigma(d, beta_pooled):
    s = d[d.density > 0.5].copy()
    s["ltime"] = -s.lspeed
    s["ldens"] = np.log(s.density)
    terms = " + ".join(f"ld{k}" for k in range(12))
    for k in range(12):
        s[f"ld{k}"] = s.ldens * (s.bracket == k)
    m = pf.feols(f"ltime ~ {terms} + {CONTROLS} | {FE}", data=s, vcov=VCOV)
    implied = d.assign(sig=abs(beta_pooled) * d.density * (d.density > BREAK)).groupby("bracket").sig.mean()
    return pd.DataFrame({"bracket": BRACKETS,
                         "sigma_loglog": [m.coef()[f"ld{k}"] for k in range(12)],
                         "sigma_loglog_se": [m.se()[f"ld{k}"] for k in range(12)],
                         "sigma_implied_single_curve": implied.reindex(range(12)).to_numpy(),
                         "mean_density": d.groupby("bracket").density.mean().reindex(range(12)).to_numpy(),
                         "share_above_break": d.assign(a=d.density > BREAK).groupby("bracket").a.mean().reindex(range(12)).to_numpy()})


def figure(sl, bpk, ks, beta_pooled):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    x = np.arange(12)
    ax = axes[0]
    ax.errorbar(x, sl.beta, yerr=1.96 * sl.se, fmt="o", color="#2a78d6", ms=5, capsize=2)
    ax.axhline(beta_pooled, color="#52514e", ls="--", lw=1)
    ax.text(11.3, beta_pooled, f"pooled {beta_pooled:.4f}", fontsize=8, color="#52514e", va="bottom", ha="right")
    ax.set_title("Slope above the kink, by time of day", loc="left", fontweight="bold", fontsize=11)
    ax.set_ylabel("Change in log speed per extra veh/mile/lane")
    ax = axes[1]
    ax.plot(x, bpk.breakpoint, "o-", color="#2a78d6", ms=5)
    ax.axhline(BREAK, color="#52514e", ls="--", lw=1)
    ax.set_ylim(0, max(40, bpk.breakpoint.max() + 5))
    ax.set_title("Breakpoint, by time of day", loc="left", fontweight="bold", fontsize=11)
    ax.set_ylabel("Breakpoint (veh/mile/lane)")
    ax = axes[2]
    ax.plot(x, ks.sigma_loglog, "o-", color="#2a78d6", ms=5, label="Estimated by bracket (Koch-style log-log)")
    ax.plot(x, ks.sigma_implied_single_curve, "s--", color="#9a9890", ms=5, label="Implied by one pooled curve")
    ax.set_title("Elasticity of travel time to density", loc="left", fontweight="bold", fontsize=11)
    ax.set_ylabel("Elasticity")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    for ax in axes:
        ax.set_xticks(x, BRACKETS, rotation=60, fontsize=8)
        ax.set_xlabel("Two-hour bracket")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(color="#e8e6e1")
    fig.text(0.01, 0.01, "OLS with station, hour, day-of-week, month FE and weather, gas, D7 VMT controls; bars are 95% CIs "
             "(SEs clustered by station and date). D7 2026.", fontsize=8, color="#52514e")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "time_of_day.png", dpi=150)


def main():
    d = load()
    beta, beta_se, sl, wald = slopes(d)
    print(f"pooled hinge slope {beta:.5f} ({beta_se:.5f}); Wald test equal slopes: {wald.to_dict()}", flush=True)
    print(sl.round(5).to_string(index=False), flush=True)
    bpk = bracket_breakpoints(d)
    print(bpk.to_string(index=False), flush=True)
    ks = koch_sigma(d, beta)
    print(ks.round(3).to_string(index=False), flush=True)
    sl.to_csv(OUT / "time_of_day_slopes.csv", index=False)
    bpk.to_csv(OUT / "time_of_day_breakpoints.csv", index=False)
    ks.to_csv(OUT / "time_of_day_elasticities.csv", index=False)
    pd.DataFrame([dict(pooled_beta=beta, pooled_se=beta_se, **{f"wald_{k}": v for k, v in wald.to_dict().items()})]) \
        .to_csv(OUT / "time_of_day_test.csv", index=False)
    figure(sl, bpk, ks, beta)


if __name__ == "__main__":
    main()
