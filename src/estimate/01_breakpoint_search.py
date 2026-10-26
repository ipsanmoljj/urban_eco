"""Breakpoint search for the speed-density kink (Bento et al. eq. 4), PRELIMINARY.

For each candidate breakpoint b = 1..50 veh/mile/lane, fit by OLS
    log(speed) = beta * f_b(density) + gamma * D7_VMT + station + hour + dow + month FE
and pick b with the lowest AIC. Every fit has the same number of parameters, so
the lowest AIC is the lowest residual sum of squares.

Two forms of f_b, because Bento et al.'s eq. 4 is ambiguous:
  - "as written": density * 1[density > b]  (jumps from 0 to beta*b at the break)
  - "hinge":      (density - b) * 1[density > b]  (continuous at the break)
Two samples, as agreed: with and without flag_high_flow rows.
Station-hours with an incident on their own link are excluded, as in Bento et al.

PRELIMINARY: weather and gas-price controls are not yet in (Bento et al. include
them). Re-run once they are added.

Fixed effects are partialled out once for all candidate regressors (Frisch-Waugh),
which gives the same coefficients and residuals as separate fits.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyfixest.estimation import demean

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "analysis" / "station_hour_d7_2026_analysis.parquet"
OUT = ROOT / "output" / "estimation"
OUT.mkdir(parents=True, exist_ok=True)

BREAKS = np.arange(1, 51)
FE = ["station", "hour", "dow", "month"]


def search(d):
    y = np.log(d.speed.to_numpy())
    dens = d.density.to_numpy()
    above = dens[:, None] > BREAKS[None, :]
    cols = [y[:, None], (d.d7_vmt.to_numpy() / 1e6)[:, None],
            dens[:, None] * above, (dens[:, None] - BREAKS[None, :]) * above]
    X = np.hstack(cols).astype(np.float64)
    flist = np.column_stack([pd.factorize(d[c])[0] for c in FE]).astype(np.uint64)
    Xd, ok = demean(X, flist, np.ones(len(d)), tol=1e-8, maxiter=100_000)
    if not ok:
        raise RuntimeError("demeaning did not converge")
    yd, vd = Xd[:, 0], Xd[:, 1]
    n, nb = len(d), len(BREAKS)
    rows = []
    for form, offset in [("as_written", 2), ("hinge", 2 + nb)]:
        for j, b in enumerate(BREAKS):
            Z = np.column_stack([Xd[:, offset + j], vd])
            coef, *_ = np.linalg.lstsq(Z, yd, rcond=None)
            rss = float(((yd - Z @ coef) ** 2).sum())
            rows.append(dict(form=form, breakpoint=b, beta=coef[0], rss=rss,
                             n_above=int(above[:, j].sum())))
    r = pd.DataFrame(rows)
    r["aic_rel"] = n * np.log(r.rss / n)
    r["aic_rel"] -= r.groupby("form").aic_rel.transform("min")
    r["n"] = n
    return r


def main():
    d = pd.read_parquet(DATA)
    d = d[~d.own_link_incident]
    out = []
    for sample, sel in [("all_rows", np.ones(len(d), bool)), ("excl_high_flow", ~d.flag_high_flow.to_numpy())]:
        r = search(d[sel])
        r["sample"] = sample
        out.append(r)
    res = pd.concat(out, ignore_index=True)
    res.to_csv(OUT / "breakpoint_search_preliminary.csv", index=False)

    best = res.loc[res.groupby(["sample", "form"]).aic_rel.idxmin()]
    print(best[["sample", "form", "breakpoint", "beta", "n", "n_above"]].to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=False)
    for ax, form, title in [(axes[0], "as_written", "Eq. 4 as written: density x 1[density > b]"),
                            (axes[1], "hinge", "Hinge: (density - b) x 1[density > b]")]:
        r = res[(res.form == form) & (res["sample"] == "all_rows")]
        b0 = int(r.loc[r.aic_rel.idxmin(), "breakpoint"])
        ax.plot(r.breakpoint, r.aic_rel / 1e6, color="#2a78d6", lw=2)
        ax.axvline(21, color="#52514e", ls="--", lw=1)
        ax.text(21.5, ax.get_ylim()[1] * 0.92, "Bento: 21", fontsize=8, color="#52514e")
        ax.scatter([b0], [0], color="#2a78d6", zorder=3)
        ax.annotate(f"minimum at {b0}", (b0, 0), xytext=(-12, 14), textcoords="offset points", fontsize=9, ha="right" if b0 > 10 else "left")
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
        ax.set_xlabel("Candidate breakpoint (veh/mile/lane)")
        ax.set_ylabel("AIC minus its minimum (millions)")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(color="#e8e6e1")
    fig.text(0.01, 0.01, "PRELIMINARY: station, hour, day-of-week, month FE and D7 VMT; no weather or gas price yet. "
             "D7 2026 cleaned station-hours, own-link incident hours excluded.", fontsize=8, color="#52514e")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "breakpoint_search_preliminary.png", dpi=150)


if __name__ == "__main__":
    main()
