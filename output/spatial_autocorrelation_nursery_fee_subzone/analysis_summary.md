# Spatial autocorrelation of full-day SC nursery fees by subzone

## Method

- Source points: `output/childcare_centres_2026.gpkg` layer `centres` (canonical 2026 layer); null `FULL_DAY_SC_NURSERY_FEE` records and the one S$0 fee excluded.
- Spatial unit: 2019 subzones (`SUBZONE_N`) from `data/MasterPlanSubZones_2019.geojson`.
- Area statistic: median centre fee in SGD. The centre count and mean are retained for context.
- Spatial weights: symmetric 4-nearest-neighbour graph based on area-weighted subzone centroids, row-standardised.
- Inference: 999 random permutations, seed 4015. Local p-values are exploratory; Benjamini-Hochberg FDR q-values are also reported.

## Data coverage

- Centre features: 1,796
- Excluded null/invalid fees: 210
- Valid fee points outside a subzone polygon: 0
- Centres analysed: 1,586
- Subzones with at least one valid centre: 232

## Global Moran's I

- Observed I: **0.4455**
- Randomisation expectation: **-0.0043**
- Permutation pseudo-p: **0.0010**

The area-level median fees show **positive spatial autocorrelation**, and the result is **statistically significant at the 5% level** under this weights specification.

## Local Moran clusters (raw permutation p < 0.05)

