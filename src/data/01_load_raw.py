"""Convert raw PeMS / CHP files to parquet for exploration.

No rows are dropped and no values are changed: this only parses the raw text
files once so the EDA does not re-read 450 MB of gzip each run.
Outputs go to data/interim/ (git-ignored).
"""
import glob
import io
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "pems" / "d7"
OUT = ROOT / "data" / "interim"
OUT.mkdir(parents=True, exist_ok=True)

# PeMS Station Hour layout: 12 station-level fields, 6 delay fields, then
# (flow, occupancy, speed) for up to 8 lanes.
SH_COLS = ["ts", "station", "district", "fwy", "dir", "lane_type", "length",
           "samples", "pct_obs", "flow", "occ", "speed"]
LANE_FLOW_IDX = list(range(18, 42, 3))

CHP_COLS = ["incident_id", "cc_code", "incident_number", "ts", "description",
            "location", "area", "zoom_map", "tb_xy", "lat", "lon", "district",
            "county_fips", "city_fips", "fwy", "dir", "state_pm", "abs_pm",
            "severity", "duration_min"]


def station_hour():
    parts = []
    for f in sorted(glob.glob(str(RAW / "station_hour" / "d07_text_station_hour_2026_*.txt.gz"))):
        d = pd.read_csv(f, header=None, usecols=list(range(12)) + LANE_FLOW_IDX)
        lane_flows = d[LANE_FLOW_IDX]
        d = d[list(range(12))]
        d.columns = SH_COLS
        d["lanes_reporting"] = lane_flows.notna().sum(axis=1).astype("int8")
        d["ts"] = pd.to_datetime(d["ts"], format="%m/%d/%Y %H:%M:%S")
        for c in ["fwy", "district"]:
            d[c] = d[c].astype("int16")
        for c in ["dir", "lane_type"]:
            d[c] = d[c].astype("category")
        parts.append(d)
        print(f"{Path(f).name}: {len(d):,} rows")
    sh = pd.concat(parts, ignore_index=True)
    for c in ["dir", "lane_type"]:
        sh[c] = sh[c].astype("category")
    sh.to_parquet(OUT / "station_hour_d7_2026.parquet", index=False)
    print(f"station hour total: {len(sh):,} rows")


def metadata():
    parts = []
    for f in sorted(ROOT.glob("d07_text_meta_2026_*.txt")):
        m = pd.read_csv(f, sep="\t")
        m["meta_date"] = pd.to_datetime(f.stem[-10:], format="%Y_%m_%d")
        parts.append(m)
    meta = pd.concat(parts, ignore_index=True)
    meta.to_parquet(OUT / "station_meta_d7_2026.parquet", index=False)
    print(f"metadata: {len(meta):,} rows from {len(parts)} versions")


def chp():
    parts = []
    for z in sorted(ROOT.glob("all_text_chp_incidents_month_2026_*.txt.zip")):
        month = z.name[-10:-8]
        with zipfile.ZipFile(z) as zf:
            inner = f"all_text_chp_incidents_month_2026_{month}.txt.gz"
            d = pd.read_csv(io.BytesIO(zf.read(inner)), compression="gzip",
                            header=None, names=CHP_COLS, dtype={"state_pm": str})
        parts.append(d)
    chp = pd.concat(parts, ignore_index=True)
    chp["ts"] = pd.to_datetime(chp["ts"], format="%m/%d/%Y %H:%M:%S")
    chp.to_parquet(OUT / "chp_incidents_2026.parquet", index=False)
    print(f"CHP incidents (statewide): {len(chp):,} rows")


if __name__ == "__main__":
    metadata()
    chp()
    station_hour()
