# Spatial autocorrelation of full-day SC nursery fees by subzone

## Method

- Source points: `data/ChildCareServices_2021.geojson`; null/non-numeric `FULL_DAY_SC_NURSERY_FEE` records excluded.
- Spatial unit: 2019 subzones (`SUBZONE_N`) from `data/MasterPlanSubZones_2019.geojson`.
- Area statistic: mean centre fee in SGD. The centre count and median are retained for context.
- Spatial weights: symmetric 4-nearest-neighbour graph based on area-weighted subzone centroids, row-standardised.
- Inference: 999 random permutations, seed 4015. Local p-values are exploratory; Benjamini-Hochberg FDR q-values are also reported.

## Data coverage

- Centre features: 1,925
- Excluded null/invalid fees: 562
- Valid fee points outside a subzone polygon: 0
- Centres analysed: 1,363
- Subzones with at least one valid centre: 210

## Global Moran's I

- Observed I: **0.3979**
- Randomisation expectation: **-0.0048**
- Permutation pseudo-p: **0.0010**

The area-level mean fees show **positive spatial autocorrelation**, and the result is **statistically significant at the 5% level** under this weights specification.

## Local Moran clusters (raw permutation p < 0.05)

| subzone | mean_fee_sgd | centre_count | lisa_cluster_p05 | local_moran_i | local_permutation_p | local_fdr_q |
| --- | --- | --- | --- | --- | --- | --- |
| BOULEVARD | 2326.6667 | 3.0000 | High-High | 5.5453 | 0.0010 | 0.0175 |
| CAIRNHILL | 2200.0000 | 1.0000 | High-High | 5.1376 | 0.0010 | 0.0175 |
| GOODWOOD PARK | 2105.0000 | 2.0000 | High-High | 3.7062 | 0.0010 | 0.0175 |
| HOLLAND ROAD | 2175.0000 | 2.0000 | High-High | 2.9425 | 0.0010 | 0.0175 |
| LEONIE HILL | 2520.0000 | 2.0000 | High-High | 6.7278 | 0.0010 | 0.0175 |
| MOUNT EMILY | 1980.0000 | 2.0000 | High-High | 3.3017 | 0.0010 | 0.0175 |
| NASSIM | 1936.5000 | 4.0000 | High-High | 3.2382 | 0.0010 | 0.0175 |
| NEWTON CIRCUS | 2370.0000 | 1.0000 | High-High | 4.4263 | 0.0010 | 0.0175 |
| OXLEY | 2950.0000 | 2.0000 | High-High | 7.9180 | 0.0010 | 0.0175 |
| ROBERTSON QUAY | 1990.0000 | 2.0000 | High-High | 2.9581 | 0.0010 | 0.0175 |
| SWISS CLUB | 1976.2520 | 5.0000 | High-High | 3.2556 | 0.0010 | 0.0175 |
| CORONATION ROAD | 1940.7980 | 5.0000 | High-High | 3.0989 | 0.0020 | 0.0280 |
| INSTITUTION HILL | 2470.0000 | 1.0000 | High-High | 3.9726 | 0.0020 | 0.0280 |
| MALCOLM | 1580.0000 | 1.0000 | High-High | 1.8534 | 0.0020 | 0.0280 |
| HILLCREST | 1830.3125 | 4.0000 | High-High | 2.6194 | 0.0050 | 0.0618 |
| MOULMEIN | 1608.2250 | 2.0000 | High-High | 1.4476 | 0.0140 | 0.1470 |
| VICTORIA | 1925.0000 | 2.0000 | High-High | 2.0213 | 0.0200 | 0.1615 |
| ANAK BUKIT | 1367.9175 | 12.0000 | High-High | 0.6103 | 0.0260 | 0.1655 |
| FARRER COURT | 2000.0000 | 1.0000 | High-High | 1.5291 | 0.0300 | 0.1703 |
| SELETAR | 1900.0000 | 1.0000 | High-Low | -1.3771 | 0.0010 | 0.0175 |
| WOODLANDS REGIONAL CENTRE | 1125.0000 | 2.0000 | High-Low | -0.0977 | 0.0080 | 0.0933 |
| UPPER THOMSON | 1279.1667 | 12.0000 | High-Low | -0.3104 | 0.0360 | 0.1800 |
| BUKIT MERAH | 1215.0000 | 2.0000 | High-Low | -0.1657 | 0.0370 | 0.1807 |
| PASIR RIS PARK | 1650.0000 | 2.0000 | High-Low | -0.7965 | 0.0480 | 0.2100 |
| BUKIT HO SWEE | 957.5000 | 4.0000 | Low-High | -0.1998 | 0.0200 | 0.1615 |
| KAMPONG JAVA | 982.5000 | 4.0000 | Low-High | -0.1571 | 0.0250 | 0.1641 |
| PEARL'S HILL | 630.0000 | 2.0000 | Low-High | -0.9211 | 0.0250 | 0.1641 |
| CRAWFORD | 610.0000 | 3.0000 | Low-High | -0.8833 | 0.0300 | 0.1703 |
| MARINE PARADE | 804.2838 | 8.0000 | Low-High | -0.4327 | 0.0350 | 0.1793 |
| FAJAR | 661.0000 | 10.0000 | Low-Low | 0.6368 | 0.0040 | 0.0525 |
| TOWNSVILLE | 615.0000 | 8.0000 | Low-Low | 0.6545 | 0.0120 | 0.1326 |
| BANGKIT | 610.0000 | 5.0000 | Low-Low | 0.6811 | 0.0160 | 0.1600 |
| NORTHSHORE | 890.0000 | 4.0000 | Low-Low | 0.2499 | 0.0180 | 0.1615 |
| BOON LAY PLACE | 674.4278 | 9.0000 | Low-Low | 0.4928 | 0.0190 | 0.1615 |
| SENGKANG TOWN CENTRE | 709.4542 | 24.0000 | Low-Low | 0.5086 | 0.0190 | 0.1615 |
| YUNNAN | 864.7059 | 17.0000 | Low-Low | 0.2780 | 0.0220 | 0.1641 |
| RIVERVALE | 819.6332 | 19.0000 | Low-Low | 0.3444 | 0.0230 | 0.1641 |
| TRAFALGAR | 622.5000 | 16.0000 | Low-Low | 0.6036 | 0.0240 | 0.1641 |
| COMPASSVALE | 627.1429 | 7.0000 | Low-Low | 0.6055 | 0.0250 | 0.1641 |
| TAMAN JURONG | 753.8462 | 13.0000 | Low-Low | 0.4165 | 0.0270 | 0.1668 |
| BUKIT BATOK WEST | 676.0000 | 5.0000 | Low-Low | 0.5401 | 0.0290 | 0.1703 |
| SENJA | 610.0000 | 3.0000 | Low-Low | 0.5540 | 0.0310 | 0.1713 |
| JURONG WEST CENTRAL | 645.7143 | 21.0000 | Low-Low | 0.5286 | 0.0320 | 0.1723 |
| TECK WHYE | 999.7778 | 9.0000 | Low-Low | 0.0629 | 0.0330 | 0.1733 |
| WENYA | 717.5000 | 4.0000 | Low-Low | 0.4437 | 0.0380 | 0.1814 |
| BRICKWORKS | 687.0000 | 10.0000 | Low-Low | 0.4607 | 0.0410 | 0.1913 |
| SAUJANA | 657.1429 | 7.0000 | Low-Low | 0.5301 | 0.0430 | 0.1963 |
| PUNGGOL FIELD | 627.5000 | 16.0000 | Low-Low | 0.5151 | 0.0480 | 0.2100 |
| YUHUA WEST | 706.6667 | 3.0000 | Low-Low | 0.4591 | 0.0490 | 0.2100 |

Note: local results involve multiple comparisons. Prefer `local_fdr_q` / `lisa_cluster_fdr05` when confirmatory control of false discoveries is required. Results describe subzone means, not individual-centre fee similarity.
