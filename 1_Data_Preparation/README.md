# 1. Data preparation

This stage turns the public downloads in `data/` into the tables every analysis reads from `output/`:
HDB block polygons joined to their attributes and grouped into neighbourhoods, children aged 0–9
placed on each block from SingStat's subzone counts, the Oct-2026 childcare centre layer with fees
and a QA of the rows left out of it, walking-time matrices from every block to every centre on a
local OSRM foot network, and the integrated block and subzone tables. Each notebook was executed
top to bottom on 2026-11-10 (Python 3.12, `jupyter nbconvert --execute`); every output it writes
was checked against the committed file and reproduced it, except where noted below. Shared helpers
live in `src/bt4015/` (`paths.py`, `fees.py`, `osrm.py`, `spatial_weights.py`). Superseded and
exploratory work (the clustering comparison, the floor-area child allocation, the OneMap-only
geocoding, the bus-stop variance check) is in [`../0_Data_Exploration/`](../0_Data_Exploration/).

| Notebook | What it does | Inputs | Outputs | Runtime | Executed? |
|---|---|---|---|---|---|
| [1_01_load_subzones](1_01_load_subzones.ipynb) | Master Plan 2019 subzones to EPSG:3414 with `area_km2` | `data/MasterPlanSubZones_2019.geojson` | `output/hdb_blocks.gpkg` layer `subzones` (332) | 2 s | yes |
| [1_02_join_hdb_blocks](1_02_join_hdb_blocks.ipynb) | Joins HDB block polygons to HDB Property Information by decoding the LTA road code and abbreviating street names; two fallback passes; manual review of four blocks; how the 156 unmatched blocks were handled | `data/HDBExistingBuilding_2026.geojson`, `data/HDBPropertyInformation_2026.csv`, `data/LTARoadNameCode_2019.xlsx` | `output/hdb_blocks.gpkg` layer `hdb_blocks` (13,436), `output/hdb_join_review.csv` (120) | 6 s | yes |
| [1_03_cluster_hdb_blocks](1_03_cluster_hdb_blocks.ipynb) | Residential block centroids tagged with subzone; complete-linkage clusters, 300 m max diameter, per subzone; map colouring | `hdb_blocks.gpkg` layers `hdb_blocks`, `subzones` | `hdb_blocks.gpkg` layers `hdb_points` (10,769), `hdb_clusters` (1,403), `hdb_cluster_hulls` (1,403) | 5 s | yes |
| [1_04_assign_child_population](1_04_assign_child_population.ipynb) | Children 0–4 and 5–9 per block by flat type (dasymetric split of SingStat subzone counts) | `hdb_blocks.gpkg`, `data/subzone_child_population_2026.xlsx`, `data/MasterPlanSubZones_2019.geojson` | `output/hdb_blocks_children_final.gpkg` (10,769), `output/child_population_unassigned.csv` (0) | 7 s | yes |
| [1_05_build_childcare_centres](1_05_build_childcare_centres.ipynb) | Canonical 2026 centre layer: ECDA list located via 2021 points and the OneMap cache, Nursery Full Day/SC fee by centre code (`bt4015.fees`), subzone attached | `data/CentreAttributes_2026.csv`, `data/ListingofCentreServices.csv`, `data/ChildCareServices_2021.geojson`, `output/onemap_geocode_cache.csv` | `output/childcare_centres_2026.gpkg` layer `centres` (1,796), `output/childcare_centres_2026_review.csv` (420) | 5 s | yes, no network calls (all 305 lookups from the cache) |
| [1_06_build_walk_matrix](1_06_build_walk_matrix.ipynb) | Walking-time matrices block → centres / planned / 2021 centres / MRT exits via OSRM (`bt4015.osrm`), kept behind `REBUILD_MATRIX = False`; per-block summary rebuilt from the saved parquet files | `hdb_blocks.gpkg` layer `hdb_points`, `childcare_centres_2026.gpkg`, `data/MRTStationExits_2026.geojson`, `data/ChildCareServices_2021.geojson`, `large_data/walk_*.parquet` | `output/hdb_walk_access.csv` (10,769); `large_data/walk_<set>_{time_min,dist_m}.parquet` only when rebuilding | 6 s (summary); ~1.7 h for a full rebuild of `centres` | yes (summary only; matrices not rebuilt) |
| [1_07_build_subzone_stats](1_07_build_subzone_stats.ipynb) | Block table (access + children + 0–6 demand band) and subzone table (children, units, centres, access shares, densities, income) | `hdb_walk_access.csv`, `hdb_blocks.gpkg`, `hdb_blocks_children_final.gpkg`, `childcare_centres_2026.gpkg`, `data/SubzoneSingleYearAge_2026.csv`, `output/resident-household-income_regression/planning_area_median_household_income_range.csv` | `output/hdb_access_children.csv` (10,769), `output/subzone_stats.csv` (332), `hdb_blocks.gpkg` layer `subzone_stats` (332) | 4 s | yes |
| [1_08_excluded_centres_qa](1_08_excluded_centres_qa.ipynb) | The 80 ECDA rows left out: located and classified; verified by hand (planned / duplicate / operating-but-absent / unverified); spatial missingness test (9,999 permutations); sensitivity of subzone supply to the unverified records | `data/CentreAttributes_2026.csv`, `childcare_centres_2026.gpkg`, `onemap_geocode_cache.csv`; read-only `output/subzone_lisa_hc.csv` (stage 2) and `output/subzone_stats.csv` (1_07) | `output/excluded_centres_2026.csv` (80), `output/excluded_centres_verification_2026.csv` (80), `childcare_centres_2026.gpkg` layer `planned` (13), `output/excluded_centres_missingness_by_area.csv`, `output/childcare_centres_2026_sensitivity.gpkg` (layers `plausible` 1,806, `upper_bound` 1,815), `output/unverified_centres_sensitivity_by_subzone.csv` | 9 s | yes, no network calls (3 no-result queries treated as such) |

