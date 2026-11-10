# 2 Exploratory spatial data analysis

Before any hypothesis is tested, this stage looks at each ingredient on its own: where income is
high and low (planning areas), where the young children live (a weighted density surface), whether
HDB blocks and childcare centres are clustered at all (Ripley's K), how far a block is from its
nearest centre on the walking network (OSRM matrices), and whether subzones with more children have
more centres (H-a, descriptive). The notebooks read the stage 1 outputs in `output/` and
`large_data/` and write figures to `figures/` (and, for the income and K-function steps, tables to
`output/`). Every notebook was executed top to bottom on 2026-11-10 with outputs saved; only the
route-sample cell of 2.4 needs the local OSRM server, and its saved output is from a run with the
server up.

| Notebook | What it does | Inputs | Outputs | Runtime | Executed? |
|---|---|---|---|---|---|
| [2_01_income_distribution.ipynb](2_01_income_distribution.ipynb) | Income-band shares per planning area (100% stacked bar) and the band containing the median household, mapped as a choropleth (Daryl) | `data/ResidentHouseholdsIncomebyPlanningArea.csv`, `data/MasterPlanSubZones_2019.geojson` | [`output/resident-household-income_regression/planning_area_median_household_income_range.csv`](../output/resident-household-income_regression/planning_area_median_household_income_range.csv), [`Resident_household_income_by_planning_area.png`](../output/resident-household-income_regression/Resident_household_income_by_planning_area.png), [`median_income_choropleth.png`](../output/resident-household-income_regression/median_income_choropleth.png) | 5 s | yes |
| [2_02_child_density_kde.ipynb](2_02_child_density_kde.ipynb) | Gaussian KDE (100 m grid, sigma 800 m) of HDB block centroids weighted by children 0–6, with the 1,796 centres overlaid; hotspot table by subzone (Kenneth) | `output/hdb_blocks.gpkg` (`hdb_points`), `output/hdb_access_children.csv`, `output/childcare_centres_2026.gpkg`, subzones | [`figures/child_centre_kde_map.png`](../figures/child_centre_kde_map.png) | 5 s | yes |
| [2_03_ripleys_k.ipynb](2_03_ripleys_k.ipynb) | Border-corrected Ripley's K for HDB blocks and for centres, 100–1,500 m, 199 CSR simulations each, global max(L−r) test; K-scale and L−r plots (Karis / Minh) | `output/hdb_blocks.gpkg` (`hdb_points`), `output/childcare_centres_2026.gpkg`, subzones | [`output/k_function/`](../output/k_function/): `k_summary.csv`, `*_k_curve.csv`, `*_csr_simulations.npz`, [`k_function_comparison.png`](../output/k_function/k_function_comparison.png), [`l_function_comparison.png`](../output/k_function/l_function_comparison.png) | 50 s | yes |
| [2_04_walking_access.ipynb](2_04_walking_access.ipynb) | Sample of 100 OSRM walking routes (folium + static), nearest-centre time and distance per block, 5/10/15-minute catchment panels, cross-checked against `hdb_walk_access.csv` (Karis) | `large_data/walk_centres_time_min.parquet`, `walk_centres_dist_m.parquet`, `output/hdb_walk_access.csv`, `hdb_points`, centres, subzones | [`figures/walk_routes_sample.html`](../figures/walk_routes_sample.html), [`walk_routes_sample.png`](../figures/walk_routes_sample.png), [`walk_nearest_time_map.png`](../figures/walk_nearest_time_map.png), [`walk_nearest_distance_map.png`](../figures/walk_nearest_distance_map.png), [`walk_catchments_5_10_15.png`](../figures/walk_catchments_5_10_15.png) | 12 s (+ OSRM on `localhost:5001` for section 2) | yes, with OSRM up |
| [2_05_centres_vs_children.ipynb](2_05_centres_vs_children.ipynb) | H-a descriptive: centres vs children 0–6 per HDB subzone (≥ 100 children), log–log OLS slope, Spearman of children vs centres per 1,000, top/bottom subzones (Minh) | `output/subzone_pressure.csv`, `output/subzone_stats.csv` | [`figures/ha_centres_vs_children.png`](../figures/ha_centres_vs_children.png) | 6 s | yes |

## Findings

- **Income clusters in the central region, at both ends.** Six of the 30 planning areas have a
  median household income band of $10,000 or more; five are in the Central Region (Tanglin
  $20,000 & over, River Valley $17,500–19,999, Bukit Timah and Downtown Core $15,000–17,499,
  Bishan $10,000–10,999), Pasir Ris is the only one outside it. The lowest bands are also central:
  Outram $3,000–3,999 (48% of its households have no employed person or earn under $3,000), then
  Bukit Merah, Geylang, Kallang, Toa Payoh and Ang Mo Kio at $5,000–5,999. Mean band order:
  Central 10.2, East 9.3, North-East 8.8, West 8.2, North 8.0. The median band is the
  planning-area income variable used in stage 3.
- **Child density hotspots are the new towns.** 176,409 children 0–6 across 10,755 blocks; the
  smoothed surface peaks at about 2,100 children per km² in Tampines North and Tampines East,
  followed by Matilda, Punggol Field, Sengkang Town Centre, Tampines West, Rivervale, Waterway East,
  Punggol Town Centre and Brickworks. Of the 20 highest-density subzones, 4 are in Punggol, 4 in
  Sengkang, 3 in Tampines and 3 in Tengah.
- **Both point patterns are clustered, which is descriptive only.** Max L(r) − r = 1,456 m for the
  10,769 HDB blocks and 1,050 m for the 1,796 centres, against CSR bands that stay within 10 m and
  28 m of zero; global p = 0.005 for each (the smallest value 199 simulations allow), Bonferroni
  0.01. The baseline is homogeneous CSR over all land, so this only says that estates exist; whether
  centres co-locate with blocks would need a cross-K, and is addressed instead by supply per child.
- **Walking access to a centre is near-universal.** Median walk from an HDB block to the nearest
  centre 3.1 min (p90 6.0 min; median 260 m); 81.3% of blocks within 5 minutes, 99.7% within 10,
  99.97% within 15. The three blocks beyond 15 minutes are at Changi Point (about 50 min). The two
  centres inside Changi Airport are unreachable from every block (expected: airport footpaths are
  not public). Hence the later stages use supply per child and the walk-time distribution, not a
  binary "has access".
- **Supply follows demand at two-thirds the rate (H-a).** Across 140 HDB subzones with ≥ 100
  children 0–6, log(centres) on log(children) has slope 0.65 (SE 0.05), R² 0.57, significantly
  below 1 (t = −7.2); Spearman between children and centres per 1,000 children is −0.50, so the
  biggest subzones are the thinnest-served. Lowest ratios: Tampines North 1.5 centres per 1,000
  children (596 children per reachable centre), Plantation 2.0, Bidadari 3.1, Brickworks 3.2;
  median across the 140 is 8.9.

## Run order

The notebooks are independent of each other; each reads only stage 1 outputs. Suggested order is
numeric, `2_01` to `2_05`. From this folder:

```
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=3600 2_0N_<name>.ipynb
```

For `2_04`, start OSRM first (root README, "Walking access"):
`osrm-routed --algorithm mld --max-table-size 10000 -p 5001 large_data/singapore.osrm &`.
Without it the route-sample cell prints a warning and draws no routes; everything else still runs.
