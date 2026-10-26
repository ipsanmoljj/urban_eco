# Congestion Pricing on California Freeways: Project Brief

This is the handoff from claude.ai ("urban project", Oct 2026) to Claude Code. It is current as of 25 Oct 2026.

Confidence tags carried over from earlier discussion:
- **[Certain]**: read directly from the paper or checked by arithmetic.
- **[Likely]**: strong inference.
- **[Guessing]**: filling gaps.

---

## 0. Read this first

**Analysis year: 2026 (decided 25 Oct 2026).** The analysis uses 2026 PeMS data, not Bento's 2017 sample. This turns the project from an exact replication into a **re-estimation of Bento's design on 2026 data**, benchmarked against their published numbers. Consequences:
- [Certain] Bento's Tables 2–4 can't be reproduced number for number from 2026 data. Gaps against the paper mix two causes: differences in our code, and real change between 2017 and 2026 (post-COVID demand, remote work, a changed detector network).
- [Likely] The only way to separate the two is to run our pipeline on Bento's own 2017 data from the Dataverse package, if it is complete enough. That makes the package a code-validation tool rather than the main dataset.
- [Likely] Upside: Google routes queried today now match the network in the data. In the 2017 design that mismatch was a weakness.
- [Certain] The D7 network is much larger now: about 1,930 mainline (ML) stations in the 2026 metadata, against 1,318 used by Bento.

**Status (25 Oct 2026).**
- The research design is settled. The year changed to 2026; see above.
- Repo: `ipsanmoljj/urban_eco`.
- Downloaded and in the repo root (not yet moved into `data/raw/`):
  - CHP Incidents, monthly, Jan–Sep 2026 (statewide; each zip holds the summary and detail files);
  - D7 Station Metadata versions dated 17 Jul, 25 Aug and 24 Oct 2026.
- D7 Station Hour, Jan–Sep 2026: on the GitHub release `data-d7-2026` (§7.5). All 9 files verified: complete hours, no duplicate rows.
- **Missing:** D7 metadata versions for Jan–Jun 2026.
- **Jan–Sep coverage** [Certain]: 1,227,191 fully observed mainline station-hours from 430 stations (Bento: 1.36M). Coverage falls through the year, from 267 observed stations per hour in January to 140 in September. Detectors are failing, not being repaired. I-10 and I-210 hold 47% of observed rows; I-405 holds 3.6%.
- [Certain] **The PeMS Clearinghouse currently offers only 2026 data** (checked by Inderpal, 25 Oct 2026). Bento's Dataverse package is now the only source of 2017 data.

**Detector coverage in 2026 is poor** [Certain, from the Jul–Sep files]:
- 1,572 of 1,936 D7 mainline stations report 0% observed for the whole quarter. Their speed and flow are entirely imputed.
- Fully observed (`% Observed = 100`) mainline data: 370,002 station-hours, 271 stations, about 168 stations per hour. Bento's 2017 sample averaged about 616 per hour (1.36M ÷ 2,208).
- I-10 and I-210 hold 52% of the fully observed rows. I-405 is thin and I-110 is nearly absent.
- Never use imputed rows for the slope: PeMS imputes speed from neighbouring stations and history.
- [Likely] Only the *treated* station needs real readings. Crashes and alternate routes are located from CHP lat/lon and station metadata, and imputed stations still have valid locations.
- [Guessing] First-stage power scales roughly with sample size, so a Jul–Sep sample would give a KP F of about 4 against Bento's 15.9. Jan–Sep would give roughly 12. Get Jan–Jun before building the instrument.
- The Bento Dataverse package has not been opened. Dataverse is blocked from the cloud session too (proxy 403), so Inderpal downloads it manually.
- EDA done (26 Oct 2026): `src/eda/eda.py`, findings in `output/eda/EDA_REPORT.md`.
- Cleaning done (26 Oct 2026, rules agreed with Inderpal): `src/data/02_clean.py` writes `data/cleaned/` (tracked in git; see its README). 1,209,294 station-hours, 422 stations. Decisions:
  - Lane flow above 2,500 is kept with `flag_high_flow`; **run every model with and without these rows.**
  - Main instrument uses **all CHP incidents** (Bento matched "every traffic incident report"); robustness checks use collisions only, and collisions plus hit-and-run.
  - Holidays kept with a flag; balanced-panel check on the 151 stations present in all nine months.
  - PeMS has no real D7 readings on 28 Feb, 27 May, 30 Aug–1 Sep, 5–7 Sep and 30 Sep 2026 (district-wide outages).