## Key numbers

- **13,436** HDB block polygons; **98.8%** matched to HDB Property Information on the first pass
  (13,280), **99.1%** after the fallback passes and manual review (13,319); 117 excluded (116 small
  Pasir Ris landed structures and one community club), 3 included with imputed units.
- **10,769** residential blocks with dwelling units (1,172,065 units), in 159 subzones; **1,403**
  neighbourhood clusters of at most 300 m (median 7 blocks, 788 flats).
- **259,910** HDB children aged 0–9 (122,640 aged 0–4, 137,270 aged 5–9), all assigned, none lost;
  **176,409** children 0–6 (67.9% of 0–9) with the per-subzone share of ages 5–6 (0.30–0.53; 55 blocks
  fall back to the flat 0.40; flat-40 variant 177,548).
- **1,796** centres operating Oct 2026 (CC 1,467, KN 183, DS 84, EYC-DS 57, EYC 5), all located
  and inside a subzone; **1,587** with a listed Nursery Full Day/SC fee (median S$650); 193 with no
  such listing, 15 with conflicting fees, 1 verified addition without a centre code.
- Of the 80 excluded ECDA rows: 40 possibly missing after location, of which 14 planned (**13**
  with a location form layer `planned`), 1 operating and added back, 23 unverified (19 located).
- Walk matrix: **10,769 × 1,796** (centres), 10,769 × 13 (planned), 10,769 × 1,925 (2021 centres),
  10,769 × 613 (MRT exits). Median walk to the nearest centre 3.1 min (p90 6.0); 3 blocks have no
  centre within 15 min; 2,350 blocks are more than 15 min from an MRT exit; median 9.5 centres per
  1,000 children 0–6 across HDB subzones.

## Decisions recorded here

- Street-name abbreviation table and two fallback passes for the HDB join (1_02, §2–4); manual
  decisions on four unmatched blocks (1_02, §6 and §9).
- Complete-linkage clustering, 300 m, per subzone (1_03; evidence in
  `../0_Data_Exploration/clustering_experiment.ipynb`, `docs/clustering_decision.md`).
- Children allocated by flat type, not floor-area band (1_04; superseded method in
  `../0_Data_Exploration/assign_child_population_floor_area.ipynb`).
- Canonical centre layer keeps all service models; `data/Centres_2026.geojson` is deprecated (1_05;
  `docs/decisions.md` 2026-11-01).
- Walk-matrix origins are blocks, not clusters; bus stops are not a destination set (1_06;
  evidence in `../0_Data_Exploration/bus_stop_variance_check.ipynb`, `docs/decisions.md` 2026-10-30).
- Demand band 0–6 with the per-subzone share of ages 5–6, flat 40% as robustness (1_07;
  `docs/decisions.md` 2026-11-02).

## Run order

1_01 → 1_02 → … → 1_08, i.e. numeric order. Each notebook reads the outputs of the
earlier ones; 1_08 comes last because its sensitivity section reads `output/subzone_stats.csv` (1_07)
and both it and its first section read `output/subzone_lisa_hc.csv` from the ESDA stage (committed
copies are fine). From this folder:

```
python3 -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=3600 <notebook>.ipynb
```

Services: 1_05 and 1_08 need no network as long as `output/onemap_geocode_cache.csv` covers every
query (a new centre row would stop the notebook with a message; set `ALLOW_ONEMAP = True` to query
OneMap). 1_06 needs OSRM on `http://localhost:5001` only when `REBUILD_MATRIX = True`; the saved
matrices are in the git-ignored `large_data/` (ask Minh / Dropbox).

## Changes from the original scripts

The teammates' logic is unchanged. Added: numbered comments, printed counts, and the paths through
`bt4015.paths` instead of paths relative to the repo root or `__file__`. Dated `# changed 2026-11-10`
comments mark the only behavioural additions: the `ALLOW_ONEMAP` guard in 1_05 and 1_08 (an
uncached query raises in 1_05 and counts as "no result" in 1_08 instead of silently calling OneMap),
and `REBUILD_MATRIX` in 1_06 (the original script always queried OSRM). `scripts/join_childcare_fees.py`
became `src/bt4015/fees.py` and the OSRM helpers of `scripts/build_walk_matrix.py` became
`src/bt4015/osrm.py`, both with docstrings and unchanged logic.

Two committed files were refreshed by the rerun; everything else reproduced byte-for-byte or
value-for-value. `output/clustering_experiment.csv` had been run in October on the then-10,741
residential blocks; on the current 10,769 blocks complete_300m gives 1,403 clusters (was 1,400),
matching the `hdb_clusters` layer, with the same ranking and conclusions. In
`output/excluded_centres_2026.csv` only the six context columns merged from `output/subzone_lisa_hc.csv`
(`children_0_9`, `centres_n`, `centres_per_1000_children`, `bv_*`) changed: the committed audit file
(2026-11-01 17:38) predates the LISA rerun on the canonical centre layer (23:13 the same day). The
audit's own columns are unchanged and `excluded_centres_verification_2026.csv` is byte-identical.
