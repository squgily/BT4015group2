# Spatial autocorrelation of full-day SC nursery fees by planning area

## Method

- Source points: `data/ChildCareServices_2021.geojson`; null/non-numeric `FULL_DAY_SC_NURSERY_FEE` records excluded.
- Spatial unit: 2019 planning areas (`PLN_AREA_N`) from `data/MasterPlanSubZones_2019.geojson`.
- Area statistic: median centre fee in SGD. The centre count and mean are retained for context.
- Spatial weights: symmetric 4-nearest-neighbour graph based on area-weighted planning area centroids, row-standardised.
- Inference: 999 random permutations, seed 4015. Local p-values are exploratory; Benjamini-Hochberg FDR q-values are also reported.

## Data coverage

- Centre features: 1,925
- Excluded null/invalid fees: 562
- Valid fee points outside a planning area polygon: 0
- Centres analysed: 1,363
- Planning areas with at least one valid centre: 38

## Global Moran's I

- Observed I: **0.2979**
- Randomisation expectation: **-0.0270**
- Permutation pseudo-p: **0.0030**

The area-level median fees show **positive spatial autocorrelation**, and the result is **statistically significant at the 5% level** under this weights specification.

## Local Moran clusters (raw permutation p < 0.05)

| planning_area | median_fee_sgd | centre_count | lisa_cluster_p05 | local_moran_i | local_permutation_p | local_fdr_q |
| --- | --- | --- | --- | --- | --- | --- |
| NEWTON | 2280.0000 | 4.0000 | High-High | 2.5022 | 0.0020 | 0.0190 |
| TANGLIN | 1750.0000 | 7.0000 | High-High | 1.2214 | 0.0020 | 0.0190 |
| RIVER VALLEY | 2470.0000 | 5.0000 | High-High | 2.1341 | 0.0030 | 0.0228 |
| SINGAPORE RIVER | 1990.0000 | 2.0000 | High-High | 1.4230 | 0.0070 | 0.0443 |
| ORCHARD | 2480.0000 | 3.0000 | High-High | 2.0945 | 0.0100 | 0.0543 |
| DOWNTOWN CORE | 1725.0000 | 14.0000 | High-High | 0.8586 | 0.0210 | 0.0697 |
| ROCHOR | 1925.0000 | 4.0000 | High-High | 1.3353 | 0.0290 | 0.0848 |
| MANDAI | 1680.0000 | 3.0000 | High-Low | -0.6893 | 0.0010 | 0.0190 |
| SELETAR | 1900.0000 | 1.0000 | High-Low | -0.9278 | 0.0010 | 0.0190 |
| BUKIT MERAH | 630.0000 | 42.0000 | Low-High | -0.6245 | 0.0210 | 0.0697 |
| OUTRAM | 650.0000 | 7.0000 | Low-High | -0.6492 | 0.0220 | 0.0697 |
| NOVENA | 650.0000 | 17.0000 | Low-High | -0.5018 | 0.0420 | 0.1064 |
| CHOA CHU KANG | 610.0000 | 55.0000 | Low-Low | 0.4587 | 0.0170 | 0.0697 |
| SERANGOON | 650.0000 | 41.0000 | Low-Low | 0.4194 | 0.0180 | 0.0697 |
| HOUGANG | 610.0000 | 69.0000 | Low-Low | 0.4459 | 0.0320 | 0.0869 |

Note: local results involve multiple comparisons. Prefer `local_fdr_q` / `lisa_cluster_fdr05` when confirmatory control of false discoveries is required. Results describe planning area medians, not individual-centre fee similarity.
