"""Marginal external cost, optimal tolls and welfare: hourly vs two-hour vs flat.

Supply (Bento et al. 6.2): speed v(D) = v_f for D <= b, v_f * exp(beta * (D - b)) above,
with b = 19 (our breakpoint), beta = our main IV estimate, v_f = mean observed speed
2-4 am. Flow per lane q = D * v(D) rises to its maximum at D* = 1/|beta| (for D* > b);
beyond that, traffic queues at q_max (Verhoef 2001, as in Bento et al.).
Cost per vehicle-mile = VOT / v (time only, as in Bento et al.).
MEC per vehicle-mile on the flowing branch = (VOT / v) * sigma / (1 - sigma), sigma = |beta| D.
Demand: constant elasticity eps through each cell's observed point.

Cells: station x hour of day, weekdays excluding holidays, at the cell's mean density.
A cell above D* is calibrated as a queue at q_max with the speed of its mean density.
Cells are weighted by lane-miles (lanes x station length).

Policies, each solved for the toll(s) that maximise total welfare over all cells:
  first-best  : a separate toll for every station and hour
  hourly      : one toll per hour of day, same at every station
  two-hour    : one toll per two-hour bracket
  flat        : one toll for all hours and stations (a true second best)
Welfare gain = change in (consumer benefit - time cost); tolls are transfers.
Writes output/estimation/welfare_*.csv and welfare.png.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AN = ROOT / "data" / "analysis"
OUT = ROOT / "output" / "estimation"

BREAK = 19
VOT_MAIN = 15.19 * 1.6           # Bento et al. Fig. 13 note: $15.19 x 1.6 occupants, per vehicle-hour
VOTS = {"Bento text ($15.00/veh-hr)": 15.00, "main ($24.30/veh-hr)": VOT_MAIN,
        "2026 dollars (approx. $32/veh-hr)": VOT_MAIN * 1.33}
EPS_MAIN = -2.0
EPSILONS = [-0.67, -1.0, -2.0]
TOLL_GRID = np.round(np.arange(0, 2.0001, 0.01), 2)


class Curve:
    def __init__(self, beta, vf, b=BREAK):
        self.beta, self.vf, self.b = beta, vf, b
        self.dstar = max(1 / abs(beta), b)
        self.D = np.linspace(1e-3, self.dstar, 4000)
        self.v = self.speed(self.D)
        self.q = self.D * self.v
        self.qmax = self.q[-1]

    def speed(self, D):
        return np.where(D <= self.b, self.vf, self.vf * np.exp(self.beta * (D - self.b)))

    def ac_of_q(self, q, vot):
        D = np.interp(q, self.q, self.D)
        return vot / self.speed(D)

    def mec_of_q(self, q, vot):
        D = np.interp(q, self.q, self.D)
        sig = np.where(D > self.b, abs(self.beta) * D, 0.0)
        return vot / self.speed(D) * sig / np.maximum(1 - sig, 1e-6)


def demand_price(q, q0, p0, eps):
    return p0 * (q / q0) ** (1 / eps)


def demand_integral(q1, q0, p0, eps):
    """Integral of inverse demand from q1 to q0."""
    k = 1 + 1 / eps
    if abs(k) < 1e-9:
        return p0 * q0 * np.log(q0 / q1)
    return p0 * q0 ** (-1 / eps) * (q0 ** k - q1 ** k) / k


def equilibrium(cv, q0, p0, eps, vot, toll, first_best=False):
    """Flow q and time cost per mile with the toll; queue at q_max if demand exceeds it."""
    def excess(q):
        extra = cv.mec_of_q(q, vot) if first_best else toll
        return demand_price(q, q0, p0, eps) - cv.ac_of_q(q, vot) - extra
    lo = np.full_like(q0, 1e-3)
    hi = np.full_like(q0, cv.qmax)
    ex_hi = excess(hi)
    for _ in range(60):
        mid = (lo + hi) / 2
        pos = excess(mid) > 0
        lo = np.where(pos, mid, lo)
        hi = np.where(pos, hi, mid)
    q = np.where(ex_hi > 0, cv.qmax, (lo + hi) / 2)
    extra = cv.mec_of_q(q, vot) if first_best else toll
    ac = np.where(ex_hi > 0, demand_price(cv.qmax, q0, p0, eps) - extra, cv.ac_of_q(q, vot))
    return q, ac


def gains(cv, cells, eps, vot, toll=None, first_best=False):
    """Weighted welfare gain per cell, the new flow, and the toll that implements it.

    The implementing toll is the wedge between willingness to pay and time cost. At the
    kink the marginal external cost jumps (sigma = |beta| D is about 0.7 just above b),
    so the first-best often sits exactly at the kink, where MEC(q) itself is not the toll.
    """
    q0, p0, w = cells.q0.to_numpy(), cells.p0.to_numpy(), cells.weight.to_numpy()
    q1, ac1 = equilibrium(cv, q0, p0, eps, vot, toll if toll is not None else 0.0, first_best)
    dw = -np.array([demand_integral(a, b_, c, eps) for a, b_, c in zip(q1, q0, p0)]) + q0 * p0 - q1 * ac1
    implementing_toll = demand_price(q1, q0, p0, eps) - ac1
    return dw * w, q1, implementing_toll


def best_uniform(cv, cells, eps, vot):
    vals = [gains(cv, cells, eps, vot, toll=t)[0].sum() for t in TOLL_GRID]
    i = int(np.argmax(vals))
    return TOLL_GRID[i], vals[i]


def cells_table(cv, vot):
    d = pd.read_parquet(AN / "station_hour_d7_2026_analysis.parquet",
                        columns=["station", "hour", "dow", "holiday", "density", "speed", "own_link_incident"])
    d = d[(d.dow < 5) & ~d.holiday & ~d.own_link_incident]
    c = d.groupby(["station", "hour"]).agg(D=("density", "mean")).reset_index()
    st = pd.read_csv(ROOT / "data" / "cleaned" / "stations_ml_d7.csv")[["station", "lanes", "length"]]
    c = c.merge(st, on="station")
    c["weight"] = c.lanes * c.length
    queue = c.D > cv.dstar
    c["queue"] = queue
    c["q0"] = np.where(queue, cv.qmax, c.D * cv.speed(c.D))
    c["v0"] = cv.speed(c.D)
    c["p0"] = vot / c.v0
    c = c[c.q0 > 1].reset_index(drop=True)
    return c


def run(beta, vf, eps, vot, label):
    cv = Curve(beta, vf)
    cells = cells_table(cv, vot)
    vmt0 = (cells.q0 * cells.weight).sum()
    fb, qfb, fb_toll = gains(cv, cells, eps, vot, first_best=True)
    total_fb = fb.sum()
    flat_t, flat_w = best_uniform(cv, cells, eps, vot)
    hourly = {}
    for h, g in cells.groupby("hour"):
        hourly[h] = best_uniform(cv, g.reset_index(drop=True), eps, vot)
    two = {}
    for k, g in cells.groupby(cells.hour // 2):
        two[k] = best_uniform(cv, g.reset_index(drop=True), eps, vot)
    hourly_w = sum(v[1] for v in hourly.values())
    two_w = sum(v[1] for v in two.values())
    summary = dict(label=label, beta=beta, vf=vf, eps=eps, vot=vot, dstar=cv.dstar, qmax=cv.qmax,
                   cells=len(cells), queue_cells=int(cells.queue.sum()),
                   gain_first_best_per_vmt=total_fb / vmt0, gain_hourly_per_vmt=hourly_w / vmt0,
                   gain_two_hour_per_vmt=two_w / vmt0, gain_flat_per_vmt=flat_w / vmt0,
                   hourly_share_of_fb=hourly_w / total_fb, two_hour_share_of_fb=two_w / total_fb,
                   flat_share_of_fb=flat_w / total_fb, flat_toll=flat_t,
                   peak_hourly_toll=max(v[0] for v in hourly.values()),
                   mean_fb_toll_vmt_weighted=np.average(fb_toll, weights=qfb * cells.weight))
    by_hour = pd.DataFrame({"hour": list(hourly), "hourly_toll": [v[0] for v in hourly.values()]})
    cells = cells.assign(fb_toll=fb_toll, mec_at_baseline=np.where(cells.queue, np.nan, cv.mec_of_q(cells.q0.to_numpy(), vot)))
    by_hour = by_hour.merge(cells.groupby("hour").apply(lambda g: pd.Series({
        "mean_density": np.average(g.D, weights=g.weight),
        "share_cells_queue": np.average(g.queue, weights=g.weight),
        "fb_toll_vmt_weighted": np.average(g.fb_toll, weights=g.q0 * g.weight)}), include_groups=False).reset_index(), on="hour")
    by_hour["two_hour_toll"] = by_hour.hour.map(lambda h: two[h // 2][0])
    by_hour["flat_toll"] = flat_t
    return summary, by_hour


def main():
    est = pd.read_csv(OUT / "main_estimates.csv")
    main_row = est[(est.variant == "main") & (est.side == "above")].iloc[0]
    beta = float(main_row.iv)
    d = pd.read_parquet(AN / "station_hour_d7_2026_analysis.parquet", columns=["hour", "speed"])
    vf = float(d[d.hour.isin([2, 3])].speed.mean())

    rows, main_hour = [], None
    for eps in EPSILONS:
        for vlab, vot in VOTS.items():
            s, bh = run(beta, vf, eps, vot, f"IV slope, eps {eps}, VOT {vlab}")
            rows.append(s)
            if eps == EPS_MAIN and vot == VOT_MAIN:
                main_hour = bh
            print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}, flush=True)
    s, _ = run(float(main_row.ols), vf, EPS_MAIN, VOT_MAIN, "OLS slope (for comparison), eps -2, VOT main")
    rows.append(s)
    print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}, flush=True)
    pd.DataFrame(rows).to_csv(OUT / "welfare_summary.csv", index=False)
    main_hour.to_csv(OUT / "welfare_tolls_by_hour.csv", index=False)
    print(main_hour.round(3).to_string(index=False))

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.step(main_hour.hour, main_hour.hourly_toll * 100, where="mid", color="#2a78d6", lw=2, label="Hourly toll (one per hour)")
    ax.step(main_hour.hour, main_hour.two_hour_toll * 100, where="mid", color="#2a78d6", lw=1, ls=":", label="Two-hour toll")
    ax.axhline(main_hour.flat_toll.iloc[0] * 100, color="#9a9890", lw=2, ls="--", label="Best flat toll")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("Hour of day (weekdays)")
    ax.set_ylabel("Toll (cents per vehicle-mile)")
    ax.set_title("Optimal tolls by hour vs the best single flat toll", loc="left", fontweight="bold", fontsize=11)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(color="#e8e6e1")
    fig.text(0.01, 0.01, f"IV slope {beta:.4f}, breakpoint {BREAK}, free-flow {vf:.1f} mph, demand elasticity {EPS_MAIN}, "
             f"VOT ${VOT_MAIN:.2f}/veh-hr. D7 2026, 422 stations.", fontsize=8, color="#52514e")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "welfare.png", dpi=150)


if __name__ == "__main__":
    main()