- **What Bento et al. report about cleaning** [Certain]: only mainline stations and "station-hour observations where all the component detectors are reporting". There's no flow cap (their max lane flow is 5,173), and nothing on stuck detectors or holidays. Their incident counts also conflict: "more than 14,000 incidents" at "around 450 per day" implies about 31 days, while Table 1's 471/day over 92 days implies about 43,000.

**First job.** Get the Bento Dataverse package and inventory it:
- files and variables,
- date range,
- observation counts,
- whether it includes the do-files and the station–route–crash crosswalk.

Its main uses now: reading their code and construction choices, and validating our pipeline on their 2017 data. The 2017 crosswalk doesn't carry over to the 2026 station network.

**Blockers Claude Code can't solve alone.**
- PeMS bulk data needs a logged-in account. Caltrans blocks programmatic access to the Clearinghouse. Inderpal downloads these files manually in the browser and puts them in `data/raw/pems/`. Claude Code should never try to log in or scrape PeMS.
- The Dataverse download was blocked from the claude.ai sandbox. [Guessing] It may work from a local machine through the Dataverse API. If not, Inderpal downloads it manually.

**Open decisions.** These are the user's calls; ask before assuming. See §10.

---

## 1. Research question

**Working title (revised 15 Oct):**
> Does the optimal congestion toll on California freeways vary by hour because the congestion curve shifts, or only because demand moves along it? Parry's framework, Bento et al.'s crash instrument, and Koch et al.'s time-bracket elasticities, tested on 2026 PeMS data for Districts 7 and 4.

**Why this framing.** An earlier framing said "the two papers disagree on time-of-day variation." That was wrong. [Certain] In Bento's form, the elasticity of travel time with respect to density is slope × density, and mean density differs by period. Their Table 4, Panel B, gives:

| Period | Slope | Mean density | Implied elasticity |
|---|---|---|---|
| AM peak | 0.0346 | 37.95 | 1.31 |
| PM peak | 0.0306 | 41.85 | 1.28 |
| Night | 0.0298 | 30.52 | 0.91 |

So both papers already imply hour-varying tolls. The real question is *why* tolls vary by hour.

- **(a) Same curve.** Peak hours just sit further along the same curve. The policy then is to price on real-time density, not on the clock.
- **(b) Shifting curve.** The curve itself shifts by hour, through driver mix, ramp metering or incidents. Hour-specific tolls are then justified independently.

**Test.** Estimate Bento's kinked speed–density curve with the slope and breakpoint allowed to differ by two-hour bracket. Then check whether the brackets still matter once density is controlled for.

**Role of each paper.**
- **Parry (2009):** the theory. That covers marginal external cost (MEC), why the toll differs from MEC at pre-toll traffic, and flat versus time-varying tolls.
- **Bento, Hall & Heilmann (2023):** the design we re-estimate on 2026 data, the benchmark numbers, and the causal identification on PeMS data.
- **Koch, Ritter, Rohlf & Thies (2023):** the log-log functional form, the two-hour time brackets, and the closed-form welfare formulas. **Not** its machine-learning pipeline; see §5.

**Scope.** This is a low-key course project. Prefer one clean estimate over three half-done models.

---

## 2. Papers and links

