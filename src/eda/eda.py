"""Exploratory analysis of the D7 2026 data (Station Hour, metadata, CHP incidents).

Reads the parquet files written by src/data/01_load_raw.py. Nothing here filters the data
for estimation; it describes it so we can agree cleaning rules first.
Outputs: output/eda/*.csv and output/eda/*.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
I = ROOT / "data" / "interim"
OUT = ROOT / "output" / "eda"
OUT.mkdir(parents=True, exist_ok=True)

# Bento et al. (2023) Table 1 kink and the density where flow peaks (1 / 0.0327)
KINK, FLOW_PEAK = 21, 30.6

BLUE, GREY, INK, INK2, SURF = "#2a78d6", "#9a9890", "#0b0b0b", "#52514e", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": "#c9c7c0", "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "text.color": INK, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": "#e8e6e1",
    "grid.linewidth": 0.8, "font.size": 10, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def load():
    sh = pd.read_parquet(I / "station_hour_d7_2026.parquet")
    meta = pd.read_parquet(I / "station_meta_d7_2026.parquet")
    chp = pd.read_parquet(I / "chp_incidents_2026.parquet")
    ml = sh[sh.lane_type == "ML"]
    ob = ml[ml.pct_obs == 100].copy()
    ob["flow_pl"] = ob.flow / ob.lanes_reporting
    ob["dens"] = ob.flow_pl / ob.speed
    ob["hour"] = ob.ts.dt.hour
    ob["weekend"] = ob.ts.dt.dayofweek >= 5
    ob["month"] = ob.ts.dt.month
    return sh, ml, ob, meta, chp


def summary_vs_bento(ob):
    rows = [
        ("Station-hours", f"{len(ob):,}", "1,362,961"),
        ("Stations", f"{ob.station.nunique():,}", "1,318"),
        ("Lane speed, mean (mph)", f"{ob.speed.mean():.1f}", "60.9"),
        ("Lane speed, flow-weighted mean (mph)", f"{np.average(ob.speed, weights=ob.flow_pl):.1f}", "about 62"),
        ("Lane flow, mean (veh/hr)", f"{ob.flow_pl.mean():,.0f}", "1,438"),
        ("Lane flow, max (veh/hr)", f"{ob.flow_pl.max():,.0f}", "5,173"),
        ("Lane density, mean (veh/mile)", f"{ob.dens.mean():.1f}", "28.2"),
        ("Lane density, max (veh/mile)", f"{ob.dens.max():.0f}", "189"),
        (f"Share of hours above {KINK} veh/mile", f"{(ob.dens > KINK).mean():.1%}", "not reported"),
        (f"Share of hours above {FLOW_PEAK} veh/mile", f"{(ob.dens > FLOW_PEAK).mean():.1%}", "not reported"),
    ]
    t = pd.DataFrame(rows, columns=["measure", "d7_2026_observed", "bento_2017_table1"])
    t.to_csv(OUT / "summary_vs_bento.csv", index=False)
    return t


def quality_flags(ml, ob):
    flags = {
        "ML station-hours, all": len(ml),
        "ML station-hours, 0% observed (fully imputed)": int((ml.pct_obs == 0).sum()),
        "ML station-hours, 1-99% observed": int(ml.pct_obs.between(1, 99).sum()),
        "ML station-hours, 100% observed": len(ob),
        "observed: speed below 5 mph": int((ob.speed < 5).sum()),
        "observed: zero flow": int((ob.flow == 0).sum()),
        "observed: lane flow above 2,500 veh/hr": int((ob.flow_pl > 2500).sum()),
        "observed: occupancy above 0.5": int((ob.occ > 0.5).sum()),
        "observed: fewer lanes reporting than metadata": None,
    }
    t = pd.DataFrame(list(flags.items()), columns=["check", "rows"])
    t.to_csv(OUT / "quality_flags.csv", index=False)
    return t


def lanes_check(ob, meta):
    lanes = meta.sort_values("meta_date").groupby("ID").Lanes.last()
    lm = ob.station.map(lanes)
    t = pd.crosstab(ob.lanes_reporting, lm).rename_axis(index="lanes_reporting", columns="lanes_in_metadata")
    t.to_csv(OUT / "lanes_reporting_vs_metadata.csv")
    return int((ob.lanes_reporting < lm).sum())


def stuck_stations(ob):
    s = ob.groupby("station").speed.agg(["std", "count"])
    s = s[s["std"] < 1]
    s.to_csv(OUT / "stuck_speed_stations.csv")
    return s


def collisions(chp):
    d7 = chp[chp.district == 7].copy()
    d7["is_collision"] = d7.description.str.contains("Collision", na=False)
    d7["is_hit_run"] = d7.description.str.startswith(("20001", "20002"), na=False)
    t = d7.description.value_counts().head(20).rename_axis("description").reset_index(name="incidents")
    t.to_csv(OUT / "chp_d7_top_descriptions.csv", index=False)
    return d7


def freeway_table(ob, d7):
    col = d7[d7.is_collision]
    t = pd.DataFrame({
        "observed_station_hours": ob.groupby("fwy").size(),
        "observed_stations": ob.groupby("fwy").station.nunique(),
        "mean_density": ob.groupby("fwy").dens.mean().round(1),
        "share_above_kink": ob.groupby("fwy").dens.apply(lambda s: (s > KINK).mean()).round(3),
        "collisions": col.groupby("fwy").size(),
    }).fillna(0)
    t["share_of_observed_hours"] = (t.observed_station_hours / t.observed_station_hours.sum()).round(3)
    t["share_of_collisions"] = (t.collisions / t.collisions.sum()).round(3)
    t = t.sort_values("collisions", ascending=False)
    t.to_csv(OUT / "freeway_coverage_vs_collisions.csv")
    return t


def fig_fundamental(ob):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, y, ylab in [(axes[0], "speed", "Speed (mph)"), (axes[1], "flow_pl", "Flow per lane (veh/hr)")]:
        ax.hexbin(ob.dens, ob[y], gridsize=90, bins="log", cmap="Blues", mincnt=1, extent=(0, 100, 0, ob[y].max()))
        top = ax.get_ylim()[1]
        for x, lab, dx, ha in [(KINK, f"Bento kink, {KINK}", -1, "right"), (FLOW_PEAK, f"Bento flow peak, {FLOW_PEAK}", 1, "left")]:
            ax.axvline(x, color=INK2, lw=1, ls="--")
            ax.text(x + dx, top * 0.97, lab, color=INK2, fontsize=8, va="top", ha=ha,
                    bbox=dict(facecolor=SURF, edgecolor="none", pad=1))
        ax.set_xlim(0, 100)
        ax.set_xlabel("Density per lane (veh/mile)")
        ax.set_ylabel(ylab)
        ax.grid(False)
    axes[0].set_title("Speed holds near 65 mph, then falls past ~20 veh/mile")
    axes[1].set_title("Flow per lane peaks near 1,800 at 25-35 veh/mile")
    fig.text(0.01, 0.01, "Fully observed D7 mainline station-hours, Jan-Sep 2026 (n = 1.23M). Darker = more hours (log scale). "
             "Dashed lines: Bento et al. (2017 data) values.", fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "fig1_fundamental_diagram.png", dpi=150)
    plt.close(fig)


def fig_hourly(ob):
    wd = ob[~ob.weekend].groupby("hour")
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    axes[0].plot(wd.speed.median().index, wd.speed.median().values, color=BLUE, lw=2, marker="o", ms=3)
    axes[0].set_ylim(0, 75)
    axes[0].set_ylabel("Median speed (mph)")
    axes[0].set_title("Weekday median speed dips to ~59 mph, 9 am-5 pm")
    share = wd.dens.apply(lambda s: (s > KINK).mean())
    axes[1].bar(share.index, share.values * 100, color=BLUE, width=0.7)
    axes[1].set_ylim(0, 100)
    axes[1].set_ylabel(f"% of station-hours above {KINK} veh/mile")
    axes[1].set_title("Up to 65% of weekday hours are past the kink")
    for ax in axes:
        ax.set_xlabel("Hour of day")
        ax.set_xticks(range(0, 24, 3))
    fig.text(0.01, 0.01, "Fully observed D7 mainline station-hours, weekdays, Jan-Sep 2026.", fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "fig2_hour_of_day.png", dpi=150)
    plt.close(fig)


def fig_imputed(ml):
    bins = np.arange(0, 86, 1)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    for sel, color, lab in [(ml.pct_obs == 0, GREY, "Imputed by PeMS (0% observed)"),
                            (ml.pct_obs == 100, BLUE, "Real readings (100% observed)")]:
        h, _ = np.histogram(ml.loc[sel, "speed"], bins=bins, density=True)
        ax.plot(bins[:-1] + 0.5, h * 100, color=color, lw=2, label=lab)
    ax.set_xlabel("Hourly speed (mph)")
    ax.set_ylabel("% of station-hours")
    ax.set_title("Imputed speeds bunch at a few values; real readings are smooth")
    ax.legend(frameon=False, loc="upper left")
    fig.text(0.01, 0.01, "D7 mainline station-hours, Jan-Sep 2026. Imputed n = 10.8M, observed n = 1.23M.", fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "fig3_imputed_vs_observed_speed.png", dpi=150)
    plt.close(fig)


def fig_freeways(fw):
    t = fw.head(12).iloc[::-1]
    y = np.arange(len(t))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(y + 0.2, t.share_of_collisions * 100, height=0.38, color=GREY, label="Share of D7 collisions")
    ax.barh(y - 0.2, t.share_of_observed_hours * 100, height=0.38, color=BLUE, label="Share of usable sensor hours")
    ax.set_yticks(y, [f"Route {int(r)}" for r in t.index])
    ax.set_xlabel("% of D7 total")
    ax.set_title("Crashes happen on I-5, I-405 and I-110; working sensors sit on I-10 and I-210")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", visible=False)
    fig.text(0.01, 0.01, "12 freeways with the most collisions, Jan-Sep 2026. Collisions = CHP codes 1179/1181/1182/1183.", fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "fig4_freeway_coverage_vs_collisions.png", dpi=150)
    plt.close(fig)


def fig_persistence(ob):
    pm = ob.groupby("station").month.nunique().value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.bar(pm.index, pm.values, color=[BLUE if m == 9 else GREY for m in pm.index], width=0.7)
    for m, n in pm.items():
        ax.text(m, n + 2, str(n), ha="center", fontsize=8, color=INK)
    ax.set_xticks(range(1, 10))
    ax.set_xlabel("Months (of 9) with at least one fully observed hour")
    ax.set_ylabel("Stations")
    ax.set_title("152 of 430 stations report in all nine months")
    ax.annotate("89 stopped after Feb\n(mostly SR-118, SR-23)", xy=(2, 101), xytext=(3.2, 125),
                fontsize=8, color=INK2, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(OUT / "fig5_station_persistence.png", dpi=150)
    plt.close(fig)


def main():
    sh, ml, ob, meta, chp = load()
    print(summary_vs_bento(ob).to_string(index=False), "\n")
    q = quality_flags(ml, ob)
    q.loc[q.check.str.startswith("observed: fewer lanes"), "rows"] = lanes_check(ob, meta)
    q.to_csv(OUT / "quality_flags.csv", index=False)
    print(q.to_string(index=False), "\n")
    print("stations with near-constant speed (sd < 1 mph):\n", stuck_stations(ob), "\n")
    d7 = collisions(chp)
    days = d7.ts.dt.normalize().nunique()
    print(f"D7 incidents: {len(d7):,} ({len(d7)/days:.0f}/day); collisions {d7.is_collision.sum():,} "
          f"({d7.is_collision.sum()/days:.0f}/day); hit-and-run {d7.is_hit_run.sum():,}\n")
    fw = freeway_table(ob, d7)
    print(fw.head(12).to_string(), "\n")
    fig_fundamental(ob)
    fig_hourly(ob)
    fig_imputed(ml)
    fig_freeways(fw)
    fig_persistence(ob)
    print("figures written to", OUT)


if __name__ == "__main__":
    main()
