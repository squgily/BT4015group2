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
and joins on block + street. Match rate: 13,280 / 13,436 (98.8%).

```
python scripts/join_hdb_nationwide.py
```

| Path | What |
|---|---|
| `data/HDBExistingBuilding_2026.geojson` | HDB Existing Building, data.gov.sg `d_16b157c52ed637edd6ba1232e026258d`, version 2026-06-21 |
| `data/HDBPropertyInformation_2026.csv` | HDB Property Information, data.gov.sg `d_17f5382f26140b1fdae0ba2ef6239d2f`, version 2026-10-08 |
| `data/LTARoadNameCode_2019.xlsx` | LTA DataMall road-code → road-name lookup (sheet `GISDomainData`) |
| `output/hdb_blocks.gpkg` | layer `hdb_blocks`, EPSG:3414, all blocks with attributes + `footprint_m2`, `gfa_m2`, `is_residential`, `match_status` |
| `output/hdb_join_review.csv` | the 156 unmatched blocks (mostly road codes newer than the 2019 LTA table) |
| `data/ChildCareServices_2021.geojson` | Child Care Services, data.gov.sg `d_5d668e3f544335f8028f546827b773b4`, version 2026-04-18 | 
| `data/MasterPlanSubZones_2019.geojson` | Master Plan 2019 Subzone Boundary (No Sea) (GEOJSON), data.gov.sg `d_8594ae9ff96d0c708bc2af633048edfb`, version 2025-12-03 | 


Use `is_residential` to drop carparks / markets / pavilions before computing demand.
`gfa_m2` = footprint area × `max_floor_lvl` is the team's agreed weight for allocating
young-child population to blocks; `total_dwelling_units` is also available for a
robustness check. Requires `geopandas`, `pyogrio`, `pandas`, `openpyxl`.
