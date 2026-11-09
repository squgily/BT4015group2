# Geographically weighted regression: household income and nursery fees

## Model

- Observations: **30 planning areas** matched across the income and nursery-fee datasets.
- Outcome: median monthly full-day nursery fee (SGD).
- Predictor: estimated median monthly household income, expressed per SGD 1,000.
- Kernel: adaptive bi-square over planning-area centroids.
- Bandwidth selection: minimum leave-one-out cross-validation (LOOCV) RMSE; AICc is not used to choose the bandwidth.
- Selected bandwidth: **14 nearest neighbours**, excluding the target area itself.
- Minimum leave-one-out RMSE: **245.5 SGD**.
- The model is descriptive; it does not establish that household income causes nursery fees.

## Global OLS versus GWR

| Metric | Global OLS | GWR |
| --- | ---: | ---: |
| R-squared | 0.721 | 0.879 |
| RMSE (SGD) | 258.0 | 169.8 |
| AICc | 422.8 | 417.2 |
| Effective parameters | 2.0 | 8.29 |

The GWR model **moderately improves** on global OLS by the conventional AICc comparison (OLS minus GWR = **5.6**). Its in-sample RMSE is **34.2%** lower. Because GWR is more flexible, the AICc and leave-one-out results should be considered alongside the in-sample fit.

## Spatial variation in the income coefficient

- Local slope range: **$5.3 to $124.9** change in median fee per additional SGD 1,000 of median income.
- Median local slope: **$104.1 per SGD 1,000**.
- Positive local slopes: **30 of 30** planning areas.
- Effective residual degrees of freedom used for approximate local t-tests: **19.24**.
- Areas with unadjusted two-sided p <= 0.05: **21**.
- Areas remaining significant at 5% after Benjamini-Hochberg FDR correction across the 30 income-slope tests: **21**.
- The smallest non-significant adjusted income-slope p-value is **0.571**.

### Monte Carlo spatial-variability test

- H0: the coefficient is spatially stationary; its observed across-area variability is no greater than expected after randomly reassigning locations.
- H1: the coefficient exhibits greater spatial variability than expected under random location assignment.
- Method: **999 coordinate randomisations**, refitting GWR each time at the fixed, selected bandwidth of **14 neighbours**. The test statistic is the sample standard deviation of the local coefficients, and the pseudo p-value uses the upper tail with the plus-one correction.

| Parameter | Observed SD | Null mean SD | Null 95th percentile | Pseudo p-value | Decision at 5% |
| --- | ---: | ---: | ---: | ---: | --- |
| Intercept | 302.87 | 263.54 | 376.82 | 0.292 | fail to reject H0 |
| Income slope | 44.96 | 34.30 | 51.28 | 0.164 | fail to reject H0 |

The income-slope test is the primary test of the research hypothesis. Local t-values test whether individual coefficients differ from zero; they do **not** test whether the coefficient varies significantly across space.

Strongest local coefficients:

- Marine Parade: $124.9 per $1,000 income (local R-squared 0.684)
- Geylang: $124.5 per $1,000 income (local R-squared 0.581)
- Choa Chu Kang: $121.2 per $1,000 income (local R-squared 0.908)
- Bukit Panjang: $115.7 per $1,000 income (local R-squared 0.923)
- Bukit Batok: $113.6 per $1,000 income (local R-squared 0.923)

Weakest local coefficients:

- Punggol: $5.3 per $1,000 income (local R-squared 0.142)
- Sembawang: $5.3 per $1,000 income (local R-squared 0.183)
- Sengkang: $5.4 per $1,000 income (local R-squared 0.195)
- Serangoon: $8.3 per $1,000 income (local R-squared 0.057)
- Hougang: $8.9 per $1,000 income (local R-squared 0.013)

## Residual spatial autocorrelation

- Global OLS residual Moran's I: **0.223**, permutation p = **0.012**.
- GWR residual Moran's I: **-0.160**, permutation p = **0.078**.

## Limitations

There are only 30 matched planning areas and one explanatory variable. Local estimates can therefore be sensitive to bandwidth choice, influential high-fee areas, and the grouped-income interpolation. The nursery data are explicitly from 2021, while the income CSV does not state its reference year. Provider type, subsidies, commercial rents, programme characteristics, and centre composition remain omitted variables. Interpret the coefficient surfaces as exploratory spatial heterogeneity rather than causal effects.
