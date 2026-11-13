# 3 Hypothesis testing

The proposal set three hypotheses: **H-a** demand (young children) is spatially clustered; **H-b**
walking access and fees differ by neighbourhood socio-economic status; **H-c** children and poor
walking access cluster together. This stage tests them on the stage-1 tables (HDB blocks with children
0-6, the canonical October 2026 centre layer, the OSRM walking matrix) with Moran's I and LISA
(Lecture 8), planning-area regression and GWR, and, after H-c was rejected as posed, the supply-pressure
index that answers the prof's reframed question "where is the best place to start a new centre". Every
notebook is executed top to bottom with outputs saved; the shared helpers are in `src/bt4015/`
(`moran.py`, `regression.py`, `sfca.py`, `maps.py`, `spatial_weights.py`). Seeds are 4015 and
permutation counts are those of the original scripts. Daryl's three fee analyses were written against
the 2021 centre file; they now read the 2026 GeoPackage (team decision 2026-11-01) and the 2021 numbers
are kept below for comparison.

| Notebook | Hypothesis | Method | Inputs | Outputs | Runtime | Executed? |
|---|---|---|---|---|---|---|
| [3_01_fee_spatial_autocorrelation](3_01_fee_spatial_autocorrelation.ipynb) (Daryl) | H-b, fee side: do fees cluster? | Median listed fee per planning area and per subzone; global + local Moran's I, symmetric KNN-4 on area-weighted centroids, 999 permutations, BH q-values | `output/childcare_centres_2026.gpkg` layer `centres`; `data/MasterPlanSubZones_2019.geojson` | `output/spatial_autocorrelation_nursery_fee_planning_area_2026/` (2 CSV + 6 PNG + summary); subzone level shown inline only | 15 s | yes |
| [3_02_income_fee_regression](3_02_income_fee_regression.ipynb) (Daryl) | H-b: do fees track planning-area income? | OLS of median fee on estimated median household income (grouped-median interpolation); 49,999-permutation p for Pearson/Spearman; 20,000 paired bootstraps; Cook's distance | 3_01 planning-area CSV; `data/ResidentHouseholdsIncomebyPlanningArea.csv` | `output/household_income_nursery_fee_regression_2026/regression_summary.csv`, `planning_area_regression_data.csv`, `income_nursery_fee_regression.png` | 6 s | yes |
| [3_03_income_fee_gwr](3_03_income_fee_gwr.ipynb) (Daryl) | H-b: is the income-fee slope stationary? | Adaptive bi-square GWR, LOOCV bandwidth, local t-tests with BH, Monte Carlo stationarity test (999 coordinate randomisations), residual Moran (KNN-4) | as 3_02 plus the subzone GeoJSON | `output/gwr_income_nursery_fee_planning_area_2026/` (6 CSV/MD + 4 PNG) | 8 s | yes |
| [3_04_child_density_moran](3_04_child_density_moran.ipynb) (Kenneth) | H-a: is demand clustered? | Global + local Moran's I on children 0-6 per km2, 159 HDB subzones, KNN-4 on EPSG:3414 centroids, 999 permutations | `output/subzone_stats.csv`; subzone GeoJSON | `output/spatial_autocorrelation_child_population/` (CSV + 7 PNG + summary) | 8 s | yes |
| [3_05_hc_bivariate_lisa](3_05_hc_bivariate_lisa.ipynb) (Minh) | H-c as proposed | Bivariate Moran's I and local bivariate LISA (esda), child density vs lagged walk time and vs log supply, Queen contiguity (islands patched), 9,999 permutations | gpkg layer `subzone_stats` | `output/subzone_lisa_hc.csv`, `figures/hc_bivariate_moran.png` | 14 s | yes |
| [3_06_pressure_index_lisa](3_06_pressure_index_lisa.ipynb) (Minh) | H-c reframed: where do many children share few centres? | 2SFCA on the walk matrix (10-min binary, one unit per centre) with 15-min, full-day-only and planned variants; subzone aggregation; global + local Moran's I on log pressure (Queen, 9,999 permutations, min 100 children); cut-off sensitivity 0/50/100/200; Rook comparison | `large_data/walk_centres_time_min.parquet`, `walk_planned_time_min.parquet`; `output/hdb_access_children.csv`; centre gpkg; `output/hdb_blocks.gpkg` | `output/hdb_pressure_index.csv`, `centre_catchment_pools.csv`, `subzone_pressure.csv` + gpkg layer `subzone_pressure`, `weak_links_top15.csv`, `lisa_threshold_sensitivity.csv`; `figures/pressure_map.png`, `pressure_index_lisa.png`, `pressure_vs_fee.png`, `lisa_robustness.png` | 17 s | yes |
| [3_07_walking_access_by_ses](3_07_walking_access_by_ses.ipynb) (Minh) | H-b: walk time / fee / pressure by SES | Medians by planning-area income tercile and by 1-3-room-flat tercile; Spearman with p; Kruskal-Wallis | gpkg layer `subzone_pressure` (3_06); `output/subzone_stats.csv` | `figures/hb_access_by_ses.png` | 5 s | yes |
| [3_08_planned_centre_impact](3_08_planned_centre_impact.ipynb) (Minh) | Will ECDA's planned centres relieve the weak links? | Each of the 13 planned centres added alone to the 2SFCA: catchment pool and percentile, own-subzone pressure before/after, children benefiting; gap list of weak links with no planned centre within 10 min | the two parquets; `output/hdb_access_children.csv`; centre gpkg; 3_06's `subzone_pressure.csv`, `weak_links_top15.csv` | `output/planned_centre_impact.csv`, `planned_centre_gap.csv`; `figures/planned_centres_on_pressure.png`, `planned_centre_relief.png` | 5 s | yes |

