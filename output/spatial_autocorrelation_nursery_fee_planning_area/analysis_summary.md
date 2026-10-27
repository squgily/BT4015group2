# Spatial autocorrelation of full-day SC nursery fees

## Method

- Source points: `data/ChildCareServices_2021.geojson`; null/non-numeric `FULL_DAY_SC_NURSERY_FEE` records excluded.
- Spatial unit: 2019 planning areas (`PLN_AREA_N`) from `data/MasterPlanSubZones_2019.geojson`.
- Area statistic: mean centre fee in SGD. The centre count and median are retained for context.
- Spatial weights: symmetric 4-nearest-neighbour graph based on area-weighted planning-area centroids, row-standardised.
- Inference: 999 random permutations, seed 4015. Local p-values are exploratory; Benjamini-Hochberg FDR q-values are also reported.

## Data coverage

- Centre features: 1,925
- Excluded null/invalid fees: 562
- Valid fee points outside a planning-area polygon: 0
- Centres analysed: 1,363
- Planning areas with at least one valid centre: 38

## Global Moran's I

- Observed I: **0.3866**
- Randomisation expectation: **-0.0270**
- Permutation pseudo-p: **0.0010**

The area-level mean fees show **positive spatial autocorrelation**, and the result is **statistically significant at the 5% level** under this weights specification.

## Local Moran clusters (raw permutation p < 0.05)

| planning_area | mean_fee_sgd | centre_count | lisa_cluster_p05 | local_moran_i | local_permutation_p | local_fdr_q |
| --- | --- | --- | --- | --- | --- | --- |
| NEWTON | 2195.0000 | 4.0000 | High-High | 2.8307 | 0.0010 | 0.0127 |
| TANGLIN | 1861.7229 | 7.0000 | High-High | 1.5763 | 0.0010 | 0.0127 |
| RIVER VALLEY | 2682.0000 | 5.0000 | High-High | 2.5686 | 0.0030 | 0.0228 |
| ORCHARD | 2326.6667 | 3.0000 | High-High | 2.3926 | 0.0040 | 0.0253 |
| SINGAPORE RIVER | 1990.0000 | 2.0000 | High-High | 1.4991 | 0.0070 | 0.0333 |
| DOWNTOWN CORE | 1597.8571 | 14.0000 | High-High | 0.6937 | 0.0140 | 0.0532 |
| ROCHOR | 1952.5000 | 4.0000 | High-High | 1.2713 | 0.0340 | 0.0782 |
| SELETAR | 1900.0000 | 1.0000 | High-Low | -1.1214 | 0.0010 | 0.0127 |
| MANDAI | 1526.6667 | 3.0000 | High-Low | -0.5005 | 0.0160 | 0.0538 |
| BUKIT MERAH | 874.4845 | 42.0000 | Low-High | -0.7115 | 0.0060 | 0.0326 |
| OUTRAM | 975.7143 | 7.0000 | Low-High | -0.4631 | 0.0170 | 0.0538 |
| NOVENA | 1190.6735 | 17.0000 | Low-High | -0.0130 | 0.0350 | 0.0782 |
| CHOA CHU KANG | 724.3273 | 55.0000 | Low-Low | 0.7782 | 0.0020 | 0.0190 |
| BUKIT BATOK | 831.0000 | 50.0000 | Low-Low | 0.5260 | 0.0100 | 0.0422 |
| JURONG WEST | 723.7958 | 84.0000 | Low-Low | 0.6304 | 0.0210 | 0.0614 |
| WESTERN WATER CATCHMENT | 650.0000 | 1.0000 | Low-Low | 0.7825 | 0.0260 | 0.0706 |
| HOUGANG | 837.0022 | 69.0000 | Low-Low | 0.3976 | 0.0340 | 0.0782 |
| SERANGOON | 1049.6580 | 41.0000 | Low-Low | 0.1864 | 0.0450 | 0.0950 |

Note: local results involve multiple comparisons. Prefer `local_fdr_q` / `lisa_cluster_fdr05` when confirmatory control of false discoveries is required. Results describe planning-area means, not individual-centre fee similarity.