| subzone | median_fee_sgd | centre_count | lisa_cluster_p05 | local_moran_i | local_permutation_p | local_fdr_q |
| --- | --- | --- | --- | --- | --- | --- |
| BOULEVARD | 2480.0000 | 3.0000 | High-High | 3.7625 | 0.0010 | 0.0258 |
| CAIRNHILL | 2200.0000 | 1.0000 | High-High | 3.3686 | 0.0010 | 0.0258 |
| CLIFFORD PIER | 2450.0000 | 1.0000 | High-High | 3.2752 | 0.0010 | 0.0258 |
| GOODWOOD PARK | 2129.5000 | 2.0000 | High-High | 2.1279 | 0.0010 | 0.0258 |
| LEONIE HILL | 3355.0000 | 2.0000 | High-High | 4.5898 | 0.0010 | 0.0258 |
| MALCOLM | 1580.0000 | 1.0000 | High-High | 0.9980 | 0.0010 | 0.0258 |
| MARINA CENTRE | 2325.0000 | 4.0000 | High-High | 3.7366 | 0.0010 | 0.0258 |
| MARINA SOUTH | 3010.0000 | 1.0000 | High-High | 5.3548 | 0.0010 | 0.0258 |
| NEWTON CIRCUS | 2370.0000 | 1.0000 | High-High | 2.5766 | 0.0010 | 0.0258 |
| CENTRAL SUBZONE | 2500.0000 | 1.0000 | High-High | 2.9181 | 0.0020 | 0.0387 |
| OXLEY | 2059.1750 | 4.0000 | High-High | 2.5047 | 0.0020 | 0.0387 |
| RAFFLES PLACE | 2470.0000 | 3.0000 | High-High | 3.0846 | 0.0020 | 0.0387 |
| BOAT QUAY | 2200.0000 | 1.0000 | High-High | 2.0578 | 0.0030 | 0.0409 |
| CITY HALL | 3000.0000 | 1.0000 | High-High | 4.4509 | 0.0030 | 0.0409 |
| HILLCREST | 1946.5000 | 6.0000 | High-High | 1.8575 | 0.0030 | 0.0409 |
| SWISS CLUB | 2224.7700 | 3.0000 | High-High | 2.3485 | 0.0030 | 0.0409 |
| VICTORIA | 1925.0000 | 2.0000 | High-High | 1.3015 | 0.0060 | 0.0663 |
| NASSIM | 2016.0000 | 5.0000 | High-High | 1.9057 | 0.0070 | 0.0738 |
| HOLLAND ROAD | 2050.0000 | 3.0000 | High-High | 1.6029 | 0.0080 | 0.0807 |
| INSTITUTION HILL | 1720.0000 | 1.0000 | High-High | 1.1549 | 0.0100 | 0.0928 |
| CORONATION ROAD | 2200.0000 | 5.0000 | High-High | 2.0680 | 0.0120 | 0.1024 |
| ANSON | 1800.0000 | 1.0000 | High-High | 0.9971 | 0.0150 | 0.1024 |
| CHATSWORTH | 1821.5300 | 2.0000 | High-High | 1.0499 | 0.0220 | 0.1187 |
| DUNEARN | 2345.0000 | 2.0000 | High-High | 1.9666 | 0.0260 | 0.1206 |
| MOULMEIN | 2080.0000 | 7.0000 | High-High | 1.3570 | 0.0330 | 0.1409 |
| FARRER COURT | 2000.0000 | 1.0000 | High-High | 1.0110 | 0.0340 | 0.1409 |
| ROBERTSON QUAY | 2200.0000 | 3.0000 | High-High | 1.3147 | 0.0370 | 0.1431 |
| CLEANTECH | 1750.0000 | 1.0000 | High-Low | -0.6900 | 0.0150 | 0.1024 |
| BRADDELL | 1760.0000 | 4.0000 | High-Low | -0.6366 | 0.0370 | 0.1431 |
| PHILLIP | 650.0000 | 1.0000 | Low-High | -0.9486 | 0.0030 | 0.0409 |
| GHIM MOH | 650.0000 | 5.0000 | Low-High | -0.6939 | 0.0240 | 0.1206 |
| TEBAN GARDENS | 650.0000 | 5.0000 | Low-High | -0.7001 | 0.0430 | 0.1512 |
| HENDERSON HILL | 610.0000 | 2.0000 | Low-High | -0.7003 | 0.0470 | 0.1604 |
| SELETAR | 650.0000 | 1.0000 | Low-Low | 0.6004 | 0.0040 | 0.0516 |
| PARK | 610.0000 | 5.0000 | Low-Low | 0.6399 | 0.0060 | 0.0663 |
| WOODLANDS REGIONAL CENTRE | 650.0000 | 3.0000 | Low-Low | 0.5836 | 0.0060 | 0.0663 |
| PUNGGOL FIELD | 630.0000 | 16.0000 | Low-Low | 0.6108 | 0.0090 | 0.0870 |
| MATILDA | 630.0000 | 12.0000 | Low-Low | 0.6108 | 0.0120 | 0.1024 |
| FAJAR | 650.0000 | 9.0000 | Low-Low | 0.5948 | 0.0130 | 0.1024 |
| MIDVIEW | 630.0000 | 12.0000 | Low-Low | 0.5991 | 0.0140 | 0.1024 |
| YUHUA WEST | 755.0000 | 2.0000 | Low-Low | 0.4582 | 0.0140 | 0.1024 |
| SAUJANA | 650.0000 | 9.0000 | Low-Low | 0.5881 | 0.0150 | 0.1024 |
| SENJA | 610.0000 | 6.0000 | Low-Low | 0.6141 | 0.0150 | 0.1024 |
| CHOA CHU KANG NORTH | 650.0000 | 11.0000 | Low-Low | 0.5836 | 0.0160 | 0.1061 |
| NORTHSHORE | 610.0000 | 15.0000 | Low-Low | 0.6423 | 0.0170 | 0.1066 |
| PUNGGOL TOWN CENTRE | 610.0000 | 12.0000 | Low-Low | 0.6351 | 0.0170 | 0.1066 |
| BALESTIER | 650.0000 | 10.0000 | Low-Low | 0.5948 | 0.0180 | 0.1099 |
| TOWNSVILLE | 610.0000 | 6.0000 | Low-Low | 0.6302 | 0.0210 | 0.1187 |
| COMPASSVALE | 650.0000 | 9.0000 | Low-Low | 0.5881 | 0.0220 | 0.1187 |
| PENG SIANG | 630.0000 | 10.0000 | Low-Low | 0.6069 | 0.0220 | 0.1187 |
| WATERWAY EAST | 610.0000 | 21.0000 | Low-Low | 0.6363 | 0.0220 | 0.1187 |
| PLANTATION | 610.0000 | 4.0000 | Low-Low | 0.6131 | 0.0230 | 0.1206 |
| BRICKWORKS | 610.0000 | 12.0000 | Low-Low | 0.6254 | 0.0250 | 0.1206 |
| GREENWOOD PARK | 650.0000 | 1.0000 | Low-Low | 0.5892 | 0.0250 | 0.1206 |
| RIVERVALE | 650.0000 | 21.0000 | Low-Low | 0.5836 | 0.0260 | 0.1206 |
| WOODGROVE | 650.0000 | 12.0000 | Low-Low | 0.5892 | 0.0260 | 0.1206 |
| CHOA CHU KANG CENTRAL | 610.0000 | 7.0000 | Low-Low | 0.6109 | 0.0300 | 0.1338 |
| HONG KAH | 630.0000 | 16.0000 | Low-Low | 0.5865 | 0.0300 | 0.1338 |
| BUKIT BATOK WEST | 650.0000 | 3.0000 | Low-Low | 0.5565 | 0.0340 | 0.1409 |
| HOUGANG EAST | 610.0000 | 7.0000 | Low-Low | 0.6157 | 0.0340 | 0.1409 |
| YEW TEE | 650.0000 | 9.0000 | Low-Low | 0.5836 | 0.0360 | 0.1431 |
| SENGKANG TOWN CENTRE | 650.0000 | 23.0000 | Low-Low | 0.5791 | 0.0370 | 0.1431 |
| BUKIT BATOK CENTRAL | 650.0000 | 9.0000 | Low-Low | 0.5701 | 0.0380 | 0.1445 |
| TECK WHYE | 650.0000 | 10.0000 | Low-Low | 0.4899 | 0.0390 | 0.1450 |
| ANCHORVALE | 610.0000 | 17.0000 | Low-Low | 0.6205 | 0.0400 | 0.1450 |
| KIM KEAT | 610.0000 | 5.0000 | Low-Low | 0.5687 | 0.0400 | 0.1450 |
| KANGKAR | 650.0000 | 10.0000 | Low-Low | 0.5836 | 0.0420 | 0.1499 |
| BOON LAY PLACE | 610.0000 | 8.0000 | Low-Low | 0.4486 | 0.0440 | 0.1524 |

Note: local results involve multiple comparisons. Prefer `local_fdr_q` / `lisa_cluster_fdr05` when confirmatory control of false discoveries is required. Results describe subzone medians, not individual-centre fee similarity.
