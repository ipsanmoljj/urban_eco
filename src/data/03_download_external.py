"""Download weather (NOAA GHCNh hourly) and gas prices (EIA weekly LA regular) for 2026.

NOAA retired ISD / ISD-Lite in August 2025 (station histories end 2025-08-27), so
2026 hourly weather comes from GHCNh, its replacement. Station IDs are USW000 + WBAN.
Bento et al. use six unnamed LA stations; ours are listed in STATIONS.
Raw files are saved untouched under data/raw/external/.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "external"

STATIONS = {  # GHCNh id: name, lat, lon (from NOAA isd-history.csv)
    "USW00023174": ("Los Angeles Intl (LAX)", 33.938, -118.387),
    "USW00023152": ("Burbank", 34.200, -118.365),
    "USW00023129": ("Long Beach", 33.812, -118.147),
    "USW00023130": ("Van Nuys", 34.212, -118.491),
    "USW00093197": ("Santa Monica", 34.021, -118.447),
    "USW00023136": ("Camarillo", 34.211, -119.088),
}
GHCNH = "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-year/2026/parquet/GHCNh_{sid}_2026.parquet"
EIA = "https://www.eia.gov/dnav/pet/hist_xls/EMM_EPMR_PTE_Y05LA_DPGw.xls"


def fetch(url, dest):
    subprocess.run(["curl", "-sS", "-f", "-m", "300", "-o", str(dest), url], check=True)
    print(f"{dest.relative_to(ROOT)}: {dest.stat().st_size:,} bytes")


def main():
    for sid in STATIONS:
        fetch(GHCNH.format(sid=sid), OUT / "weather" / f"GHCNh_{sid}_2026.parquet")
    fetch(EIA, OUT / "gas" / "EMM_EPMR_PTE_Y05LA_DPGw.xls")


if __name__ == "__main__":
    main()