| Paper | Role | Link |
|---|---|---|
| Bento, Hall & Heilmann (2023), *Evaluating Alternative Strategies for Traffic Reduction in Los Angeles*, NCST report NCST-USC-RR-23-28 | Replicate | PDF: https://rosap.ntl.bts.gov/view/dot/71875/dot_71875_DS1.pdf · DOI: https://doi.org/10.7922/G2JW8C6H |
| Bento et al. replication data (Stata) | Replicate | https://doi.org/10.7910/DVN/VMJIRX (Harvard Dataverse) |
| Koch, Ritter, Rohlf & Thies (2023), *Machine Learning from Big GPS Data about the Heterogeneous Costs of Congestion*, SSRN, 31 Jul 2023 | Method source | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4526796 · DOI: https://doi.org/10.2139/ssrn.4526796 |
| Parry (2009), *Pricing Urban Congestion* | Theory frame | The PDF in hand is **RFF Discussion Paper 08-35 (Nov 2008)**; cite that version. [Likely] The *Annual Review of Resource Economics* 2009 version may number sections differently. |
| Akbar, Couture, Duranton & Storeygard (2023), *Mobility and Congestion in Urban India*, AER | Discussion only | https://www.aeaweb.org/doi/10.1257/aer.20181662 |

**Koch version warning.** [Certain] Older drafts in circulation have different headline numbers. A ZEW seminar version reports 2.8–34 c/km and says a uniform tax gets 32% of the optimal gains. **Use the SSRN July 2023 version** (3.0–87.4 c/km, 78%). All Koch numbers in this file are from that version.

---

## 3. Plan

1. **Inventory the Dataverse package.** If the observation counts don't reconcile with the paper, email Jonathan Hall before going further.
2. **Validate the pipeline on Bento's 2017 data** (if the package allows): run our estimation code on their data and check that it reproduces their Tables 2–4. This proves the code before it meets 2026 data. If the package lacks the inputs, say so and skip.
3. **Re-estimate Bento Tables 2–4 on 2026 D7 data**, reporting each number next to the published 2017 value:
   - the breakpoint search (§4.2): does it still pick 21 vehicles/mile/lane?
   - Table 2: the first stage;
   - Table 3: OLS vs IV, below and above the kink. This is the core result.
   - Table 4: heterogeneity across freeways and periods.
   - Re-query Google routes for a 2026 sample of OD pairs. The 2017 crosswalk doesn't match the 2026 station network.
4. **Rebuild the LA welfare step (§6.2–6.3) independently on 2026 estimates.** Bento's figure to compare against is about 33¢/mile, not $0.81 (see §4 inconsistencies). Convert to 2026 dollars before comparing.
5. **Extend to District 4** (SF Bay Area), 2026:
   - Bento's crash instrument;
   - Koch-style two-hour-bracket elasticities;
   - density-bin σ;
   - bracket-specific slope and breakpoint (the §1 test).
6. **Compute a true uniform-toll second best** (one toll imposed on brackets with different σ) before quoting any "% of optimal" figure.
7. **Compare with Parry's city figures as a sanity check only** (§6).

---

## 4. Bento, Hall & Heilmann (2023): details

**Data**
- **Caltrans PeMS, District 7** (LA and Ventura counties), 2017.
  - Hourly mainline-station data, 1,318 stations.
  - Keeps only station-hours where every component detector reports.
- **PeMS CHP-investigated crash reports:** location, minute-level time, description and duration.
- **LEHD LODES** home–work census-block pairs.
- **Google Maps API:** the preferred route plus up to two alternatives for a 1% random sample of commutes (19,163 origin–destination pairs).
- **Controls:**
  - NOAA ISD-Lite hourly weather from 6 LA stations (the stations are unnamed);
  - EIA weekly LA regular gasoline price;
  - District 7 VMT.

**Construction**
1. Take each Google alternative route and keep only the part that doesn't overlap the main route. Match those parts to PeMS stations in the correct direction.
2. Match each crash to the nearest station within 1 mile, on the same freeway and direction.
3. A station is *treated* in an hour if a crash occurs on the non-overlapping part of one of its alternatives.
4. Drop any station-hour on a link (interchange to interchange) that had its own crash. This removes the crash's direct capacity effect.
5. Density = flow ÷ speed, per lane. They use density because speed–density is single-valued, while speed–flow bends backward.

