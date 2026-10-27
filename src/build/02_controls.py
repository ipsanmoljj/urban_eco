"""Attach weather and gas-price controls to the analysis station-hours.

Weather (NOAA GHCNh): per weather station and hour, mean temperature (C), mean
wind speed (m/s) and precipitation (mm; reports without precipitation count as 0).
Reports are assigned to the hour they fall in. Each PeMS station uses the closest
weather station with a temperature reading in that hour (Bento et al.: "the closest
weather station for which data is provided during that hour").
Gas: EIA weekly Los Angeles regular retail price; each date takes the price of the
week starting on the most recent Monday.

Writes data/analysis/weather_hourly.csv, data/analysis/gas_weekly.csv and adds
temp_c, wind_ms, precip_mm, gas_price to station_hour_d7_2026_analysis.parquet.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "data"))
from importlib import import_module  # noqa: E402

STATIONS = import_module("03_download_external").STATIONS
RAW = ROOT / "data" / "raw" / "external"
AN = ROOT / "data" / "analysis"


def weather():
    parts = []
    for sid in STATIONS:
        w = pd.read_parquet(RAW / "weather" / f"GHCNh_{sid}_2026.parquet",
                            columns=["DATE", "temperature", "wind_speed", "precipitation"])
        w["ts"] = pd.to_datetime(w.DATE).dt.floor("h")
        h = w.groupby("ts").agg(temp_c=("temperature", "mean"), wind_ms=("wind_speed", "mean"),
                                precip_mm=("precipitation", lambda s: s.fillna(0).max()))
        h["wx_station"] = sid
        parts.append(h.reset_index())
    return pd.concat(parts, ignore_index=True)


def gas():
    g = pd.read_excel(RAW / "gas" / "EMM_EPMR_PTE_Y05LA_DPGw.xls", sheet_name="Data 1", skiprows=2)
    g.columns = ["week", "gas_price"]
    g["week"] = pd.to_datetime(g.week)
    return g[(g.week >= "2025-12-01") & (g.week <= "2026-10-31")].reset_index(drop=True)


def haversine_mi(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * np.arcsin(np.sqrt(a))


def main():
    wx = weather()
    gp = gas()
    wx.to_csv(AN / "weather_hourly.csv", index=False)
    gp.to_csv(AN / "gas_weekly.csv", index=False)

    st = pd.read_csv(AN / "stations_links_d7.csv")
    ids = list(STATIONS)
    dist = np.column_stack([haversine_mi(st.lat, st.lon, STATIONS[s][1], STATIONS[s][2]) for s in ids])
    order = np.argsort(dist, axis=1)

    sh = pd.read_parquet(AN / "station_hour_d7_2026_analysis.parquet")
    sh = sh.drop(columns=[c for c in ["temp_c", "wind_ms", "precip_mm", "gas_price"] if c in sh], errors="ignore")
    rank = pd.DataFrame(order, columns=[f"r{k}" for k in range(len(ids))])
    rank["station"] = st.station.values
    sh = sh.merge(rank, on="station", how="left")

    wxi = wx.set_index(["wx_station", "ts"])
    for c in ["temp_c", "wind_ms", "precip_mm"]:
        sh[c] = np.nan
    for k in range(len(ids)):
        need = sh.temp_c.isna()
        if not need.any():
            break
        cand = pd.Series(np.array(ids)[sh.loc[need, f"r{k}"].to_numpy()], index=sh.index[need])
        key = pd.MultiIndex.from_arrays([cand.values, sh.loc[need, "ts"].values])
        vals = wxi.reindex(key)
        for c in ["temp_c", "wind_ms", "precip_mm"]:
            sh.loc[need, c] = vals[c].to_numpy()
        sh.loc[need & sh.temp_c.notna(), "wx_rank_used"] = k
    sh["wind_ms"] = sh.wind_ms.fillna(sh.groupby("ts").wind_ms.transform("mean"))
    sh["precip_mm"] = sh.precip_mm.fillna(0)
    sh = sh.drop(columns=[f"r{k}" for k in range(len(ids))])

    week = sh.ts.dt.normalize() - pd.to_timedelta(sh.ts.dt.dayofweek, unit="D")
    sh = sh.merge(gp.rename(columns={"week": "_week"}), left_on=week.rename("_week"), right_on="_week", how="left")
    sh = sh.drop(columns=["key_0", "_week"], errors="ignore")

    sh.to_parquet(AN / "station_hour_d7_2026_analysis.parquet", index=False, compression="zstd")
    print(f"rows {len(sh):,}; temp missing {sh.temp_c.isna().mean():.3%}; "
          f"nearest weather station used {(sh.wx_rank_used == 0).mean():.1%}; gas missing {sh.gas_price.isna().mean():.3%}")
    print(sh[["temp_c", "wind_ms", "precip_mm", "gas_price"]].describe().round(2).to_string())
    print(f"station-hours with any rain: {(sh.precip_mm > 0).mean():.2%}")


if __name__ == "__main__":
    main()
