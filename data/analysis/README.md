# Analysis datasets: District 7, January–September 2026

Built by `src/build/01_links_incidents_vmt.py` from `data/cleaned/` and the raw metadata (via `data/interim/`). These are derived variables for the instrument and the controls. Nothing here changes the cleaned data.

## Files

| File | What it is |
|---|---|
| `station_hour_d7_2026_analysis.parquet` | The cleaned station-hours (1,209,294) plus `link`, own-link incident flags and `d7_vmt`. **Use this file for estimation.** |
| `incidents_d7_matched.parquet` | All D7 incidents, with the nearest mainline station (same freeway and direction, under 1 mile), its link, and the distance |
| `interchanges_d7.csv` | 1,092 interchanges located from PeMS ramp stations |
| `links_d7.csv` | 1,137 links (interchange to interchange) with postmile bounds and length |
| `stations_links_d7.csv` | Every mainline station (including ones with no real readings) and its link |
| `d7_vmt_hourly.csv` | Hourly D7 vehicle-miles travelled |

## How each piece is built

**Interchanges and links.** Bento et al. drop station-hours on any link (interchange to interchange) that has a crash in that hour, but don't say how they define links. We place interchanges at PeMS ramp stations (on-ramps, off-ramps, freeway connectors, collector-distributors). Ramps belong to one interchange if they share a street name (ignoring NB/SB, 1/2, Ave/Blvd) and are within 0.6 miles of each other, or if any two ramps are within 0.15 miles. Interior links have a median length of 0.78 miles (10th percentile 0.32, 90th percentile 1.61). Limitation: an interchange with no ramp detector is missed, which makes the surrounding link longer.

**Incident matching.** As in Bento et al.: the nearest mainline station on the same freeway and direction, by straight-line distance, if under 1 mile. This uses all mainline stations, including ones with no real readings, because only their location matters. 96,662 of 102,544 incidents (94.3%) match.

**Own-link flags.** `own_link_incident` is true if any matched incident starts in that hour on the station's link. That's 14,676 station-hours (1.21%), which Bento et al. would drop. `own_link_collision` (0.42%) and `own_link_collision_hr` (0.48%) are the same flag for the robustness definitions.

**D7 VMT.** For each hour, the sum over all mainline station-hours of flow × station length. This includes stations with no real readings, which is fine for a district-wide background control. The median is 4.4 million vehicle-miles per hour.

## Extra columns in `station_hour_d7_2026_analysis.parquet`

| Column | Meaning |
|---|---|
| `link` | Link ID, `<freeway><direction>-<index>` |
| `own_link_incident`, `own_link_collision`, `own_link_collision_hr` | Incident on own link this hour (all incidents; collisions; collisions plus hit-and-run) |
| `d7_vmt` | D7 vehicle-miles travelled this hour |