**Estimation**
- **First stage:** Density = γ·(crash on alternate) + controls.
- **Second stage:** log(Speed) = β·Density + controls.
- **Fixed effects:** station, hour-of-day, day-of-week and month, entered additively.
- **Other controls:** temperature and its square, wind, precipitation, gas price, D7 VMT.
- **Standard errors:** two-way clustered.
- **Kink:** run 50 OLS fits with the slope forced to zero below a threshold of 1 to 50 vehicles/mile. AIC (minimized) picks 21. Then split the sample on whether the average density of each detector × day-of-week × hour cell is above 21, and run the IV on each side.

**Reported results**

| | Below kink | Above kink |
|---|---|---|
| First stage (crash → density) | 0.033, not significant | 0.638*** |
| OLS slope on log speed | −0.0044 | −0.0244 |
| IV slope, with controls | −0.0196, not significant (KP F 5.4) | −0.0327*** (KP F 15.9) |

- **Heterogeneity:** the slope is stable across I-5, I-10, I-110 and I-405 (−0.030 to −0.034) and across the AM peak, PM peak and night. The midday estimate is noise (SE 0.70).

**Welfare model**
- A single representative link in a static model.
- Supply: the IV slope above the kink, with free-flow speed taken as the 2–4 am average.
- The backward-bending part of the speed–flow curve is replaced by a vertical queue (following Verhoef 2001).
- Demand elasticity: −2.0 (assumed).
- Value of time: about $15 per vehicle-hour. It appears as both $15.00 and $15.19, with 1.6 occupants per vehicle.

**Headline claims:**
- peak toll of 33¢/mile, lower or zero off-peak;
- more than $2bn a year in welfare gains;
- ignoring the kink understates high-flow MEC by more than 60%.

**Internal inconsistencies** [Certain unless tagged]
- **Missing results.** The 33¢, 10% VMT cut, $2bn and 56% figures, the promised toll maps and the distributional results never appear in the body.
- **Same coefficient, three values.** It is reported as 3.11%, 3.27% and 3.1%.
- **Study period.** It is described as "2017", "August 2017" and "three months". Table 1 covers 92 days.
- **Observation counts.** Table 1 has 1.36M station-hours, but Table 2 has 5.5M observations, more than the 2.9M possible (1,318 stations × 2,208 hours). So the regression unit is not a station-hour. [Guessing] It may be station × alternative-route pairs.
- **Table 2 F-statistics don't match coef/SE.** Below the kink, t = 1.28 implies F ≈ 1.6, but 107.5 is reported. Use the KP F values from Table 3.
- **Text vs specification.** The text says comparisons are made within station × hour × DOW × month cells, but the fixed effects are additive.
- **Typos.** Equation references are shifted, and AIC is described as "maximized".
- [Likely] **§6.3 text contradicts Fig. 14b.**
  - The text says flow goes from 1,560 vph/lane at 30 mph to 1,441 at 69 mph, with a $0.81/mile toll and $0.68 welfare gain per vehicle-mile.
  - Reading the figure gives roughly 1,675 → 1,510 and a gap of about $0.33, which matches the abstract.
  - Trust the figure, and verify against the code.
- [Likely] **The "lower bound" claim is wrong as stated.** Random crash under-reporting shrinks the first stage and the reduced form by the same factor, so the IV ratio stays unbiased. Only density-dependent misreporting causes bias, and its direction is unknown.
- [Likely] **The toll is fragile because of the kink.** MEC jumps from 0 to about $0.38 at capacity (Fig. 13), and the optimum sits just past the kink. The breakpoint is chosen by OLS AIC.
- **Hypercongestion is treated as non-causal,** despite Hall's own work arguing otherwise.
- [Likely] **The welfare model ignores the network:** no rerouting, even though identification relies on rerouting.

---

## 5. Koch, Ritter, Rohlf & Thies (2023): what to take, what to skip

