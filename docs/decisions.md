# Decisions log

Settled methodological decisions, so they are not re-opened by accident. Newest first. Each entry
says what was decided, the evidence, and who confirmed it. Open questions stay in the project
CLAUDE.md "Open decisions" list until they land here.

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
| 2026-10-28 | Canonical centre layer is the Oct-2026 ECDA listing, geocoded; the 2021 GeoJSON is stale (292 active centres missing, 541 closed). Which of the two 2026 builds (Minh `data/Centres_2026.geojson`, Jessie `output/childcare_centres_2026.gpkg`) is adopted is still to be settled; they share 1,650 codes with identical coordinates. | README "Walking access" |
| 2026-10-26 | Walk matrix origins are individual HDB **blocks**, not clusters (prof). Clusters kept for mapping only. | `docs/work_split_2026-10-26.md` |
| 2026-10-22 | Child allocation to blocks by **flat type** (Jessie), not floor-area bands (Kenneth). | `output/hdb_unresolved_blocks_handling.md` |
| 2026-10-18 | HDB clustering: complete-linkage, 300 m max diameter, per subzone. | `docs/clustering_decision.md` |
| proposal | Centre capacity is not used as a variable. | proposal |
