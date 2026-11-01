# Decisions log

Settled methodological decisions, so they are not re-opened by accident. Newest first. Each entry
says what was decided, the evidence, and who confirmed it. Open questions stay in the project
CLAUDE.md "Open decisions" list until they land here.

## 2026-11-02 — Supply-pressure index: 10-minute binary catchment, one unit per centre

**Decision.** The reframed H-c measure is a two-step floating catchment (2SFCA) index: for each
centre, children 0–6 in HDB blocks within a 10-minute walk form its demand pool; for each block, the
sum of 1/pool over centres within 10 minutes is its supply ratio, and its inverse (children per
reachable centre) is the pressure. Every centre counts as one unit, since capacity is not used
(proposal). Sensitivities: 15-minute catchment; full-day supply only (kindergartens excluded);
ECDA's 13 planned centres added ("future"). Local Moran's I (Lecture 8) on subzone pressure gives
the weak-link clusters. **Decided by** Minh, 2026-11-02, after the prof's 30 Oct framing ("where is
the best place to start a new centre"). Validation uses the planned-centre layer and external
policy references; the ECDA listing's vacancy columns are empty for every centre, so vacancy cannot
be used. Limitation: demand pool is HDB children only.

## 2026-11-02 — Ages 5–6 counted with the per-subzone share, flat 40% as robustness

**Decision.** `child_0_6 = child_0_4 + share_5_6 × child_5_9`, where `share_5_6` is the subzone's
share of ages 5–6 within 5–9 from the SingStat single-year table (`scripts/build_subzone_stats.py`).
Subzones with fewer than 100 residents aged 5–9 (10 of 159 HDB subzones; SingStat rounds to 10) fall
back to the approved flat 0.40. Range across the rest: 0.30–0.53. `child_0_6_flat40` carries the
flat rule for a robustness check. **Decided by** Minh, 2026-11-02.

## 2026-11-01 — Canonical centre layer is `output/childcare_centres_2026.gpkg`; all service models are supply

**Decision.** The team's centre dataset is Jessie's `output/childcare_centres_2026.gpkg`, layer
`centres` (1,796 centres operating Oct 2026, fees joined by `centre_code`, subzone attached). It
replaces both the 2021 GeoJSON and Minh's `data/Centres_2026.geojson` (1,651, CC + KN only; now
deprecated, kept only until Karis and Daryl switch paths). For supply and accessibility all service
models count (CC, DS, EYC, EYC-DS and KN); the full-day-only variant drops the 183 KN as a
sensitivity, which also answers the prof's kindergarten-fee question without a fee proxy.
**Evidence** for keeping DS/EYC: all 145 carry a listed full-day Nursery fee (the PCF anchor-operator
rate), and leaving them out had understated supply in Fernvale, Yishun, Punggol and Tampines East
(children with no centre within 10 min: 612 vs 334). Walk-matrix id = `centre_code`, with `tp_code`
for the one verified addition. **Decided by** Jessie (PR #12) and Minh, 2026-11-01.

## 2026-10-30 — Demand age band is 0–4 plus 40% of 5–9 (children below 7)

**Decision.** Childcare demand counts children aged 0–6. From the 5-year SingStat bands this is
ages 0–4 plus 40% of ages 5–9. **Confirmed by** the prof on 2026-10-30. The SingStat single-year
table (`data/SubzoneSingleYearAge_2026.csv`) gives the exact per-subzone share of 5–6 within 5–9
(33–44%, national 38.8%), which may be used instead of the flat 40%; whichever is used, the other is
a one-line robustness check.

## 2026-10-30 — Bus stops are not used; MRT exit walk time is kept as a covariate

**Decision.** Walking time to the nearest bus stop is **not** computed for the full block set and is
**not** a covariate in any model. Walking time to the nearest MRT exit **is** kept, as an explanatory
variable for fees (H-b) and as a transit-connectivity control. Neither is combined with
walking time to a centre: the accessibility measure stays "walk from block to nearest centre".

**Confirmed by** the prof at the consultation on 2026-10-30, as proposed in the consultation brief.

**Evidence** (`scripts/check_bus_stop_variance.py`; 500-block random sample, seed 4015, routed on
the same OSRM foot network as the centre matrix):

| Walk to nearest … | p10 | median | p90 | p99 | max | share > 5 min | share > 10 min |
|---|---:|---:|---:|---:|---:|---:|---:|
| bus stop | 1.3 min | 2.8 min | 4.7 min | 6.6 min | 8.9 min | 7% | 0% |
| MRT exit | 3.7 min | 9.0 min | 19.6 min | 31.5 min | 37.8 min | 81% | 44% |

(The consultation brief quoted 2.7 / 9.2 min and 45% from an earlier draw of the same size; the
difference is sampling noise.)

Straight-line distance for all 10,769 blocks tells the same story: median 107 m to a bus stop,
90th percentile 187 m, farthest block 424 m.

**Why.** Every HDB block sits within one to six minutes of a bus stop, so the variable has
essentially no variance across estates and cannot explain differences in fees or supply. MRT
proximity ranges from under four minutes to over an hour and can. Running the full
10,769 × 5,205 bus-stop matrix (~45 min) would only have sharpened decimals.

**If it is ever revisited.** The one way bus access could carry information is service frequency
(buses per hour at the nearest stop), not stop proximity. That needs LTA DataMall route and
timetable data, roughly a week of work, and was judged out of scope.

## Earlier decisions (documented elsewhere)

| Date | Decision | Where |
|---|---|---|
| 2026-10-28 | Canonical centre layer is the Oct-2026 ECDA listing, geocoded; the 2021 GeoJSON is stale (292 active centres missing, 541 closed). Superseded by the 2026-11-01 entry above: Jessie's layer is canonical. | README "Walking access" |
| 2026-10-26 | Walk matrix origins are individual HDB **blocks**, not clusters (prof). Clusters kept for mapping only. | `docs/work_split_2026-10-26.md` |
| 2026-10-22 | Child allocation to blocks by **flat type** (Jessie), not floor-area bands (Kenneth). | `output/hdb_unresolved_blocks_handling.md` |
| 2026-10-18 | HDB clustering: complete-linkage, 300 m max diameter, per subzone. | `docs/clustering_decision.md` |
| proposal | Centre capacity is not used as a variable. | proposal |