**What they did**
- Data: INRIX GPS trips in Berlin, 2017, full year.
- DBSCAN clusters anonymous trips into pseudo-drivers. QuickBundles groups trips into routes.
- Density: count all INRIX trips crossing a convex hull around the route in each hour (median 255).
- Main equation: log(TimeCost) = σ·log(Density) + weather + holidays + driver-route FE + DOW FE + hour FE. Standard errors are clustered by route.
- Instrument: the number of incidents whose 50–1,000 m ring the route crosses. Trips passing within 50 m of an incident are dropped.

**Results**
- First stage: an incident raises density about 2.5% (KP F ≈ 2,000).
- Elasticity: OLS 0.067, IV 0.492; 0.40–0.57 across specifications.
- By two-hour bracket:
  - peaks: 08–10 = 0.63, 16–18 = 0.67;
  - lows: 10–12 = 0.17, 04–06 = 0.13, 20–22 = 0.08;
  - peak vs off-peak: 0.55 vs 0.26.
- No spatial variation: CBD 0.49, inner ring 0.45, outer 0.46.
- MEC: 3.0–87.4 c/km. Optimal charges: 3.0–42.3 c/km, against a uniform 27.9 c/km.
- Welfare per year: €985M with hourly charges, €784M peak/off-peak, €771M uniform ("uniform is 78% as effective").
- Value of time: 33% of the median wage (about €8.44/hour), one person per car.

**TAKE (works on PeMS)**
1. The log-log form, giving an elasticity σ (their eq. 1).
2. Two-hour time brackets instead of Bento's four broad periods.
3. The cost formula: MECC = σ/(1−σ) × average travel-time cost. This is Parry's VOT·V·T′(V) with an estimated curve in place of BPR.
4. The toll and welfare formulas (eqs. 6–7).
   - [Certain] Eq. 7 is undefined at their baseline η = 1, because it contains η/(η−1).
   - Use the limit: **Δ(σ) = σ + (1−σ)·ln(1−σ)**.
   - Check: σ = 0.493 gives 14.9% and σ = 0.665 gives 29.9%, both matching their numbers.

**SKIP**
- [Certain] DBSCAN, QuickBundles and convex-hull density. They need vehicle trajectories, and PeMS is fixed loop detectors.
- [Likely] Koch's 50–1,000 m incident ring. On freeways, a crash within 1 km is often on the opposite carriageway, and drivers slowing to look at it would contaminate the instrument. Use Bento's same-direction route matching.

**Cautions**
- [Certain] **σ/(1−σ) blows up as σ → 1.**
  - Past σ = 1 (the backward-bending, queueing part of the curve), more cars *lower* flow.
  - In Bento's estimates, flow peaks at 1/0.0327 ≈ 30.6 veh/mile, and the congested-sample mean (36.8) sits past that point.
  - σ = 0.67 gives a factor of about 2. σ = 0.95 gives about 19, which is hypersensitive.
  - If you run log-log on PeMS, keep Bento's treatment: cap flow at its maximum and treat anything beyond it as a queue.
- [Likely] **The 78% is not a real second-best comparison.**
  - Their "uniform" figure is the optimum of a world where σ is constant all day.
  - Δ(σ) is convex, so part of the 22% gap is Jensen's inequality, not policy.
  - Don't quote it as a finding.
- [Likely] **Half the welfare gain comes from people the elasticity wasn't estimated on.** Δ is scaled by the travel time of cyclists (18%) and bus/tram users (7%) as well as cars (26%). The shares sum to 51%, but 49% is used.
- [Certain] **Ω and Φ calibration is undocumented.** This is the biggest obstacle to reproducing the euro figures.
- [Likely] **Noisy density.** The hull count isn't on-route density, so OLS is attenuated. That probably explains most of the 7× OLS/IV gap. In LA, IV is only about a third above OLS.
- [Likely] **Possible unstated transformation.** log(incident count) with mostly-zero counts implies one. Try both log(1+x) and asinh.
- [Likely] **"Drivers" are really OD clusters.** Only 6.6% of trips survive clustering, and those trips are shorter and slower than average.
- [Certain] **Text slips.**
  - The η = 0.5 paragraph quotes the η = 1.5 figures (€885M/€887M).
  - "17:00–18:59" should be 16:00–17:59.
  - The peak/off-peak windows leave 12:00–14:00 unassigned.

