# Spatial autocorrelation of full-day SC nursery fees by subzone

## Method

- Source points: `data/ChildCareServices_2021.geojson`; null/non-numeric `FULL_DAY_SC_NURSERY_FEE` records excluded.
- Spatial unit: 2019 subzones (`SUBZONE_N`) from `data/MasterPlanSubZones_2019.geojson`.
- Area statistic: median centre fee in SGD. The centre count and mean are retained for context.
- Spatial weights: symmetric 4-nearest-neighbour graph based on area-weighted subzone centroids, row-standardised.
- Inference: 999 random permutations, seed 4015. Local p-values are exploratory; Benjamini-Hochberg FDR q-values are also reported.

## Data coverage

- Centre features: 1,925
- Excluded null/invalid fees: 562
- Valid fee points outside a subzone polygon: 0
- Centres analysed: 1,363
- Subzones with at least one valid centre: 210

## Global Moran's I

- Observed I: **0.3757**
- Randomisation expectation: **-0.0048**
- Permutation pseudo-p: **0.0010**

The area-level median fees show **positive spatial autocorrelation**, and the result is **statistically significant at the 5% level** under this weights specification.

## Local Moran clusters (raw permutation p < 0.05)

| subzone | median_fee_sgd | centre_count | lisa_cluster_p05 | local_moran_i | local_permutation_p | local_fdr_q |
| --- | --- | --- | --- | --- | --- | --- |
| BOULEVARD | 2480.0000 | 3.0000 | High-High | 5.4440 | 0.0010 | 0.0210 |
| CAIRNHILL | 2200.0000 | 1.0000 | High-High | 4.6873 | 0.0010 | 0.0210 |
| GOODWOOD PARK | 2105.0000 | 2.0000 | High-High | 3.4098 | 0.0010 | 0.0210 |
| HOLLAND ROAD | 2175.0000 | 2.0000 | High-High | 2.9504 | 0.0010 | 0.0210 |
| LEONIE HILL | 2520.0000 | 2.0000 | High-High | 6.0435 | 0.0010 | 0.0210 |
| NASSIM | 1883.0000 | 4.0000 | High-High | 3.0018 | 0.0010 | 0.0210 |
| NEWTON CIRCUS | 2370.0000 | 1.0000 | High-High | 4.0451 | 0.0010 | 0.0210 |
| OXLEY | 2950.0000 | 2.0000 | High-High | 6.9461 | 0.0010 | 0.0210 |
| SWISS CLUB | 1930.0000 | 5.0000 | High-High | 3.4674 | 0.0010 | 0.0210 |
| CORONATION ROAD | 2200.0000 | 5.0000 | High-High | 3.8030 | 0.0020 | 0.0323 |
| MALCOLM | 1580.0000 | 1.0000 | High-High | 1.7378 | 0.0020 | 0.0323 |
| ROBERTSON QUAY | 1990.0000 | 2.0000 | High-High | 2.5024 | 0.0020 | 0.0323 |
| MOUNT EMILY | 1980.0000 | 2.0000 | High-High | 2.7301 | 0.0040 | 0.0560 |
| HILLCREST | 2085.6250 | 4.0000 | High-High | 3.2942 | 0.0050 | 0.0618 |
| INSTITUTION HILL | 2470.0000 | 1.0000 | High-High | 3.2897 | 0.0080 | 0.0840 |
| ANAK BUKIT | 1500.0000 | 12.0000 | High-High | 0.9206 | 0.0200 | 0.1378 |
| FARRER COURT | 2000.0000 | 1.0000 | High-High | 1.5684 | 0.0210 | 0.1378 |
| VICTORIA | 1925.0000 | 2.0000 | High-High | 1.9011 | 0.0230 | 0.1464 |
| MOULMEIN | 1608.2250 | 2.0000 | High-High | 1.2240 | 0.0250 | 0.1544 |
| SELETAR | 1900.0000 | 1.0000 | High-Low | -1.0656 | 0.0010 | 0.0210 |
| WOODLANDS REGIONAL CENTRE | 1125.0000 | 2.0000 | High-Low | -0.1447 | 0.0040 | 0.0560 |
| PASIR RIS PARK | 1650.0000 | 2.0000 | High-Low | -0.7496 | 0.0350 | 0.1758 |
| TEBAN GARDENS | 610.0000 | 7.0000 | Low-High | -0.7396 | 0.0210 | 0.1378 |
| CRAWFORD | 610.0000 | 3.0000 | Low-High | -0.7525 | 0.0280 | 0.1633 |
| MARINE PARADE | 630.0000 | 8.0000 | Low-High | -0.5937 | 0.0300 | 0.1658 |
| BUKIT HO SWEE | 610.0000 | 4.0000 | Low-High | -0.5993 | 0.0360 | 0.1758 |
| YUHUA WEST | 610.0000 | 3.0000 | Low-Low | 0.4637 | 0.0050 | 0.0618 |
| PUNGGOL FIELD | 610.0000 | 16.0000 | Low-Low | 0.4558 | 0.0080 | 0.0840 |
| SENGKANG TOWN CENTRE | 610.0000 | 24.0000 | Low-Low | 0.4637 | 0.0080 | 0.0840 |
| BUKIT BATOK WEST | 610.0000 | 5.0000 | Low-Low | 0.4566 | 0.0130 | 0.1225 |
| COMPASSVALE | 610.0000 | 7.0000 | Low-Low | 0.4637 | 0.0130 | 0.1225 |
| RIVERVALE | 610.0000 | 19.0000 | Low-Low | 0.4637 | 0.0140 | 0.1225 |
| TAMAN JURONG | 610.0000 | 13.0000 | Low-Low | 0.4542 | 0.0140 | 0.1225 |
| TOWNSVILLE | 610.0000 | 8.0000 | Low-Low | 0.4542 | 0.0150 | 0.1260 |
| FAJAR | 610.0000 | 10.0000 | Low-Low | 0.4637 | 0.0160 | 0.1292 |
| BALESTIER | 650.0000 | 14.0000 | Low-Low | 0.4077 | 0.0190 | 0.1378 |
| NORTHSHORE | 650.0000 | 4.0000 | Low-Low | 0.4163 | 0.0200 | 0.1378 |
| SENJA | 610.0000 | 3.0000 | Low-Low | 0.4479 | 0.0210 | 0.1378 |
| CHOA CHU KANG NORTH | 650.0000 | 10.0000 | Low-Low | 0.4077 | 0.0280 | 0.1633 |
| SEMBAWANG CENTRAL | 610.0000 | 16.0000 | Low-Low | 0.4542 | 0.0300 | 0.1658 |
| HONG KAH | 610.0000 | 19.0000 | Low-Low | 0.4577 | 0.0330 | 0.1758 |
| TRAFALGAR | 610.0000 | 16.0000 | Low-Low | 0.4494 | 0.0350 | 0.1758 |
| BRICKWORKS | 610.0000 | 10.0000 | Low-Low | 0.4518 | 0.0360 | 0.1758 |
| BOON LAY PLACE | 610.0000 | 9.0000 | Low-Low | 0.4400 | 0.0390 | 0.1861 |
| SAUJANA | 610.0000 | 7.0000 | Low-Low | 0.4542 | 0.0430 | 0.2007 |
| BUKIT BATOK CENTRAL | 640.0000 | 7.0000 | Low-Low | 0.4150 | 0.0490 | 0.2229 |

Note: local results involve multiple comparisons. Prefer `local_fdr_q` / `lisa_cluster_fdr05` when confirmatory control of false discoveries is required. Results describe subzone medians, not individual-centre fee similarity.
