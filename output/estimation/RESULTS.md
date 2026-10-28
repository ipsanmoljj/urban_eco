# Results: District 7, January–September 2026

Scripts: `src/build/02_controls.py`, `src/build/03_instrument.py`, `src/estimate/01_breakpoint_search.py` to `04_welfare.py`. Run date 27 Oct 2026.

## Deviations from Bento et al. (state these in the write-up)

- **Data year:** 2026 instead of 2017, since PeMS now offers only 2026.
- **Instrument:** an incident on a **parallel freeway** (a different freeway, same direction of travel, 0.5–3 miles away), not on a Google-Maps alternative route. Google routes and LODES were dropped for time. 159 of 422 stations have such a parallel freeway; 1.31% of station-hours are treated.
- **Weather:** NOAA GHCNh hourly data, because ISD-Lite was retired in August 2025. Six stations: LAX, Burbank, Long Beach, Van Nuys, Santa Monica, Camarillo.
- **Breakpoint form:** the hinge `(density − b)·1[density > b]`. Eq. 4 as printed in the paper gives a degenerate breakpoint of 1.

## 1. Breakpoint (`breakpoint_search.csv`, `.png`)

With full controls, the hinge form picks **19 vehicles/mile/lane** (Bento: 21), with slope −0.0282. The high-flow rows make no difference.

## 2. Main estimates (`main_estimates.csv`)

Columns: below the kink (`<=19`) and above it (`>19`), ours against Bento et al.'s Tables 2–3.

| | Below, ours | Below, Bento | Above, ours | Above, Bento |
|---|---|---|---|---|
| OLS slope | −0.0113 (0.0008) | −0.0044 | −0.0270 (0.0004) | −0.0244 |
| First stage | 0.128 (0.070) | 0.033 | 0.984 (0.293) | 0.638 |
| First-stage F | 3.4 | 5.4 | 11.3 | 15.9 |
| IV slope | −0.0235 (0.0116) | −0.0196 | **−0.0378 (0.0047)** | −0.0327 |
| N | 747,013 | | 442,731 | |

SEs are clustered by station and date. Above the kink, the IV slope means each extra vehicle per mile per lane cuts speed by about 3.7% (Bento: 3.3%).

Robustness, above the kink (IV slope, F): without high-flow rows −0.0378 (11.3); collisions only −0.0353 (14.9); collisions plus hit-and-run −0.0358 (15.6); balanced panel of 151 stations −0.0328 (6.8, weak); holidays excluded −0.0380 (10.0); breakpoint of 21 −0.0379 (11.0).

## 3. Does the curve shift by time of day? (`time_of_day_*.csv`, `time_of_day.png`)

**Answer: no, in practice. Traffic moves along one curve.**
- **Slope:** between 06:00 and 20:00, the slope above the kink lies between −0.0270 and −0.0292 in every two-hour bracket (pooled −0.0282). A Wald test rejects exact equality (χ² = 74, p < 0.001), as it would with 1.2M observations. The differences are small, and the largest come from night brackets with very few hours above the kink (330–423).
- **Breakpoint:** 16–21 in every bracket from 04:00 to 24:00. The 00–04 brackets are uninformative, since only 0.3% of hours there are above the kink.
- **Elasticity:** Koch-style elasticities estimated bracket by bracket track the elasticity a single pooled curve implies at each bracket's densities (correlation 0.98 overall, 0.88 for 06–20, mean gap 0.06). At 16–18 the estimate is 0.61 against 0.67 from the single curve; Koch et al. report 0.67 for Berlin.
- **Implication:** the hour-to-hour pattern in congestion costs comes from density, not the clock. A toll that follows real-time density would capture what an hour-of-day schedule captures.

## 4. Tolls and welfare (`welfare_summary.csv`, `welfare_tolls_by_hour.csv`, `welfare.png`)

**Model.** Bento et al.'s representative-link model, applied to each station × hour-of-day cell (9,931 weekday cells, weighted by lane-miles):
- IV slope −0.0378 and breakpoint 19;
- free-flow speed 67.4 mph (mean at 2–4 am);
- flow peaks at 1,345 veh/hr/lane at 26.4 veh/mile, with a vertical queue beyond that (18% of cells are queued at their mean density);
- the cost per vehicle-mile is travel time only.

**Main case** (demand elasticity −2.0, VOT $24.30 per vehicle-hour):

| Policy | Gain (¢ per vehicle-mile) | Share of first best |
|---|---|---|
| First best (toll varies by station and hour) | 11.8 | 100% |
| Hourly toll (same at every station) | 3.4 | 29% |
| Two-hour toll | 3.3 | 28% |
| Best flat toll (12¢/mile, all day) | 2.7 | 23% |

- **Tolls:** the peak hourly toll is **27¢/mile** at 4–5 pm (Bento: 33¢, 2017 dollars). The morning peak is 22¢; night is 0–1¢.
- **Flat vs hourly:** a flat toll gets **80–83% of the hourly toll's gain** under every VOT and elasticity tried. The two-hour toll gets about 98% of it.
- **Where the gain comes from:** both time-based tolls capture under a third of the first-best gain. Most of the gain comes from varying the toll **by location**, i.e. by how congested each stretch actually is, which is consistent with result 3.
- **Sensitivity:** across elasticities −0.67 to −2.0 and VOT $15–$32, the peak hourly toll is 17–61¢/mile and the flat toll 8–28¢/mile.
- **Using OLS instead of IV** gives a 20¢ peak toll and a first-best gain of 6.8¢/mile. Ignoring the instrument understates the cost by about 40%.

## Limitations

- **The instrument is simpler than Bento's** and covers only stations with a parallel freeway nearby. With F of about 11, it is moderate, not strong.
- **Sensor coverage is thin and shrinking:** 422 stations, concentrated on I-10 and I-210.
- **The welfare model is static,** with no rerouting across the network and no change in departure times. Demand elasticity and VOT are assumed, not estimated.
- **Bento's 2017 data was not used to validate our code** (dropped for time).