**Converting units between the papers** [Certain]
- Bento's semi-elasticity converts to Koch's elasticity as σ = 0.0327 × D.
- That gives 0.69 at the kink (D = 21) and 1.20 at the congested mean (D = 36.8). Koch's peak is 0.67.
- [Likely] Bento finds σ rising with density, while Koch assumes σ is constant and varies only by clock time. Koch's hourly pattern may be density variation in disguise. **This is the core extension test.**

---

## 6. Parry framework: notes and traps

- **General MEC = VOT · V · ∂T/∂V.** [Certain] The shortcut MEC = VOT·β·AD holds only under BPR, because it relies on V·T′(V) = β(T − T_f). Once the curve is estimated, use the general form.
- **BPR uses the volume/capacity ratio, not raw flow.** [Certain] Plugging 2,000 vph into α = 0.15, β = 4 gives nonsense. If a BPR baseline is fitted, use nonlinear least squares on V/C.
- **The optimal toll is below MEC at pre-toll traffic,** because traffic falls once the toll applies. [Certain] Getting the toll needs a demand response. Parry says it can't be observed before tolling exists, so **report a sensitivity range for demand elasticity**, not one number. Bento assumes −2.0; Koch assumes η = 1.
- **Parry's city figures (Table 2: LA, SF, San Diego, San Jose) are a sanity check, not a validation target.** [Guessing] They are probably metro-wide, all-road averages, built on an assumed curve, in older dollars. Match units, year and road type before comparing, and compare on LA first, where Bento's number is also available.
- **Bottleneck model, single-lane tolling and revenue recycling: discussion and limitations only.** Each needs data we don't have. Both papers use the static flow model. [Likely] In bottleneck models much of the gain comes from retiming trips, so say so in the limitations.
- "Destroys up to 90%" understates the worst case of single-lane tolling. [Certain] The 10% figure is from one study (Verhoef et al. 1996), and with perfectly inelastic demand a single-lane toll *lowers* welfare.

---

## 7. Data

### 7.1 Bento replication package (get this first)
- Harvard Dataverse, DOI 10.7910/DVN/VMJIRX, Stata format. It describes itself as the full dataset used in the report.
- Read it in Python with `pandas.read_stata` or `pyreadstat`.
- **Check whether it includes the route → station → crash crosswalk.** With 2026 as the analysis year, the routes must be re-queried from Google anyway, which costs money per request. The 2017 crosswalk is still useful for learning how they built it and for the 2017 validation run (§3 step 2).
  - [Likely] Google returns today's road network, which now matches the 2026 data.

### 7.2 Caltrans PeMS (manual download by Inderpal)
**Where:** log in at pems.dot.ca.gov, then go to **Tools → Data Clearinghouse** (`pems.dot.ca.gov/?dnode=Clearinghouse`). Set Type and District and submit. The home-page freeway/detector dropdown is for single-road charts only, not bulk data.

**District 7, 2026:**
1. **Station Hour, Jan–Sep 2026,** to match the CHP Incident months already downloaded. Add later months as they appear.
   - Keep only mainline rows (Lane Type = ML), which excludes HOV lanes.
   - Keep only rows with % Observed = 100. This is the closest match to "every detector reporting", since PeMS imputes missing detectors.
   - Per-lane density = Total Flow ÷ lanes ÷ Avg Speed, with lanes from the metadata.
   - [Likely] Drop per-lane flows above roughly 2,500 vph. Table 1's maximum of 5,173 per lane is physically impossible.
