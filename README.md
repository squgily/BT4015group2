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
python scripts/geocode_centres_2026.py      # -> data/Centres_2026.geojson (canonical centre layer)
python scripts/build_walk_matrix.py         # -> large_data/walk_<set>_{time_min,dist_m}.parquet + output/hdb_walk_access.csv
python scripts/summarise_walk_matrix.py     # rebuild hdb_walk_access.csv from parquet without OSRM
python scripts/build_subzone_stats.py       # -> output/hdb_access_children.csv, output/subzone_stats.csv, gpkg layer subzone_stats
```

| Path | What |
|---|---|
| `data/Centres_2026.geojson` | **Canonical centre layer.** 1,651 active childcare (CC) + kindergarten (KN) centres from the Oct-2026 ECDA listing, geocoded by postal code (1,359 reused from the 2021 points, 292 via OneMap). Has `centre_code`, operator, service model, scheme, hours. The 2021 GeoJSON is stale: 292 active centres have no 2021 point and 541 of its points are at postal codes no longer listed. |
| `data/MRTStationExits_2026.geojson`, `data/BusStops_2026.geojson` | LTA MRT exits (613) and bus stops (5,205), data.gov.sg, Oct 2026 |
| `output/hdb_walk_access.csv` | per block: nearest walk minutes / metres / id and counts within 10 and 15 min, for `centres` (2026), `centres2021` (comparison) and `mrt_exits`. Bus stops not run yet (`--sets bus_stops`). |
| `output/hdb_access_children.csv` | the above joined to Jessie's children 0–4 / 5–9 and flat-type mix |
| `output/subzone_stats.csv` + gpkg layer `subzone_stats` | per subzone: children, dwelling units, % 1–3 room, centres in polygon (by type), centres per 1,000 children, centre and child density, child-weighted nearest walk time, share of children within 10 / 15 min of a centre, MRT walk time, planning-area median income |

Headline (2026 centres): median walk from an HDB block to the nearest centre 3.4 min (p90 6.4);
only 3 blocks have no centre within 15 min; 2,350 blocks are more than 15 min from an MRT exit.
Walking access to *a* centre is near-universal, so the discriminating measures are supply per child
(`centres_per_1000_children`, p10–p90 = 2.6–9.6 across HDB subzones) and the walk-time distribution,
not a binary "has access". Two unreachable destinations (a centre and the MRT exit inside Changi
Airport) are expected: the airport is cut off from the public footpath network.
