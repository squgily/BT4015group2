# Spatial autocorrelation of child population density (ages 0-6) by subzone

## Method

- Variable: `child_density_0_6_km2` (children aged 0-6 per km2, from subzone_stats.csv)
- child_0_6 = child_0_4 + per-subzone share_5_6 * child_5_9 (fallback: flat 40%).
- Spatial unit: 2019 subzones restricted to 159 HDB subzones (has_hdb == True).
- Spatial weights: symmetric 4-nearest-neighbour graph on EPSG:3414 centroids, row-standardised.
- Inference: 999 random permutations, seed 4015.
  Local p-values use conditional randomisation; Benjamini-Hochberg FDR q-values also reported.

## Global Moran's I

- Observed I: **0.1867**
- Expected I (under randomisation): **-0.0063**
- Permutation pseudo-p: **0.0010**

Child density (ages 0-6) shows **positive spatial autocorrelation** across HDB subzones,
and the result is **statistically significant at the 5% level**.

## Local Moran clusters (raw permutation p < 0.05)

            SUBZONE_N    PLN_AREA_N  child_density_0_6_km2 lisa_cluster_p05  local_moran_i  local_permutation_p  local_fdr_q
        PUNGGOL FIELD       PUNGGOL            1513.642600        High-High       1.251424                0.002     0.079500
  PUNGGOL TOWN CENTRE       PUNGGOL            1318.729611        High-High       0.929039                0.003     0.079500
           NORTHSHORE       PUNGGOL            2381.700038        High-High       2.752746                0.010     0.170357
        WATERWAY EAST       PUNGGOL            2604.377312        High-High       2.522689                0.013     0.170357
              MATILDA       PUNGGOL            2514.250559        High-High       2.537642                0.014     0.170357
            RIVERVALE      SENGKANG            1865.447282        High-High       1.193615                0.017     0.178875
 SENGKANG TOWN CENTRE      SENGKANG            2043.521921        High-High       1.566632                0.020     0.187059
           ANCHORVALE      SENGKANG            1857.722829        High-High       1.459707                0.023     0.192474
            TECK WHYE CHOA CHU KANG            1048.929833        High-High       0.109184                0.039     0.250731
              SAUJANA BUKIT PANJANG            1817.907722        High-High       0.939593                0.041     0.250731
       CLEMENTI NORTH      CLEMENTI            1775.881242         High-Low      -0.806668                0.015     0.170357
                 PARK        TENGAH             842.951529         Low-High      -0.147931                0.003     0.079500
              BANGKIT BUKIT PANJANG             841.599879         Low-High      -0.142588                0.009     0.170357
          COMPASSVALE      SENGKANG             813.829988         Low-High      -0.150750                0.018     0.178875
            NORTHLAND        YISHUN             668.431342         Low-High      -0.298089                0.039     0.250731
               GUILIN   BUKIT BATOK             254.727742         Low-High      -0.846905                0.041     0.250731
CHOA CHU KANG CENTRAL CHOA CHU KANG             461.496869         Low-High      -0.528488                0.047     0.263172
               JELEBU BUKIT PANJANG             861.127669         Low-High      -0.067939                0.048     0.263172
         LITTLE INDIA        ROCHOR             301.828712          Low-Low       0.722455                0.001     0.079500
          SUNGEI ROAD        ROCHOR             756.468689          Low-Low       0.193495                0.002     0.079500
          FARRER PARK        ROCHOR             302.603401          Low-Low       0.718046                0.003     0.079500
             CRAWFORD       KALLANG             746.424242          Low-Low       0.209638                0.009     0.170357
         KAMPONG JAVA       KALLANG             234.693144          Low-Low       0.862128                0.012     0.170357
            BENCOOLEN        ROCHOR              82.032385          Low-Low       0.904698                0.015     0.170357
             VICTORIA        ROCHOR             205.367275          Low-Low       0.805355                0.022     0.192474
                BUGIS DOWNTOWN CORE              49.968811          Low-Low       0.790717                0.033     0.249857
             LAVENDER       KALLANG             294.612713          Low-Low       0.563531                0.033     0.249857
        LORONG AH SOO       HOUGANG             420.425973          Low-Low       0.477164                0.039     0.250731
           KAKI BUKIT         BEDOK             462.105616          Low-Low       0.440171                0.046     0.263172

Note: local results involve multiple comparisons. Prefer `local_fdr_q` / `lisa_cluster_fdr05`
for confirmatory inference.