2. **Station Metadata, every version dated in 2026.**
   - It gives each station's lat/lon, freeway, direction, postmile, lanes, type and length.
   - Stations change during the year, so join each hour to the metadata version in force on that date.
   - [Certain] Only 17 Jul, 25 Aug and 24 Oct are in hand. The Jan–Jun versions are still needed, or Jan–Jun hours get joined to July stations.
3. **CHP Incidents, monthly, 2026.** Jan–Sep are in hand.
   - [Likely] The files are statewide; filter to D7 using the location fields.
   - [Likely] Filter to collisions using the CHP codes in the description field, e.g. 1179/1181/1182/1183 "Trfc Collision".
   - The files include start time and duration. Bento uses only the crash hour; using duration is a later improvement.

**Optional:** Station Day files, for spotting broken stations. **Skip:** Station Raw (30-second) and Station 5-Minute files.

**District 4:** the same three file types, 2026. [Guessing] Whether 2026 had enough Bay Area rain for the rain conditions is unknown. Count wet hours in NOAA data before designing around rain.

**After download:** check for duplicate and empty files, which are common with batch browser downloads.

### 7.3 Outside Caltrans
- **LODES (Census LEHD), California OD file.** [Likely] LODES lags several years, so 2026 isn't available; use the most recent year released and document it.
- **NOAA ISD-Lite hourly weather.** Bento's six LA stations are unnamed, so pick them and document the choice.
- **EIA weekly LA regular retail gasoline price.**
- **Freeway interchange locations,** to define the links used to drop own-crash station-hours. [Guessing] Build them from PeMS postmiles or Caltrans GIS layers; the paper doesn't say how.
- **Optional:** CHIPS (UC Davis, scraped from the CHP real-time feed) as an alternative crash source. PeMS undercounts incidents relative to SWITRS and CHIPS.

### 7.4 Data pitfalls
- [Likely] **Speed is usually estimated, not measured.** Most detectors are single loops, so speed is computed from flow and occupancy. Speed and density therefore share an input; the instrument protects against the resulting measurement error.
- [Guessing] **Reprocessed history.** Caltrans has reprocessed historical speeds before. Recent 2026 months may also be revised after download. Record download dates.
- **Avoid METR-LA and PEMS-BAY** (the ML benchmark datasets). [Likely] They contain speed only, no flow.

### 7.5 Storing large raw files
- [Certain] The GitHub web upload caps files at 25 MB. Git itself rejects files over 100 MB.
- **Station Hour files go in GitHub Releases, not in git history.** Upload them as assets on a release (tag `data-d7-2026`). Each asset can be up to 2 GB, and they don't count against the repo size or the LFS quota.
- Keep the files as downloaded (`.txt.gz`); don't unzip before uploading.
- Fetch into a session with `gh release download data-d7-2026 -R ipsanmoljj/urban_eco -D data/raw/pems/d7/station_hour/`.
- `data/raw/pems/*/station_hour/` is git-ignored.

---

## 8. Extension design (District 4)

1. **Instrument.** Use Bento's crash-on-alternate-route instrument. [Likely] It only works where real parallel freeway alternatives exist. Check first-stage strength before investing.
2. **Kink first.** Estimate the breakpoint separately where conditions differ. Rain lowers free-flow speed and capacity, so 21 vehicles/mile probably moves in wet hours.
3. **Two-hour-bracket elasticities,** Koch style.
4. **σ by density bins,** then test whether the hour brackets still matter once density is controlled for. This is the §1 test, and the actual contribution.
5. **Bracket-specific slope and breakpoint** of the kinked curve.
6. **Rain traps.**
   - Rain raises crash rates, so wet hours have different instrument compliers.
   - Cells get thin (crash × rain × above capacity).
   - Check the first-stage F in wet hours before committing.
7. **Welfare.**
   - Hourly, peak/off-peak and **true uniform** second-best tolls.
   - A demand-elasticity sensitivity range.
   - Handle σ ≥ 1 with Bento's queue treatment.

---

## 9. ML component (unresolved)

