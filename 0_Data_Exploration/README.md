# 0 Data exploration and superseded approaches

Work that shaped the pipeline but is not part of it: method experiments whose result became a
decision, and earlier versions of a step that a later notebook replaced. Each notebook's title cell
says what it tried, what it found, and which stage notebook took over. Nothing here is read by
stages 1 to 3; the committed outputs were produced by the stage notebooks.

| Notebook | What it is | Decision or replacement | Executed? |
|---|---|---|---|
| [clustering_experiment.ipynb](clustering_experiment.ipynb) | Compares DBSCAN and single, average and complete linkage for grouping HDB blocks into neighbourhoods, per subzone, by cluster size, diameter and the error of using the cluster centroid for walk times (Minh) | Complete linkage, 300 m, chosen ([docs/clustering_decision.md](../docs/clustering_decision.md)); implemented in `1_03`. Later superseded altogether when the prof asked for blocks, not clusters, as walk-matrix origins | yes, 6 s |
| [cadastral_lots_clustering.ipynb](cadastral_lots_clustering.ipynb) | Alternative grouping of blocks by SLA cadastral land lot (Karis): 2,081 clusters, 540 singletons, centroid error up to 960 m | Not used; block-centroid clustering in `1_03` kept the error under 300 m | no (SLA layer not in the repo; saved outputs kept) |
| [assign_child_population_floor_area.ipynb](assign_child_population_floor_area.ipynb) | First child allocation: subzone counts by floor-area band spread over blocks using floor areas from HDB resale transactions (Kenneth) | Replaced by the type-of-dwelling allocation in `1_04`, which needs no resale download and uses HDB dwelling rows only | no (downloads five resale datasets) |
| [geocode_centres_onemap.ipynb](geocode_centres_onemap.ipynb) | First centre layer: the Oct 2026 ECDA listing geocoded by postal code through the OneMap API, child care and kindergartens only, 1,651 points (`data/Centres_2026.geojson`, deprecated) (Minh) | Replaced by `1_05`, which reuses 2021 points, geocodes only new addresses, keeps all service models (1,796) and attaches fees by centre code | no (live OneMap calls) |
| [bus_stop_variance_check.ipynb](bus_stop_variance_check.ipynb) | Why bus stops are not a covariate: straight-line and OSRM walk times from blocks to the nearest bus stop have almost no spread (median 2.8 min, none over 10), unlike MRT exits (median 9.0 min, 44% over 10) (Minh) | Bus stops dropped, MRT walk time kept as covariate; prof-confirmed 30 Oct 2026 ([docs/decisions.md](../docs/decisions.md)) | yes, 76 s (part 2 needs OSRM on `localhost:5001`) |
| [osrm_walking_query_original.ipynb](osrm_walking_query_original.ipynb) | Karis's original OSRM notebook, trimmed to her origin–destination matrix builder (Docker OSRM, 100 × 100 table chunks, JSON output) | Replaced by `1_06_build_walk_matrix`; her analysis cells became `2_04_walking_access` and `2_03_ripleys_k` | no (needs her matrix files; saved outputs kept) |