## Results

- **H-a, demand clusters (3_04): supported.** Child density 0-6 has Moran's I = +0.187 (p = 0.001) across the 159 HDB subzones; the high-high cluster is the Punggol-Sengkang belt (Punggol Field, Punggol Town Centre, Northshore, Waterway East, Matilda, Rivervale, Sengkang Town Centre, Anchorvale). No subzone survives the FDR correction, so the local result is exploratory.
- **H-b, walking access by SES (3_07): not supported.** Median walk to the nearest centre is 3.2 / 3.3 / 2.9 min across low / mid / high income terciles and 2.9 / 3.2 / 3.2 across 1-3-room-flat terciles; Spearman with income -0.16 (p = 0.06), with the 1-3-room share +0.23 (p = 0.007), differences of about 20 seconds that run the wrong way for income. Listed fees are S$650 in every tercile (rho -0.04 and -0.05).
- **H-b, fees track income between planning areas (3_01-3_03): supported.** Fees cluster strongly (planning-area I = 0.511, p = 0.001; subzone I = 0.446); the central high-fee areas (Newton, Orchard, River Valley, Tanglin, Downtown Core, Museum, Singapore River, Marina South) are one high-high cluster. OLS: +S$113.9 per S$1,000 of median income (bootstrap 95% CI 70.9-142.1), R2 = 0.626, Pearson r = 0.79 (permutation p = 0.00006); most HDB towns sit at the anchor-operator fee, so the gradient is carried by the affluent central areas (dropping the most influential area, by Cook's distance, leaves +S$103.3). GWR (14 neighbours by LOOCV) lifts R2 to 0.861 and removes the positive residual autocorrelation (OLS residual I = 0.27, p = 0.009; GWR -0.21), but the Monte Carlo test does not reject a stationary slope (p = 0.345): one island-wide slope is adequate.
- **H-c as proposed, children cluster where walking is poor (3_05): rejected.** Bivariate Moran's I of child density against neighbouring walk time is -0.191 (p = 0.0002); only two subzones (Tiong Bahru, Tiong Bahru Station) fall in the high-density / long-walk quadrant. Dense-child subzones sit among well-served ones.
- **H-c reframed, supply pressure clusters (3_06): supported.** Children per reachable centre (10-min walk) has Moran's I = +0.176 (p = 0.002) over the 140 HDB subzones with at least 100 children 0-6; the high-high cluster has 10 subzones: Garden, Plantation, Park (Tengah), Brickworks, Hong Kah North (Bukit Batok), Yuhua West (Jurong East), Matilda, Punggol Town Centre, Waterway East (Punggol), Woodgrove (Woodlands). Seven are high-high at every cut-off from 50 to 200 children; Rook contiguity gives I = +0.21 with 8 high-high (Jelebu in, Matilda / Waterway East / Yuhua West out). The index is robust to the catchment (Spearman with the 15-min variant 0.86) and to excluding kindergartens (0.98). Highest single value: Tampines North, 596 children per reachable centre. All high-pressure subzones sit at the S$610-650 anchor fee, so the barrier is capacity, not price.
- **Planned-centre gap (3_08).** The Tampines North centre has the largest catchment (2,750 children, 98th percentile of existing centres) yet cuts that subzone's pressure by only 8%; Garden and Plantation gain 16% and 10%. 16 of the 20 weak-link subzones (top 15 or high-high) have no planned centre within 10 minutes of their children, among them Park, Brickworks, Matilda, Sembawang East, Woodlands West and Yishun East.

## Fee analyses: 2021 file versus 2026 canonical layer

Daryl's original scripts read `data/ChildCareServices_2021.geojson`; since his 11 Nov re-run on `main`, his scripts and these notebooks both read `output/childcare_centres_2026.gpkg` and write to the same `_2026` output folders (his re-run reproduces the 2026 column below). The notebooks read it (layer `centres`, reprojected to EPSG:4326 for his loader; the one S$0 fee, RC1909, is set to null). The method is unchanged.

| Statistic | 2021 (scripts) | 2026 (notebooks) |
|---|---:|---:|
| Centres with a usable fee | 1,363 | 1,586 |
| Planning areas with a fee / subzones with a fee | 38 / 210 | 42 / 232 |
| Planning-area Moran's I (p) | 0.298 (0.003) | 0.511 (0.001) |
| Subzone Moran's I (p) | 0.376 (0.001) | 0.446 (0.001) |
| Planning areas matched to income | 30 | 30 |
| OLS slope, S$ per S$1,000 income (R2) | 107.1 (0.721) | 113.9 (0.626) |
| Slope bootstrap 95% CI | 63.0-138.6 | 70.9-142.1 |
| GWR bandwidth (LOOCV) | 14 neighbours | 14 neighbours |
| GWR R2 (AICc gain over OLS) | 0.879 (5.6) | 0.861 (10.2) |
| Income-slope stationarity p | 0.164 | 0.345 |

The Theil-Sen slope (7.4 on the 2021 file, 0.0 on the 2026 layer) was dropped from the outputs on 13 Nov, following Daryl's script update: with most areas at the S$650 anchor fee the median pairwise slope is degenerate and read as "no relationship" beside a significant OLS.

## Run order

From this folder, `jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=3600 <name>.ipynb`
(Python 3.12 kernel `python3`). 3_02 and 3_03 read the planning-area CSV written by 3_01; 3_07 reads
the gpkg layer `subzone_pressure` and 3_08 the tables written by 3_06, so run the notebooks in
numeric order. With the committed outputs present any single notebook can also be run on its own. Total runtime about 80 s. 3_06 writes the layer `subzone_pressure` into the shared
`output/hdb_blocks.gpkg`; do not run it while another notebook is writing that file.