[Likely] As the design stands, the project has no real ML component. Koch's ML (DBSCAN/QuickBundles) can't run on PeMS. The two ML review papers, Mystakidis et al. (2025) and Attioui & Lahby (2025), were evaluated and dropped: they are surveys with no method to replicate. Attioui is mostly about classification, and classification labels are useless for taking a slope.

Options discussed for where ML could do real work:
- **Double/debiased ML with an instrument, or an instrumental causal forest,** to let σ vary across hour, weather and detector, instead of hand-picked brackets. [Likely] Both are in Python's EconML.
- **Learning the speed–density curve flexibly** instead of fixing a single AIC-chosen breakpoint at 21. Prior suggestion: Shi et al., physics-informed deep learning with a fundamental-diagram learner, arXiv 2106.03142.
- **Use regression slopes for MEC, not tree-model derivatives.**

**This is Inderpal's decision; ask.** The risk is that "ML" becomes decorative.

---

## 10. Open decisions (ask, don't assume)

1. **District 4 focus.** Stay rain-focused, or make D4 the main test of curve shift vs movement along the curve, with rain as one of the conditions? The second makes the stronger paper.
2. **The ML component** (§9): which option, if any.
3. **Toolchain.** Python only, or does Inderpal have Stata to run the original do-files directly? [Likely] In Python, `pyfixest` handles IV with high-dimensional fixed effects and multi-way clustering; `linearmodels` is an alternative.
4. **India.** Akbar et al. stays as a discussion section on why this can't yet be done for Delhi. Their finding is that Indian cities are slow mainly because of low uncongested speed, not congestion, which pushes back on the "price congestion" premise. If any Indian application is attempted:
   - Call simulated data **"synthetic" or "simulated", never "fabricated"**; that word means research misconduct.
   - Synthetic data is useful only for testing that the pipeline recovers a known σ and breakpoint, and for exploring the σ ≥ 1 blow-up. It tells you nothing about India.

---

## 11. Decided against (don't reopen without new information)

- **Replicating Parry's Table 2 directly.** It is at best a ratio exercise on someone else's inputs.
- **Mendeley "Traffic Congestion Prediction" data:** unclear source, and it only supports classification.
- **Kaggle "US Traffic Congestions 2016–2022"** (Moosavi): only for an optional side section on accident-driven congestion.
- **NYC taxi and other trajectory-like datasets:** a fleet is an unrepresentative slice of traffic, so there is no total density.
- **INRIX:** commercial. The trajectory-ML track only starts if trajectory data is obtained.
- **Merging Akbar et al. into the main analysis:** it would dilute both.
- **Using 2017 PeMS data as the main sample** (decided 25 Oct 2026): the analysis uses 2026. Bento's 2017 data is used only to validate code (§3 step 2). The Clearinghouse no longer offers years before 2026 anyway.

---

## 12. Suggested repo layout

```
data/raw/dataverse/      # Bento replication package, untouched
data/raw/pems/d7/        # Station Hour, Metadata, CHP Incidents (manual download)
data/raw/pems/d4/
data/raw/external/       # LODES, NOAA ISD-Lite, EIA gas prices
data/processed/
src/                     # cleaning, instrument construction, estimation, welfare
notebooks/               # exploration only
output/tables/  output/figures/
papers/                  # PDFs
```

Raw data is never edited in place. Every replication number goes in a table next to the paper's reported number, with a column explaining any gap.

---

## 13. Working with Inderpal

- He wants an advisor, not an assistant:
  - challenge assumptions first;
  - lead with uncomfortable truths;
  - no warm-up paragraphs;
  - hold a position under pushback unless given new information.
- Tag claims [Certain] / [Likely] / [Guessing]. If most of a reply is guessing, say so up front.
- Structure disagreement as: "I disagree because ___. Here's what I'd do instead: ___. The risk in your approach is ___."
- Avoid these phrases: "great question", "you're absolutely right", "that makes a lot of sense", "absolutely", "definitely".
- Casual, direct and concise. In prose he writes himself, use plain complete sentences, not corporate fragments.
