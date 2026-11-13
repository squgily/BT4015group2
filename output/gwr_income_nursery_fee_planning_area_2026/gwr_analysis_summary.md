# Geographically weighted regression: household income and nursery fees

## Model

- Observations: **30 planning areas** matched across the income and nursery-fee datasets (fees: canonical 2026 centre layer via 3.1).
- Outcome: median monthly full-day nursery fee (SGD).
- Predictor: estimated median monthly household income, expressed per SGD 1,000.
- Kernel: adaptive bi-square over planning-area centroids.
- Bandwidth selection: minimum leave-one-out cross-validation (LOOCV) RMSE; AICc is not used to choose the bandwidth.
- Selected bandwidth: **14 nearest neighbours**, excluding the target area itself.
- Minimum leave-one-out RMSE: **274.7 SGD**.
- The model is descriptive; it does not establish that household income causes nursery fees.

## Global OLS versus GWR

| Metric | Global OLS | GWR |
| --- | ---: | ---: |
| R-squared | 0.626 | 0.861 |
| RMSE (SGD) | 340.7 | 207.4 |
| AICc | 439.4 | 429.2 |
| Effective parameters | 2.0 | 8.29 |

The GWR model **strongly improves** on global OLS by the conventional AICc comparison (OLS minus GWR = **10.2**). Its in-sample RMSE is **39.1%** lower. Because GWR is more flexible, the AICc and leave-one-out results should be considered alongside the in-sample fit.

## Spatial variation in the income coefficient

- Local slope range: **$6.4 to $157.5** change in median fee per additional SGD 1,000 of median income.
- Median local slope: **$103.9 per SGD 1,000**.
- Positive local slopes: **30 of 30** planning areas.
- Effective residual degrees of freedom used for approximate local t-tests: **19.24**.
- Areas with unadjusted two-sided p <= 0.05: **21**.
- Areas remaining significant at 5% after Benjamini-Hochberg FDR correction across the 30 income-slope tests: **20**.
- The smallest non-significant adjusted income-slope p-value is **0.070**.

### Monte Carlo spatial-variability test

- H0: the coefficient is spatially stationary; its observed across-area variability is no greater than expected after randomly reassigning locations.
- H1: the coefficient exhibits greater spatial variability than expected under random location assignment.
- Method: **999 coordinate randomisations**, refitting GWR each time at the fixed, selected bandwidth of **14 neighbours**. The test statistic is the sample standard deviation of the local coefficients, and the pseudo p-value uses the upper tail with the plus-one correction.

| Parameter | Observed SD | Null mean SD | Null 95th percentile | Pseudo p-value | Decision at 5% |
| --- | ---: | ---: | ---: | ---: | --- |
| Intercept | 278.62 | 301.73 | 470.93 | 0.560 | fail to reject H0 |
| Income slope | 41.98 | 37.39 | 63.09 | 0.345 | fail to reject H0 |

The income-slope test is the primary test of the research hypothesis. Local t-values test whether individual coefficients differ from zero; they do **not** test whether the coefficient varies significantly across space.

Strongest local coefficients:

- Geylang: $157.5 per $1,000 income (local R-squared 0.641)
- Marine Parade: $150.6 per $1,000 income (local R-squared 0.702)
- Bedok: $132.4 per $1,000 income (local R-squared 0.252)
- Bukit Panjang: $122.0 per $1,000 income (local R-squared 0.853)
- Toa Payoh: $120.0 per $1,000 income (local R-squared 0.637)

Weakest local coefficients:

- Pasir Ris: $6.4 per $1,000 income (local R-squared 0.001)
- Punggol: $9.1 per $1,000 income (local R-squared 0.012)
- Sembawang: $12.5 per $1,000 income (local R-squared 0.041)
- Sengkang: $22.1 per $1,000 income (local R-squared 0.051)
- Tampines: $37.4 per $1,000 income (local R-squared 0.027)

## Residual spatial autocorrelation

- Global OLS residual Moran's I: **0.275**, permutation p = **0.009**.
- GWR residual Moran's I: **-0.213**, permutation p = **0.035**.

## Limitations

There are only 30 matched planning areas and one explanatory variable. Local estimates can therefore be sensitive to bandwidth choice, influential high-fee areas, and the grouped-income interpolation. The nursery fees are the October 2026 ECDA listing; the income CSV does not state its reference year. Provider type, subsidies, commercial rents, programme characteristics, and centre composition remain omitted variables. Interpret the coefficient surfaces as exploratory spatial heterogeneity rather than causal effects.
