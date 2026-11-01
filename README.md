# BT4015group2

Proposal document:
https://docs.google.com/document/d/1D4b8GMSYMx0BUsGKTX3J_nI62QtSSxzxvbTxfGdXYas/edit?usp=sharing

Data that needs to be self-downloaded:
HDB Existing Building https://data.gov.sg/datasets/d_16b157c52ed637edd6ba1232e026258d/view


## HDB block join (baseline, step 1 of preprocessing)

`scripts/join_hdb_nationwide.py` joins the HDB block polygons to the HDB Property
Information attributes (floors, dwelling units, flat-type mix, function flags) for all
13,436 blocks. The two datasets have no common key: polygons use an LTA road code
(`ST_COD`), the CSV uses an abbreviated street name. The script decodes the road code
with LTA's lookup table, rewrites suffixes to HDB's abbreviations (AVENUE→AVE, SOUTH→STH …)
and joins on block + street. A fallback pass resolves 36 more blocks (alternate street
spellings; road codes newer than the LTA table, matched by block number within the postal
sector's town). Match rate: 13,316 / 13,436 (99.1%).

```
python scripts/join_hdb_nationwide.py
```

| Path | What |
|---|---|
| `data/HDBExistingBuilding_2026.geojson` | HDB Existing Building, data.gov.sg `d_16b157c52ed637edd6ba1232e026258d`, version 2026-06-21 |
| `data/HDBPropertyInformation_2026.csv` | HDB Property Information, data.gov.sg `d_17f5382f26140b1fdae0ba2ef6239d2f`, version 2026-10-08 |
| `data/LTARoadNameCode_2019.xlsx` | LTA DataMall road-code → road-name lookup (sheet `GISDomainData`) |
| `output/hdb_blocks.gpkg` | layer `hdb_blocks`, EPSG:3414, all blocks with attributes + `footprint_m2`, `gfa_m2`, `is_residential`, `match_status` |
| `output/hdb_join_review.csv` | the 120 blocks not in HDB Property Information 2026: 117 excluded (116 small Pasir Ris structures + a community club) and 3 included with units imputed from same-street neighbours (`match_status = imputed`, `review_flag`) |
| `output/hdb_unresolved_blocks_handling.md` | how the 156 unmatched blocks were handled: evidence, decisions, imputation method, effect on child counts |
| `data/subzone_child_population_2026.xlsx` | SingStat Resident Population by Subzone, Age Group and Type of Dwelling, June 2026 (`respopagesextod2026e.xlsx`) |
| `output/hdb_blocks_children_final.gpkg` | from `scripts/assign_child_population_fillnull.py`: residential blocks with `child_0_4`, `child_5_9`, `child_pop_0_9`, split by flat type |
| `data/ChildCareServices_2021.geojson` | Child Care Services, data.gov.sg `d_5d668e3f544335f8028f546827b773b4`, version 2026-04-18 | 
| `data/MasterPlanSubZones_2019.geojson` | Master Plan 2019 Subzone Boundary (No Sea) (GEOJSON), data.gov.sg `d_8594ae9ff96d0c708bc2af633048edfb`, version 2025-12-03 | 
| `large_data/singapore_only.osm.pbf` | OSRM Network Street Data, https://download.geofabrik.de/asia/malaysia-singapore-brunei.html | 
| `large_data/Singapore.poly` | Singapore Polygon, https://download.geofabrik.de/asia/malaysia-singapore-brunei.html |


Use `is_residential` to drop carparks / markets / pavilions before computing demand.
`gfa_m2` = footprint area × `max_floor_lvl` is the team's agreed weight for allocating
young-child population to blocks; `total_dwelling_units` is also available for a
robustness check. Requires `geopandas`, `pyogrio`, `pandas`, `openpyxl`.

## HDB neighbourhood clusters (preprocessing steps 2–4)

Residential blocks are grouped into walkable neighbourhoods so that one walk time per cluster
stands in for all its blocks. Method: complete-linkage agglomerative clustering with a **300 m
maximum diameter**, run separately inside each subzone. See `docs/clustering_decision.md` for
the options compared (DBSCAN vs complete linkage), the evidence, and why 300 m;
`figures/clustering_comparison.png` shows the difference on Tampines East.

```
python scripts/load_subzones.py        # adds layer "subzones" to output/hdb_blocks.gpkg
python scripts/cluster_hdb_blocks.py   # adds hdb_points, hdb_clusters, hdb_cluster_hulls
python scripts/experiment_clustering.py  # optional: re-run the method comparison
```

| Layer in `output/hdb_blocks.gpkg` | What |
|---|---|
| `subzones` | MP2019 subzones, EPSG:3414, `SUBZONE_C/N`, `PLN_AREA_N`, `area_km2` |
| `hdb_points` | 10,741 residential block centroids with subzone, `cluster_id`, flat counts, `gfa_m2` |
| `hdb_clusters` | 1,400 cluster centroids (weighted by dwelling units): `n_blocks`, `dwelling_units`, `gfa_m2`, `diameter_m` |
| `hdb_cluster_hulls` | convex hull per cluster, for maps and visual QA only |

`dwelling_units` and `gfa_m2` are sums over the cluster's blocks; `diameter_m` is the largest
block-to-block distance (always ≤ 300 m). All three layers carry `color_idx` (0–7, neighbouring
clusters never share a value): in QGIS use Categorized symbology on `color_idx`.

## Walking access (OSRM) and the integrated subzone table

Local OSRM (installed via Homebrew, no Docker) with the foot profile on a Singapore clip of the
Geofabrik extract. Full origin × destination walking-time tables for all 10,769 residential HDB
blocks are stored as parquet in git-ignored `large_data/` (ask Minh / Dropbox); the committable
per-block and per-subzone summaries are in `output/`.

```
brew install osrm-backend osmium-tool
osmium extract --bbox 103.55,1.15,104.15,1.50 -o large_data/singapore.osm.pbf large_data/malaysia-singapore-brunei-latest.osm.pbf
osrm-extract -p "$(brew --prefix osrm-backend)/share/osrm/profiles/foot.lua" large_data/singapore.osm.pbf
osrm-partition large_data/singapore.osrm && osrm-customize large_data/singapore.osrm
osrm-routed --algorithm mld --max-table-size 10000 -p 5001 large_data/singapore.osrm &
python scripts/build_walk_matrix.py --sets centres,planned   # -> large_data/walk_<set>_{time_min,dist_m}.parquet (~1.7 h for centres)
python scripts/summarise_walk_matrix.py     # rebuild hdb_walk_access.csv from parquet without OSRM
python scripts/build_subzone_stats.py       # -> output/hdb_access_children.csv, output/subzone_stats.csv, gpkg layer subzone_stats
```

| Path | What |
|---|---|
| `output/childcare_centres_2026.gpkg`, layer `centres` | **Canonical centre layer (Jessie, PR #12).** 1,796 centres operating Oct 2026, all service models (CC 1,467, KN 183, DS 84, EYC-DS 57, EYC 5), fees joined by `centre_code`, subzone attached. Matrix column id = `centre_code`, or `tp_code` for the one verified addition without a code. Layer `planned` = ECDA's 13 upcoming centres. See `output/childcare_centres_2026_handling.md`. |
| `data/Centres_2026.geojson` | **Deprecated** (1,651 CC + KN only; missed 145 DS/EYC full-day centres). Kept until Karis's notebook and Daryl's GWR switch to the gpkg; do not use for new work. |
| `data/MRTStationExits_2026.geojson`, `data/BusStops_2026.geojson` | LTA MRT exits (613) and bus stops (5,205), data.gov.sg, Oct 2026 |
| `output/hdb_walk_access.csv` | per block: nearest walk minutes / metres / id and counts within 10 and 15 min, for `centres` (canonical 2026), `centres2021` (comparison), `mrt_exits` and `planned`. **Bus stops deliberately not run** (prof-confirmed 2026-10-30): every block is within 1–6 min of a stop, so the variable has no spread. Evidence: `scripts/check_bus_stop_variance.py`, decision in `docs/decisions.md`. |
| `output/hdb_access_children.csv` | the above joined to Jessie's children 0–4 / 5–9 and flat-type mix, plus the demand band **`child_0_6` = child_0_4 + share_5_6 × child_5_9** (prof-approved 30 Oct; `share_5_6` = the subzone's share of ages 5–6 within 5–9 from `data/SubzoneSingleYearAge_2026.csv`, 0.30–0.53, flat 0.40 where the subzone has < 100 residents aged 5–9) and `child_0_6_flat40` for robustness. National total 176,409 children 0–6 (67.9% of 0–9). |
| `output/subzone_stats.csv` + gpkg layer `subzone_stats` | per subzone: children 0–4 / 5–9 / 0–9 / 0–6, dwelling units, % 1–3 room, centres in polygon (`centres_n`, `_cc`, `_kn`, `_fullday`), centres per 1,000 children (0–9 legacy and `_0_6`), centre and child density, nearest walk time and shares within 10 / 15 min weighted by children 0–6, MRT walk time, planning-area median income |

Headline (1,796 canonical centres): median walk from an HDB block to the nearest centre 3.1 min (p90 6.0);
only 3 blocks have no centre within 15 min; 2,350 blocks are more than 15 min from an MRT exit.
Walking access to *a* centre is near-universal, so the discriminating measures are supply per child
(`centres_per_1000_children_0_6`, median 9.5 across HDB subzones) and the walk-time distribution,
not a binary "has access". Three unreachable destinations (two centres and the MRT exit inside Changi
Airport) are expected: the airport is cut off from the public footpath network.

## Supply-pressure index (reframed H-c) and ECDA's planned centres

H-c as proposed (children cluster where walkability is poor) is rejected: walking access to *a* centre
is near-universal. The question the prof set on 30 Oct is "where is the best place to start a new
centre", so the measure is **supply pressure**: how many children share each reachable centre.
Decisions and evidence: `docs/decisions.md`.

```
python scripts/pressure_index.py            # -> output/hdb_pressure_index.csv, subzone_pressure.csv (+ gpkg layer), weak_links_top15.csv, centre_catchment_pools.csv
python scripts/planned_centre_impact.py     # -> output/planned_centre_impact.csv, planned_centre_gap.csv
python scripts/make_pressure_figures.py     # -> figures/pressure_index_lisa.png, pressure_vs_fee.png, planned_centres_on_pressure.png
```

**Method (two-step floating catchment, 2SFCA, 10-min walk, binary).** Step 1: each centre's demand
pool = children 0–6 in HDB blocks within 10 min; its supply ratio = 1 / pool (one unit per centre,
capacity not used). Step 2: each block's supply = sum of the ratios of centres within 10 min;
**pressure = 1 / supply = children per reachable centre**. Subzone value = children-weighted mean.
Variants in the same tables: `s15` (15-min catchment, rank correlation 0.86 with base), `fullday`
(183 kindergartens excluded, 0.98), `future` (plus the 13 planned centres). Spatial clustering:
global and local Moran's I on log pressure (Lecture 8), Queen contiguity with islands attached to
the nearest neighbour (`scripts/spatial_weights.py`), 9,999 permutations, 140 HDB subzones with
≥ 100 children 0–6.

**Results.** Global Moran's I = +0.18 (p = 0.002): pressure clusters. The **high-high cluster has
10 subzones**: Garden, Plantation, Park (Tengah); Brickworks (Bukit Batok); Yuhua West and Hong Kah
North (Jurong); Matilda, Punggol Town Centre, Waterway East (Punggol); Woodgrove (Woodlands).
Highest single value: Tampines North, 596 children 0–6 per reachable centre (6,838 children, 10
centres) against a median of about 110. Pressure is driven by new-town demand, not fees: the
high-pressure subzones all sit at the S$610 anchor-operator fee (`figures/pressure_vs_fee.png`), so
the barrier there is capacity, not affordability.

**Planned centres.** Of ECDA's 13 upcoming centres, the Tampines North one has the largest
catchment (2,750 children, 98th percentile of existing centres) and cuts that subzone's pressure
by 8%; the Garden and Plantation (Tengah) ones cut theirs by 16% and 10%. But **16 of the 20
weak-link subzones (top 15 or HH) have no planned centre within 10 min of their children**,
including Park, Brickworks, Matilda, Sembawang East, Woodlands West and Yishun East
(`output/planned_centre_gap.csv`). Limitation: the demand pool is HDB children only, so centres
beside private estates look under-pressured; the ECDA listing's vacancy columns are empty, so
validation uses the planned layer and external references rather than vacancies.
