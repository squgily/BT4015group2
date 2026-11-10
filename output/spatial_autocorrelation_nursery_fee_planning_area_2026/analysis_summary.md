# Spatial autocorrelation of full-day SC nursery fees by planning area

## Method

- Source points: `data/Centres_2026_fees.geojson`; null/non-numeric `FULL_DAY_SC_NURSERY_FEE` records excluded.
- Spatial unit: 2019 planning areas (`PLN_AREA_N`) from `data/MasterPlanSubZones_2019.geojson`.
- Area statistic: median centre fee in SGD. The centre count and mean are retained for context.
- Spatial weights: symmetric 4-nearest-neighbour graph based on area-weighted planning area centroids, row-standardised.
- Inference: 999 random permutations, seed 4015. Local p-values are exploratory; Benjamini-Hochberg FDR q-values are also reported.

## Data coverage

- Centre features: 1,796
- Excluded null/invalid fees: 210
- Valid fee points outside a planning area polygon: 0
- Centres analysed: 1,586
- Planning areas with at least one valid centre: 42

## Global Moran's I

- Observed I: **0.5110**
- Randomisation expectation: **-0.0244**
- Permutation pseudo-p: **0.0010**

The area-level median fees show **positive spatial autocorrelation**, and the result is **statistically significant at the 5% level** under this weights specification.

## Local Moran clusters (raw permutation p < 0.05)

| planning_area | median_fee_sgd | centre_count | lisa_cluster_p05 | local_moran_i | local_permutation_p | local_fdr_q |
| --- | --- | --- | --- | --- | --- | --- |
| MUSEUM | 2250.0000 | 1.0000 | High-High | 1.3833 | 0.0010 | 0.0140 |
| SINGAPORE RIVER | 2200.0000 | 6.0000 | High-High | 1.5309 | 0.0010 | 0.0140 |
| MARINA SOUTH | 3010.0000 | 1.0000 | High-High | 2.7757 | 0.0020 | 0.0140 |
| NEWTON | 2280.0000 | 4.0000 | High-High | 1.6211 | 0.0020 | 0.0140 |
| ORCHARD | 2480.0000 | 3.0000 | High-High | 1.6281 | 0.0040 | 0.0240 |
| RIVER VALLEY | 2100.0000 | 7.0000 | High-High | 1.0605 | 0.0060 | 0.0305 |
| TANGLIN | 2291.0000 | 11.0000 | High-High | 1.4353 | 0.0070 | 0.0305 |
| DOWNTOWN CORE | 2350.0000 | 18.0000 | High-High | 1.5964 | 0.0080 | 0.0305 |
| MANDAI | 1815.0000 | 2.0000 | High-Low | -0.6342 | 0.0410 | 0.1062 |
| OUTRAM | 975.0000 | 8.0000 | Low-High | -0.4416 | 0.0010 | 0.0140 |
| BUKIT MERAH | 650.0000 | 43.0000 | Low-High | -0.7789 | 0.0080 | 0.0305 |
| SELETAR | 650.0000 | 1.0000 | Low-Low | 0.6293 | 0.0020 | 0.0140 |
| HOUGANG | 650.0000 | 70.0000 | Low-Low | 0.5490 | 0.0120 | 0.0420 |
| BUKIT BATOK | 650.0000 | 58.0000 | Low-Low | 0.5308 | 0.0200 | 0.0646 |
| SERANGOON | 1000.0000 | 45.0000 | Low-Low | 0.2398 | 0.0270 | 0.0810 |
| JURONG EAST | 650.0000 | 33.0000 | Low-Low | 0.6187 | 0.0360 | 0.1008 |
| TENGAH | 610.0000 | 14.0000 | Low-Low | 0.5465 | 0.0430 | 0.1062 |
| WESTERN WATER CATCHMENT | 1200.0000 | 2.0000 | Low-Low | 0.0246 | 0.0470 | 0.1083 |
| SENGKANG | 610.0000 | 90.0000 | Low-Low | 0.5801 | 0.0490 | 0.1083 |

Note: local results involve multiple comparisons. Prefer `local_fdr_q` / `lisa_cluster_fdr05` when confirmatory control of false discoveries is required. Results describe planning area medians, not individual-centre fee similarity.
