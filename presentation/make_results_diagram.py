"""Results-at-a-glance diagram for the slides (reads the project's result files)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EST = ROOT / "output" / "estimation"
BLUE, GREY, INK, INK2, AMBER = "#1a218d", "#9a9890", "#111111", "#555555", "#b86a00"

main = pd.read_csv(EST / "main_estimates.csv")
beta = float(main[(main.variant == "main") & (main.side == "above")].iv.iloc[0])
el = pd.read_csv(EST / "time_of_day_elasticities.csv")
tolls = pd.read_csv(EST / "welfare_tolls_by_hour.csv")
summ = pd.read_csv(EST / "welfare_summary.csv")
s = summ[summ.label.str.startswith("IV slope, eps -2.0, VOT main")].iloc[0]
B, VF = 19, float(s.vf)

def speed(D):
    return np.where(D <= B, VF, VF * np.exp(beta * (D - B)))

fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [1.55, 1]})

# Left: every window on one curve
D = np.linspace(0, 40, 400)
ax.plot(D, speed(D), color=INK, lw=2.5, zorder=1)
ax.axvline(B, color=INK2, ls=":", lw=1)
ax.text(B + 0.4, 25, f"kink: {B} cars/mile/lane", color=INK2, fontsize=10, rotation=90, va="bottom")
ax.annotate(f"each extra car: speed {beta*100:.1f}%", xy=(33, float(speed(33))), xytext=(30.5, 62),
            fontsize=10.5, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
show = ["02-04", "06-08", "08-10", "12-14", "16-18", "20-22"]
two_hour = tolls.groupby(tolls.hour // 2).two_hour_toll.first()
offsets = {"02-04": (6, -34), "06-08": (-125, -32), "08-10": (12, 6), "12-14": (-150, -78), "16-18": (12, 6), "20-22": (-24, 12)}
for _, r in el[el.bracket.isin(show)].iterrows():
    d = float(r.mean_density)
    k = int(r.bracket[:2]) // 2
    toll = round(float(two_hour.loc[k]) * 100)
    peak = r.bracket in ("08-10", "16-18")
    c = BLUE if d > B else GREY
    ax.scatter([d], [float(speed(d))], s=140 if peak else 90, color=c, edgecolor="white", lw=1.5, zorder=3)
    dx, dy = offsets[r.bracket]
    ax.annotate(f"{r.bracket.replace('-', '–')}h\ntoll {toll}¢", (d, float(speed(d))), xytext=(dx, dy),
                textcoords="offset points", fontsize=10, color=INK, ha="left",
                fontweight="bold" if peak else "normal",
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6, shrinkA=2, shrinkB=5))
ax.set_xlim(0, 40)
ax.set_ylim(20, 75)
ax.set_xlabel("Typical density in that two-hour window (cars per mile per lane)")
ax.set_ylabel("Speed (mph)")
ax.set_title("Every hour of the day sits on the same curve", loc="left", fontweight="bold", fontsize=13)
ax.text(0.5, 21.5, "Rush hour costs more only because it is further along the curve.", fontsize=10, color=INK2)

# Right: how much of the possible gain each policy captures
pol = [("Ideal: by place and hour", s.gain_first_best_per_vmt), ("One toll per hour", s.gain_hourly_per_vmt),
       ("One toll per two hours", s.gain_two_hour_per_vmt), (f"Flat {round(s.flat_toll*100)}¢ all day", s.gain_flat_per_vmt)]
y = np.arange(len(pol))[::-1]
vals = [v * 100 for _, v in pol]
bx.barh(y, vals, color=[BLUE, GREY, GREY, GREY], height=0.55)
for yi, (lab, v) in zip(y, pol):
    share = v / s.gain_first_best_per_vmt
    bx.text(v * 100 + 0.2, yi, f"{v*100:.1f}¢  ({share:.0%})", va="center", fontsize=10.5, color=INK)
bx.set_yticks(y, [p[0] for p in pol], fontsize=10.5)
bx.set_xlim(0, max(vals) * 1.45)
bx.set_xlabel("Welfare gain (cents per vehicle-mile)")
bx.set_title("Pricing by place beats pricing by clock", loc="left", fontweight="bold", fontsize=13)
bx.text(0.98, 0.16, f"A flat toll gets {s.gain_flat_per_vmt / s.gain_hourly_per_vmt:.0%}\nof the hourly toll's gain.",
        fontsize=10, color=INK2, transform=bx.transAxes, ha="right")
bx.set_axisbelow(True)

for a in (ax, bx):
    a.spines[["top", "right"]].set_visible(False)
bx.grid(axis="x", color="#e6e6e6")
ax.grid(color="#eeeeee")
fig.text(0.01, 0.01, f"D7 2026. Curve: free flow {VF:.1f} mph to the kink, then IV slope {beta:.4f}. Points: mean density per window. "
         "Tolls: best two-hour toll (VOT $24.30/veh-hr, elasticity -2.0).", fontsize=8.5, color=INK2)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(ROOT / "presentation" / "figures" / "results_at_a_glance.png", dpi=200)
