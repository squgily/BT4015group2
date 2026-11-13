# BT4015 Group 2 — Spatial Accessibility of Early Childhood Centres in Singapore

Where is childcare access weakest for young families in HDB estates, and would ECDA's planned centres fix it?
We measure walking access from every residential HDB block to every operating centre, build a demand estimate
of children aged 0–6 per block, test where fees, income and access cluster, and derive a supply-pressure
index whose high-high clusters are the recommendation. Proposal:
<https://docs.google.com/document/d/1D4b8GMSYMx0BUsGKTX3J_nI62QtSSxzxvbTxfGdXYas/edit?usp=sharing>.

Every analysis is an executed Jupyter notebook with its outputs saved, so the work can be read without
running anything. The style rules are in [docs/notebook_style.md](docs/notebook_style.md); the decisions
the team took along the way, with dates and evidence, are in [docs/decisions.md](docs/decisions.md).

## Project structure

| Stage | Purpose | Notebooks |
|---|---|---|
| [0_Data_Exploration](0_Data_Exploration/README.md) | Experiments and superseded approaches kept for the record: the clustering-method experiment, the floor-area child allocation, the first OneMap geocoding pass, the bus-stop variance check, Karis's original OD-matrix notebook and her cadastral-lot clustering. Not part of the pipeline. | 6 |
| [1_Data_Preparation](1_Data_Preparation/README.md) | Join HDB blocks to their attributes, allocate children to blocks, build the 2026 centre layer with fees, route walking times with OSRM, integrate everything per block and per subzone. | 8 |
| [2_ESDA](2_ESDA/README.md) | Describe the data spatially: income and fee maps, child-density KDE, Ripley's K, walking-access maps and isochrones, centres against children. | 5 |
| [3_Hypothesis_Testing](3_Hypothesis_Testing/README.md) | Test the hypotheses: fee clustering (Moran's I, LISA), income–fee regression and GWR, child-density clustering, walking access by SES, the proposal's H-c, the supply-pressure index with LISA and sensitivities, and the planned-centre impact. | 8 |
| [run_all.ipynb](run_all.ipynb) | Driver: executes the 21 stage 1–3 notebooks in order and prints a status table. | 1 |
| [src/bt4015](src/bt4015/) | Small shared helpers imported by the notebooks: paths, spatial weights, OSRM table calls, 2SFCA, fee join, Moran utilities, regression helpers. | — |

Shared folders at the root:

| Folder | Contents |
|---|---|
| `data/` | Raw downloads, never edited (sources below). |
| `output/` | Derived tables and GeoPackage layers written by the notebooks; later stages read earlier stages' outputs from here. |
| `figures/` | Figures used in the report and slides. |
| `large_data/` | Git-ignored: the OSM extract, the OSRM graph, and the walk-time matrices as parquet (see stage 1 for how to rebuild). |
| `docs/` | Decision log, clustering experiment write-up, notebook style guide. |

## Run order

**One-click:** open [run_all.ipynb](run_all.ipynb) at the root and run it. It executes the 21 notebooks of
stages 1–3 in order, each in a fresh kernel, refreshes their outputs in place and prints a pass/fail table
(about 4 minutes, no network needed).

By hand: run the notebooks in each stage in numeric order; stage 2 and stage 3 read stage 1's outputs. The committed
`output/` folder already holds every result, so any notebook can be opened and re-run on its own.

Two steps are not re-run by default because they need external services:

- The OneMap geocoding (`0_Data_Exploration/geocode_centres_onemap.ipynb`; stage 1's `1_05` is served
  entirely from the committed cache) and the walk-matrix build in `1_06` (about 1.7 h against a local OSRM
  server, kept behind `REBUILD_MATRIX = False`). Their outputs are committed (`output/childcare_centres_2026.gpkg`,
  the matrices in `large_data/`). Stage 1's README has the OSRM setup commands.

Python 3.12 with geopandas, pyogrio, shapely, pandas, numpy, scipy, scikit-learn, statsmodels, matplotlib,
libpysal, esda, pyarrow, openpyxl and requests. Execute a notebook from its folder with
`jupyter nbconvert --to notebook --execute --inplace <notebook>.ipynb`.

## Hypotheses and headline results

| Hypothesis | Verdict | Evidence |
|---|---|---|
| H-a: subzones with more young children have more centres | Supported, with a lag: supply follows demand at an elasticity of 0.65, so the largest estates have the fewest centres per child | `2_05`, `3_04` |
| H-b: walking access differs by income or housing type | Not for distance (median 3.1 min, flat across income and flat-type terciles); yes for price (fees rise S$114 per S$1,000 of income, one national slope) | `3_01`–`3_03`, `3_05` |
| H-c: children and poor access cluster together | Rejected as posed (bivariate Moran's I −0.19); reframed as supply pressure, which clusters (I +0.18, p 0.002) in Tengah, Bukit Batok and Punggol | `3_06`, `3_07` |
| Do the 13 planned centres close the gap? | Partly: Tengah and Tampines North get relief; 16 of 20 weak-link subzones have no planned centre within a 10-minute walk | `3_08` |

Main finding: the gap is not distance or price, it is capacity in fast-growing new towns.

## Key numbers

| Quantity | Value |
|---|---|
| HDB blocks (polygons joined to attributes) | 13,436, 98.8% matched; 10,769 residential |
| Children on HDB blocks | 259,910 aged 0–9; 176,409 aged 0–6 (0–4 plus each subzone's 5–6 share of 5–9) |
| Centres operating Oct 2026 | 1,796 (CC 1,467, KN 183, DS 84, EYC-DS 57, EYC 5); 1,587 with a listed full-day nursery fee; 13 planned |
| Walk matrix | 10,769 blocks × 1,796 centres (+13 planned, 613 MRT exits), OSRM foot profile |
| Spatial units | 332 Master Plan 2019 subzones (159 with HDB), 55 planning areas |

## Data sources

| File | Source |
|---|---|
| `data/HDBExistingBuilding_2026.geojson` | HDB Existing Building, data.gov.sg `d_16b157c52ed637edd6ba1232e026258d`, version 2026-06-21 |
| `data/HDBPropertyInformation_2026.csv` | HDB Property Information, data.gov.sg `d_17f5382f26140b1fdae0ba2ef6239d2f`, version 2026-10-08 |
| `data/LTARoadNameCode_2019.xlsx` | LTA DataMall road-code → road-name lookup (sheet `GISDomainData`) |
| `data/MasterPlanSubZones_2019.geojson` | Master Plan 2019 Subzone Boundary (No Sea), data.gov.sg `d_8594ae9ff96d0c708bc2af633048edfb`, version 2025-12-03 |
| `data/subzone_child_population_2026.xlsx` | SingStat Resident Population by Planning Area/Subzone, Age Group and Type of Dwelling, June 2026 |
| `data/SubzoneSingleYearAge_2026.csv` | SingStat Residents by Planning Area/Subzone, Single Year of Age and Sex, June 2026 (for the 5–6 share of ages 5–9) |
| `data/CentreAttributes_2026.csv`, `data/ListingofCentreServices.csv` | ECDA centre listing and fee listing, Oct 2026 (`d_44cfe12f2858ae503a093dfc075a28be`) |
| `data/ChildCareServices_2021.geojson` | Child Care Services, data.gov.sg `d_5d668e3f544335f8028f546827b773b4` (2021 points reused for geocoding) |
| `data/MRTStationExits_2026.geojson`, `data/BusStops_2026.geojson` | LTA MRT exits (613) and bus stops (5,205), data.gov.sg, Oct 2026 |
| `data/ResidentHouseholdsIncomebyPlanningArea.csv` | SingStat Census 2020 resident households by planning area and monthly household income |
| `data/PrivatePropertyPoint_2025.geojson` | URA private property points (not used in the demand estimate; see limitations) |
| `large_data/*.osm.pbf` | OpenStreetMap extract, Geofabrik `malaysia-singapore-brunei`, clipped to Singapore |

Deprecated and kept only for the record: `data/Centres_2026.geojson` (1,651 CC + KN centres from the first
geocoding pass; superseded by `output/childcare_centres_2026.gpkg`).

## Team

Hoang Anh Minh (coordination, HDB join, clustering, walk matrix, subzone integration, pressure index, planned
centres), Jessie (child allocation, canonical centre layer and its QA), Daryl (income, fees, Moran, OLS, GWR),
Kenneth (child-density KDE and Moran), Karis (walking-access maps, isochrones, Ripley's K).
