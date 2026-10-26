# Cleaned datasets: District 7, January–September 2026

Built by `src/data/02_clean.py` from the raw files (through `src/data/01_load_raw.py`). Raw files are never modified. Rules agreed on 26 Oct 2026.

To rebuild: download the Station Hour release (`CLAUDE.md` §7.5), then run `python src/data/01_load_raw.py` and `python src/data/02_clean.py`.

## Files

| File | What it is | Rows |
|---|---|---|
| `station_hour_d7_2026_clean.parquet` | Station-hours used for estimation | 1,209,294 |
| `incidents_d7_2026.parquet` | All D7 CHP incidents, with type flags | 102,544 |
| `stations_ml_d7.csv` | One row per mainline station: location, lanes (latest metadata version) | 1,936 |
| `cleaning_log.csv` | Rows remaining after each rule | 6 |

## Cleaning rules (station-hours)

| Step | Rule | Why | Rows dropped |
|---|---|---|---|
| 1 | Mainline (ML) stations only | HOV lanes and ramps follow a different speed–density relationship. Bento et al. do the same. | 19,497,032 |
| 2 | `% Observed = 100` | Keep only hours where every detector reported. PeMS fills the rest with imputed values. Bento et al. do the same. | 11,358,344 |
| 3 | All metadata lanes reporting | Per-lane density is wrong when a lane is silent. Our addition. | 12,952 |
| 4 | Flow > 0 | Zero cars with a recorded speed (median 68 mph) is a detector fault. Our addition. | 2,285 |
| 5 | Drop stuck stations (speed sd < 1 mph): 717992, 765920, 765922 | Speed that never changes is a broken detector. Our addition. | 2,660 |

Kept and flagged rather than dropped:
- `flag_high_flow`: lane flow above 2,500 veh/hr (51 rows). Models are run with and without these rows.
- `holiday`: US federal holiday (Jan 1, Jan 19, Feb 16, May 25, Jun 19, Jul 3, Sep 7).
- `station_all_months`: the station has data in all nine months (151 of 422 stations). Used for the balanced-panel robustness check.
- Speeds below 5 mph are kept, since they're plausible jams.

## Gaps in the data

PeMS has no real readings for any D7 station on 28 Feb, 27 May, 30 Aug–1 Sep, 5–7 Sep and 30 Sep 2026. Real readings also stop at 04:00 on 29 Sep. These hours are entirely imputed, so step 2 removes them. 26 and 28 May and 2 and 8 Sep are partial days.

## Columns: `station_hour_d7_2026_clean.parquet`

| Column | Meaning |
|---|---|
| `ts`, `date`, `hour`, `dow` (0 = Monday), `month` | Start of the hour |
| `holiday` | US federal holiday |
| `station`, `fwy`, `dir` | PeMS station ID, freeway number, direction |
| `lanes` | Mainline lanes (metadata) |
| `samples`, `pct_obs` | PeMS sample count; percent observed (always 100 here) |
| `flow` | Vehicles in the hour, all lanes |
| `occ` | Average occupancy (0–1) |
| `speed` | Average speed (mph) |
| `flow_pl` | Flow per lane (veh/hr/lane) = `flow / lanes` |
| `density` | Vehicles per mile per lane = `flow_pl / speed` |
| `flag_high_flow` | `flow_pl` above 2,500 |
| `station_all_months` | Station present in all nine months |

## Columns: `incidents_d7_2026.parquet`

All D7 incidents are kept. The main instrument uses all of them, matching Bento et al., who matched "every traffic incident report". Robustness checks use `is_collision` (CHP codes 1179–1183) and `is_collision | is_hit_run` (adds 20001/20002).

| Column | Meaning |
|---|---|
| `incident_id`, `ts`, `hour_start` | CHP incident ID, start time, start of its hour |
| `code`, `description` | CHP code and text, e.g. `1182`, "Trfc Collision-No Inj" |
| `location`, `area`, `lat`, `lon` | Location text and coordinates |
| `fwy`, `dir`, `state_pm`, `abs_pm` | Freeway, direction, state and absolute postmile |
| `duration_min` | Minutes until cleared |
| `is_collision`, `is_hit_run` | Type flags |
