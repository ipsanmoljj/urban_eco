"""Apply the agreed cleaning rules to the D7 2026 data (agreed 26 Oct 2026).

Reads the parquet files from src/data/01_load_raw.py (data/interim/) and writes
cleaned datasets to data/cleaned/. Raw files are never modified.

Station-hour rules, applied in order:
  1. Mainline (ML) stations only.
  2. % Observed = 100: every detector at the station reported that hour.
  3. Drop hours where fewer lanes report than the station has in the metadata.
  4. Drop hours with zero flow (a recorded speed with no cars is a detector fault).
  5. Drop stations with stuck speeds (sd < 1 mph over the whole period).
Kept but flagged, for sensitivity runs at the modelling stage:
  - flag_high_flow: lane flow above 2,500 veh/hr (51 rows before cleaning).
  - holiday: US federal holiday.
  - station_all_months: station has observed hours in all nine months.
Incidents: all D7 CHP incidents are kept (the main definition, as in Bento et al.),
with flags for collisions and hit-and-runs for the robustness checks.
"""
from pathlib import Path

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

ROOT = Path(__file__).resolve().parents[2]
I = ROOT / "data" / "interim"
OUT = ROOT / "data" / "cleaned"
OUT.mkdir(parents=True, exist_ok=True)

HIGH_FLOW = 2500  # veh/hr/lane
STUCK_SD = 1.0    # mph


def stations(meta):
    """One row per mainline station: its latest metadata version."""
    st = (meta[meta.Type == "ML"].sort_values("meta_date").groupby("ID").last().reset_index())
    st = st.rename(columns={"ID": "station", "Fwy": "fwy", "Dir": "dir", "District": "district",
                            "County": "county", "City": "city", "State_PM": "state_pm",
                            "Abs_PM": "abs_pm", "Latitude": "lat", "Longitude": "lon",
                            "Length": "length", "Lanes": "lanes", "Name": "name"})
    st["last_meta_date"] = st.pop("meta_date").dt.date
    return st[["station", "fwy", "dir", "district", "county", "city", "state_pm", "abs_pm",
               "lat", "lon", "length", "lanes", "name", "last_meta_date"]]


def station_hours(sh, st):
    log = [("all rows, all lane types", len(sh))]

    d = sh[sh.lane_type == "ML"]
    log.append(("1. mainline only", len(d)))

    d = d[d.pct_obs == 100]
    log.append(("2. % observed = 100", len(d)))

    d = d.merge(st[["station", "lanes"]], on="station", how="left", validate="many_to_one")
    d = d[d.lanes_reporting >= d.lanes]
    log.append(("3. all metadata lanes reporting", len(d)))

    d = d[d.flow > 0]
    log.append(("4. flow > 0", len(d)))

    sd = d.groupby("station").speed.std()
    stuck = sd[sd < STUCK_SD].index
    d = d[~d.station.isin(stuck)].copy()
    log.append((f"5. drop {len(stuck)} stuck stations", len(d)))

    d["flow_pl"] = d.flow / d.lanes
    d["density"] = d.flow_pl / d.speed
    d["date"] = d.ts.dt.normalize()
    d["hour"] = d.ts.dt.hour.astype("int8")
    d["dow"] = d.ts.dt.dayofweek.astype("int8")
    d["month"] = d.ts.dt.month.astype("int8")
    holidays = USFederalHolidayCalendar().holidays(d.date.min(), d.date.max())
    d["holiday"] = d.date.isin(holidays)
    d["flag_high_flow"] = d.flow_pl > HIGH_FLOW
    months = d.groupby("station").month.nunique()
    d["station_all_months"] = d.station.map(months == months.max())

    cols = ["ts", "date", "hour", "dow", "month", "holiday", "station", "fwy", "dir", "lanes",
            "samples", "pct_obs", "flow", "occ", "speed", "flow_pl", "density",
            "flag_high_flow", "station_all_months"]
    return d[cols].sort_values(["station", "ts"]).reset_index(drop=True), log, list(stuck)


def incidents(chp):
    d = chp[chp.district == 7].copy()
    d["abs_pm"] = pd.to_numeric(d.abs_pm, errors="coerce")
    d["code"] = d.description.str.split("-").str[0]
    d["is_collision"] = d.code.isin(["1179", "1180", "1181", "1182", "1183"])
    d["is_hit_run"] = d.code.isin(["20001", "20002"])
    d["hour_start"] = d.ts.dt.floor("h")
    cols = ["incident_id", "ts", "hour_start", "code", "description", "location", "area", "lat",
            "lon", "fwy", "dir", "state_pm", "abs_pm", "duration_min", "is_collision", "is_hit_run"]
    return d[cols].sort_values("ts").reset_index(drop=True)


def main():
    sh = pd.read_parquet(I / "station_hour_d7_2026.parquet")
    meta = pd.read_parquet(I / "station_meta_d7_2026.parquet")
    chp = pd.read_parquet(I / "chp_incidents_2026.parquet")

    st = stations(meta)
    clean, log, stuck = station_hours(sh, st)
    inc = incidents(chp)

    st.to_csv(OUT / "stations_ml_d7.csv", index=False)
    clean.to_parquet(OUT / "station_hour_d7_2026_clean.parquet", index=False, compression="zstd")
    inc.to_parquet(OUT / "incidents_d7_2026.parquet", index=False, compression="zstd")

    log = pd.DataFrame(log, columns=["step", "rows_remaining"])
    log["rows_dropped"] = (-log.rows_remaining.diff()).fillna(0).astype(int)
    log.to_csv(OUT / "cleaning_log.csv", index=False)

    print(log.to_string(index=False))
    print(f"\nstuck stations dropped: {stuck}")
    print(f"stations kept: {clean.station.nunique()}, of which all nine months: "
          f"{clean.loc[clean.station_all_months, 'station'].nunique()}")
    print(f"flag_high_flow rows: {clean.flag_high_flow.sum()}, holiday rows: {clean.holiday.sum():,}")
    print(f"D7 incidents: {len(inc):,}; collisions {inc.is_collision.sum():,}; "
          f"hit-and-run {inc.is_hit_run.sum():,}")


if __name__ == "__main__":
    main()
