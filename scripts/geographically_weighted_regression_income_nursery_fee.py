"""Geographically weighted regression of nursery fees on household income.

The analysis uses an adaptive bi-square kernel over planning-area centroids.
Candidate neighbour counts are compared solely using leave-one-out
cross-validation (LOOCV) RMSE.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, TwoSlopeNorm
import numpy as np
import pandas as pd
from scipy.stats import t as student_t

from household_income_nursery_fee_regression import ols_fit, prepare_data
from spatial_autocorrelation_nursery_fee import (
    add_planning_area_boundaries,
    feature_patches,
    geometry_area_centroid,
    knn_weights,
    load_geojson,
    moran_i,
    prepare_subzones,
    set_map_style,
)


def local_xy_km(longitude: np.ndarray, latitude: np.ndarray) -> np.ndarray:
    """Convert Singapore lon/lat to a local kilometre approximation."""
    lon0 = float(longitude.mean())
    lat0 = float(latitude.mean())
    x = (longitude - lon0) * 111.32 * math.cos(math.radians(lat0))
    y = (latitude - lat0) * 110.57
    return np.column_stack([x, y])


def pairwise_distances(coordinates: np.ndarray) -> np.ndarray:
    delta = coordinates[:, None, :] - coordinates[None, :, :]
    return np.sqrt(np.sum(delta**2, axis=2))


def adaptive_bisquare_weights(
    distances: np.ndarray, neighbour_count: int, exclude_self: bool = False
) -> tuple[np.ndarray, float]:
    """Return adaptive bi-square weights and the local bandwidth distance."""
    ordered = np.sort(distances[distances > 0] if exclude_self else distances)
    if neighbour_count > len(ordered):
        raise ValueError("Neighbour count exceeds available observations")
    bandwidth = float(ordered[neighbour_count - 1]) * (1.0 + 1e-9)
    weights = np.where(
        distances < bandwidth,
        (1.0 - (distances / bandwidth) ** 2) ** 2,
        0.0,
    )
    return weights, bandwidth


def weighted_fit(
    design: np.ndarray, outcome: np.ndarray, weights: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    xtw = design.T * weights
    inverse = np.linalg.pinv(xtw @ design)
    beta = inverse @ xtw @ outcome
    return beta, inverse, xtw


def information_criteria(sse: float, n: int, effective_parameters: float) -> tuple[float, float]:
    sigma2_ml = max(sse / n, np.finfo(float).tiny)
    aic = n * (math.log(2 * math.pi * sigma2_ml) + 1) + 2 * effective_parameters
    denominator = n - effective_parameters - 1
    if denominator <= 0:
        return aic, math.inf
    aicc = aic + (2 * effective_parameters * (effective_parameters + 1)) / denominator
    return aic, aicc


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    """Return Benjamini-Hochberg FDR-adjusted p-values."""
    values = np.asarray(p_values, dtype=float)
    if values.ndim != 1 or np.any(~np.isfinite(values)):
        raise ValueError("Benjamini-Hochberg requires finite one-dimensional p-values")
    order = np.argsort(values)
    ranked = values[order]
    scale = len(values) / np.arange(1, len(values) + 1)
    adjusted_ranked = np.minimum.accumulate((ranked * scale)[::-1])[::-1]
    adjusted = np.empty_like(adjusted_ranked)
    adjusted[order] = np.clip(adjusted_ranked, 0.0, 1.0)
    return adjusted


def fit_gwr(
    design: np.ndarray,
    outcome: np.ndarray,
    distance_matrix: np.ndarray,
    neighbour_count: int,
) -> dict[str, np.ndarray | float]:
    n, predictors = design.shape
    coefficients = np.empty((n, predictors))
    fitted = np.empty(n)
    bandwidth_km = np.empty(n)
    hat_matrix = np.empty((n, n))
    local_r2 = np.empty(n)
    covariance_factors = np.empty((n, predictors))

    for location in range(n):
        weights, bandwidth = adaptive_bisquare_weights(
            distance_matrix[location], neighbour_count + 1
        )
        beta, inverse, xtw = weighted_fit(design, outcome, weights)
        coefficients[location] = beta
        fitted[location] = design[location] @ beta
        bandwidth_km[location] = bandwidth
        hat_matrix[location] = design[location] @ inverse @ xtw

        local_predictions = design @ beta
        weight_sum = weights.sum()
        local_mean = float(weights @ outcome / weight_sum)
        local_sse = float(weights @ ((outcome - local_predictions) ** 2))
        local_tss = float(weights @ ((outcome - local_mean) ** 2))
        local_r2[location] = 1 - local_sse / local_tss if local_tss > 0 else np.nan

        middle = (design.T * (weights**2)) @ design
        covariance = inverse @ middle @ inverse
        covariance_factors[location] = np.maximum(np.diag(covariance), 0)

    residual = outcome - fitted
    sse = float(residual @ residual)
    tss = float(((outcome - outcome.mean()) ** 2).sum())
    trace_s = float(np.trace(hat_matrix))
    trace_sts = float(np.sum(hat_matrix**2))
    effective_df = max(n - 2 * trace_s + trace_sts, 1.0)
    sigma2 = sse / effective_df
    standard_errors = np.sqrt(covariance_factors * sigma2)
    t_values = np.divide(
        coefficients,
        standard_errors,
        out=np.full_like(coefficients, np.nan),
        where=standard_errors > 0,
    )
    aic, aicc = information_criteria(sse, n, trace_s)
    return {
        "coefficients": coefficients,
        "fitted": fitted,
        "residual": residual,
        "bandwidth_km": bandwidth_km,
        "local_r2": local_r2,
        "standard_errors": standard_errors,
        "t_values": t_values,
        "hat_matrix": hat_matrix,
        "trace_s": trace_s,
        "effective_df": effective_df,
        "sigma2": sigma2,
        "sse": sse,
        "r_squared": 1 - sse / tss,
        "adjusted_r_squared": 1 - (sse / tss) * (n - 1) / max(n - trace_s - 1, 1),
        "rmse": float(np.sqrt(sse / n)),
        "aic": aic,
        "aicc": aicc,
    }


def leave_one_out_rmse(
    design: np.ndarray,
    outcome: np.ndarray,
    distance_matrix: np.ndarray,
    neighbour_count: int,
) -> float:
    predictions = np.empty(len(outcome))
    for location in range(len(outcome)):
        distances = distance_matrix[location].copy()
        weights, _ = adaptive_bisquare_weights(
            distances, neighbour_count, exclude_self=True
        )
        weights[location] = 0.0
        beta, _, _ = weighted_fit(design, outcome, weights)
        predictions[location] = design[location] @ beta
    return float(np.sqrt(np.mean((outcome - predictions) ** 2)))


def select_bandwidth(
    design: np.ndarray,
    outcome: np.ndarray,
    distance_matrix: np.ndarray,
    minimum_neighbours: int,
) -> tuple[pd.DataFrame, dict[str, np.ndarray | float]]:
    rows = []
    models = {}
    for neighbours in range(minimum_neighbours, len(outcome)):
        model = fit_gwr(design, outcome, distance_matrix, neighbours)
        cv_rmse = leave_one_out_rmse(design, outcome, distance_matrix, neighbours)
        rows.append(
            {
                "adaptive_neighbours": neighbours,
                "aicc": float(model["aicc"]),
                "aic": float(model["aic"]),
                "effective_parameters_trace_s": float(model["trace_s"]),
                "rmse_sgd": float(model["rmse"]),
                "loocv_rmse_sgd": cv_rmse,
            }
        )
        models[neighbours] = model
    results = pd.DataFrame(rows)
    selected = int(
        results.loc[results["loocv_rmse_sgd"].idxmin(), "adaptive_neighbours"]
    )
    results["selected_by_loocv"] = results["adaptive_neighbours"].eq(selected)
    return results, models[selected]


def residual_moran_test(
    residuals: np.ndarray,
    coordinates_lonlat: np.ndarray,
    permutations: int,
    seed: int,
) -> tuple[float, float]:
    _, weights = knn_weights(coordinates_lonlat, k=min(4, len(residuals) - 1))
    z = (residuals - residuals.mean()) / residuals.std(ddof=0)
    observed = moran_i(z, weights)
    rng = np.random.default_rng(seed)
    permuted = np.empty(permutations)
    for index in range(permutations):
        permuted[index] = moran_i(rng.permutation(z), weights)
    expected = -1 / (len(z) - 1)
    if observed >= expected:
        extreme = np.count_nonzero(permuted >= observed)
    else:
        extreme = np.count_nonzero(permuted <= observed)
    return observed, float((extreme + 1) / (permutations + 1))


def monte_carlo_spatial_variability(
    design: np.ndarray,
    outcome: np.ndarray,
    distance_matrix: np.ndarray,
    neighbour_count: int,
    observed_coefficients: np.ndarray,
    permutations: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Test whether GWR coefficients vary over space more than expected by chance.

    The null distribution is generated by randomly assigning the observed spatial
    coordinates to the attribute rows. Each randomisation is fitted using the
    bandwidth selected for the observed data. The upper-tail pseudo p-value asks
    whether the observed across-location coefficient SD is unusually large.
    """
    if permutations < 1:
        raise ValueError("At least one Monte Carlo permutation is required")

    parameter_names = ["intercept", "income_slope"]
    if observed_coefficients.shape[1] != len(parameter_names):
        raise ValueError("Update parameter_names for the supplied GWR design")

    observed_sd = np.std(observed_coefficients, axis=0, ddof=1)
    permuted_sd = np.empty((permutations, observed_coefficients.shape[1]))
    rng = np.random.default_rng(seed)
    n = len(outcome)

    for iteration in range(permutations):
        coordinate_order = rng.permutation(n)
        randomised_distances = distance_matrix[
            np.ix_(coordinate_order, coordinate_order)
        ]
        randomised_model = fit_gwr(
            design,
            outcome,
            randomised_distances,
            neighbour_count,
        )
        permuted_sd[iteration] = np.std(
            np.asarray(randomised_model["coefficients"]), axis=0, ddof=1
        )

    rows = []
    for column, parameter in enumerate(parameter_names):
        extreme = int(np.count_nonzero(permuted_sd[:, column] >= observed_sd[column]))
        p_value = float((extreme + 1) / (permutations + 1))
        rows.append(
            {
                "parameter": parameter,
                "observed_coefficient_sd": observed_sd[column],
                "null_mean_coefficient_sd": float(permuted_sd[:, column].mean()),
                "null_sd_coefficient_sd": float(permuted_sd[:, column].std(ddof=1)),
                "null_95th_percentile": float(
                    np.quantile(permuted_sd[:, column], 0.95)
                ),
                "extreme_permutations": extreme,
                "permutations": permutations,
                "pseudo_p_value_upper": p_value,
                "monte_carlo_se": math.sqrt(
                    p_value * (1.0 - p_value) / (permutations + 1)
                ),
                "significant_at_0_05": p_value <= 0.05,
                "selected_adaptive_neighbours": neighbour_count,
                "seed": seed,
            }
        )

    distribution = pd.DataFrame(
        {
            "permutation": np.arange(1, permutations + 1),
            "intercept_coefficient_sd": permuted_sd[:, 0],
            "income_slope_coefficient_sd": permuted_sd[:, 1],
        }
    )
    return pd.DataFrame(rows), distribution


def colour_norm(values: np.ndarray):
    finite = values[np.isfinite(values)]
    minimum, maximum = float(finite.min()), float(finite.max())
    if minimum < 0 < maximum:
        extent = max(abs(minimum), abs(maximum))
        return TwoSlopeNorm(vmin=-extent, vcenter=0, vmax=extent), "RdBu_r"
    if math.isclose(minimum, maximum):
        maximum = minimum + 1
    return Normalize(vmin=minimum, vmax=maximum), "viridis"


def draw_continuous_map(
    ax,
    fig,
    subzones,
    values_by_area: dict[str, float],
    title: str,
    colourbar_label: str,
    cmap: str | None = None,
    norm=None,
    colourbar_fraction: float = 0.035,
    colourbar_shrink: float = 1.0,
):
    patches, values = feature_patches(subzones, values_by_area)
    if norm is None:
        norm, inferred_cmap = colour_norm(values)
        cmap = cmap or inferred_cmap
    collection = matplotlib.collections.PatchCollection(
        patches,
        cmap=cmap,
        norm=norm,
        edgecolor="none",
        linewidth=0,
        antialiased=False,
    )
    collection.set_array(np.ma.masked_invalid(values))
    ax.add_collection(collection)
    add_planning_area_boundaries(ax, subzones)
    ax.autoscale_view()
    set_map_style(ax)
    ax.set_title(title, fontweight="bold")
    colourbar = fig.colorbar(
        collection,
        ax=ax,
        fraction=colourbar_fraction,
        shrink=colourbar_shrink,
        pad=0.01,
    )
    colourbar.set_label(colourbar_label)


def plot_fit_maps(data: pd.DataFrame, subzones: list[dict], output_path: Path) -> None:
    observed = data["median_fee_sgd"].to_numpy()
    fitted = data["gwr_fitted_fee_sgd"].to_numpy()
    residual = data["gwr_residual_sgd"].to_numpy()
    fee_norm = Normalize(vmin=float(min(observed.min(), fitted.min())), vmax=float(max(observed.max(), fitted.max())))
    residual_extent = max(abs(float(residual.min())), abs(float(residual.max())))
    residual_norm = TwoSlopeNorm(vmin=-residual_extent, vcenter=0, vmax=residual_extent)
    fig, axes = plt.subplots(1, 3, figsize=(20, 6.8))
    for axis, column, title in zip(
        axes[:2],
        ["median_fee_sgd", "gwr_fitted_fee_sgd"],
        ["Observed Median Nursery Fee", "GWR Fitted Nursery Fee"],
    ):
        draw_continuous_map(
            axis,
            fig,
            subzones,
            dict(zip(data["planning_area"], data[column])),
            title,
            "Monthly fee (SGD)",
            cmap="viridis_r",
            norm=fee_norm,
        )
    draw_continuous_map(
        axes[2],
        fig,
        subzones,
        dict(zip(data["planning_area"], residual)),
        "GWR Residual",
        "Observed minus fitted fee (SGD)",
        cmap="RdBu_r",
        norm=residual_norm,
    )
    fig.suptitle("GWR Fit Across Planning Areas", fontsize=16, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(output_path, dpi=240, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_bandwidth_selection(results: pd.DataFrame, output_path: Path) -> None:
    selected = results.loc[results["selected_by_loocv"]].iloc[0]
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    ax.plot(
        results["adaptive_neighbours"],
        results["loocv_rmse_sgd"],
        marker="o",
        color="#1B9E77",
    )
    ax.scatter(
        selected["adaptive_neighbours"],
        selected["loocv_rmse_sgd"],
        color="#D7191C",
        s=70,
        zorder=3,
        label=(
            f"Selected: {int(selected['adaptive_neighbours'])} neighbours "
            f"(RMSE {selected['loocv_rmse_sgd']:.1f})"
        ),
    )
    ax.set_title("Adaptive Bandwidth Selection by LOOCV", fontweight="bold")
    ax.set_xlabel("Adaptive nearest neighbours")
    ax.set_ylabel("RMSE")
    ax.grid(color="#E0E0E0", linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=240, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_monte_carlo_spatial_variability(
    results: pd.DataFrame,
    distribution: pd.DataFrame,
    output_path: Path,
) -> None:
    """Plot permutation null distributions for GWR coefficient variability."""
    panels = [
        (
            "intercept",
            "intercept_coefficient_sd",
            "Local intercept",
            "SD of local intercepts (SGD)",
        ),
        (
            "income_slope",
            "income_slope_coefficient_sd",
            "Local household-income coefficient",
            "SD of local slopes (SGD fee per SGD 1,000 income)",
        ),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6))
    for axis, (parameter, column, title, xlabel) in zip(axes, panels):
        row = results.loc[results["parameter"].eq(parameter)].iloc[0]
        null_values = distribution[column].to_numpy(dtype=float)
        axis.hist(
            null_values,
            bins=30,
            color="#7AA6C2",
            edgecolor="white",
            linewidth=0.6,
            alpha=0.9,
        )
        axis.axvline(
            row["null_95th_percentile"],
            color="#555555",
            linestyle="--",
            linewidth=1.8,
            label="95th percentile of null",
        )
        axis.axvline(
            row["observed_coefficient_sd"],
            color="#C51B2E",
            linewidth=2.6,
            label="Observed variability",
        )
        axis.set_title(title, fontweight="bold")
        axis.set_xlabel(xlabel)
        axis.set_ylabel("Permutation count")
        axis.text(
            0.97,
            0.95,
            f"Observed SD = {row['observed_coefficient_sd']:.2f}\n"
            f"Monte Carlo p = {row['pseudo_p_value_upper']:.3f}",
            transform=axis.transAxes,
            ha="right",
            va="top",
            bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "alpha": 0.92},
        )
        axis.grid(axis="y", color="#E5E5E5", linewidth=0.7)
        axis.spines[["top", "right"]].set_visible(False)
        axis.legend(frameon=False, loc="upper left")

    permutations = int(results["permutations"].iloc[0])
    neighbours = int(results["selected_adaptive_neighbours"].iloc[0])
    fig.suptitle(
        "Monte Carlo Test of GWR Coefficient Spatial Variability",
        fontsize=16,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.01,
        f"{permutations:,} coordinate randomisations; adaptive bi-square kernel; "
        f"fixed bandwidth of {neighbours} neighbours",
        ha="center",
        fontsize=10,
        color="#444444",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    fig.savefig(output_path, dpi=240, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_local_regression_lines(
    data: pd.DataFrame,
    ols: dict[str, np.ndarray | float],
    output_path: Path,
) -> None:
    """Overlay the 30 planning-area GWR lines on the observed data."""
    income = data["estimated_median_income_sgd"].to_numpy(dtype=float)
    fee = data["median_fee_sgd"].to_numpy(dtype=float)
    income_grid = np.linspace(float(income.min()), float(income.max()), 250)
    income_grid_thousands = income_grid / 1_000
    ordered = data.sort_values("planning_area_name").reset_index(drop=True)
    colours = plt.colormaps["turbo"](np.linspace(0.02, 0.98, len(ordered)))
    fig, ax = plt.subplots(figsize=(16, 9.5))

    for colour, row in zip(colours, ordered.itertuples()):
        local_line = (
            row.local_intercept_sgd
            + row.local_income_slope_sgd_per_1000 * income_grid_thousands
        )
        ax.plot(
            income_grid,
            local_line,
            color=colour,
            linewidth=1.55,
            alpha=0.78,
            label=row.planning_area_name,
        )
        ax.scatter(
            row.estimated_median_income_sgd,
            row.median_fee_sgd,
            s=28,
            color=colour,
            edgecolor="white",
            linewidth=0.45,
            zorder=3,
        )

    ax.plot(
        income_grid,
        float(ols["intercept"]) + float(ols["slope"]) * income_grid_thousands,
        color="#111111",
        linewidth=2.8,
        linestyle="--",
        label="Global OLS",
        zorder=4,
    )
    ax.set_title(
        "Local GWR Income x Nursery Fees by Planning Area",
        fontsize=16,
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("Estimated Median Monthly Household Income (SGD)")
    ax.set_ylabel("Predicted Median Monthly Nursery Fee (SGD)")
    ax.grid(color="#E4E4E4", linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(
        title="Planning area (point = observed value)",
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        ncol=2,
        frameon=False,
        fontsize=8.2,
        title_fontsize=9.5,
        handlelength=2.5,
        columnspacing=1.2,
    )
    fig.tight_layout(rect=(0.04, 0.04, 0.78, 1))
    fig.savefig(output_path, dpi=240, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_summary(
    path: Path,
    data: pd.DataFrame,
    selected_neighbours: int,
    gwr: dict[str, np.ndarray | float],
    ols: dict[str, np.ndarray | float],
    ols_rmse: float,
    ols_aicc: float,
    selected_loocv_rmse: float,
    spatial_variability: pd.DataFrame,
    gwr_residual_moran: tuple[float, float],
    ols_residual_moran: tuple[float, float],
) -> None:
    slopes = data["local_income_slope_sgd_per_1000"]
    local_t = data["local_income_slope_t"]
    local_p = data["local_income_slope_p_two_sided"]
    local_p_fdr = data["local_income_slope_p_fdr_bh"]
    inference_df = float(data["local_inference_effective_df"].iloc[0])
    delta_aicc = ols_aicc - float(gwr["aicc"])
    improvement = 100 * (ols_rmse - float(gwr["rmse"])) / ols_rmse
    best = data.nlargest(5, "local_income_slope_sgd_per_1000")
    weakest = data.nsmallest(5, "local_income_slope_sgd_per_1000")
    slope_variability = spatial_variability.loc[
        spatial_variability["parameter"].eq("income_slope")
    ].iloc[0]
    intercept_variability = spatial_variability.loc[
        spatial_variability["parameter"].eq("intercept")
    ].iloc[0]

    def variability_conclusion(row: pd.Series) -> str:
        return "reject H0" if bool(row["significant_at_0_05"]) else "fail to reject H0"

    def rows(frame: pd.DataFrame) -> str:
        return "\n".join(
            f"- {row.planning_area_name}: ${row.local_income_slope_sgd_per_1000:,.1f} "
            f"per $1,000 income (local R-squared {row.local_r_squared:.3f})"
            for row in frame.itertuples()
        )

    if delta_aicc > 10:
        conclusion = "strongly improves"
    elif delta_aicc > 4:
        conclusion = "moderately improves"
    elif delta_aicc > 2:
        conclusion = "slightly improves"
    else:
        conclusion = "does not clearly improve"
    summary = f"""# Geographically weighted regression: household income and nursery fees

## Model

- Observations: **{len(data)} planning areas** matched across the income and nursery-fee datasets.
- Outcome: median monthly full-day nursery fee (SGD).
- Predictor: estimated median monthly household income, expressed per SGD 1,000.
- Kernel: adaptive bi-square over planning-area centroids.
- Bandwidth selection: minimum leave-one-out cross-validation (LOOCV) RMSE; AICc is not used to choose the bandwidth.
- Selected bandwidth: **{selected_neighbours} nearest neighbours**, excluding the target area itself.
- Minimum leave-one-out RMSE: **{selected_loocv_rmse:.1f} SGD**.
- The model is descriptive; it does not establish that household income causes nursery fees.

## Global OLS versus GWR

| Metric | Global OLS | GWR |
| --- | ---: | ---: |
| R-squared | {float(ols['r_squared']):.3f} | {float(gwr['r_squared']):.3f} |
| RMSE (SGD) | {ols_rmse:.1f} | {float(gwr['rmse']):.1f} |
| AICc | {ols_aicc:.1f} | {float(gwr['aicc']):.1f} |
| Effective parameters | 2.0 | {float(gwr['trace_s']):.2f} |

The GWR model **{conclusion}** on global OLS by the conventional AICc comparison (OLS minus GWR = **{delta_aicc:.1f}**). Its in-sample RMSE is **{improvement:.1f}%** lower. Because GWR is more flexible, the AICc and leave-one-out results should be considered alongside the in-sample fit.

## Spatial variation in the income coefficient

- Local slope range: **${slopes.min():,.1f} to ${slopes.max():,.1f}** change in median fee per additional SGD 1,000 of median income.
- Median local slope: **${slopes.median():,.1f} per SGD 1,000**.
- Positive local slopes: **{int((slopes > 0).sum())} of {len(slopes)}** planning areas.
- Effective residual degrees of freedom used for approximate local t-tests: **{inference_df:.2f}**.
- Areas with unadjusted two-sided p <= 0.05: **{int((local_p <= 0.05).sum())}**.
- Areas remaining significant at 5% after Benjamini-Hochberg FDR correction across the {len(slopes)} income-slope tests: **{int((local_p_fdr <= 0.05).sum())}**.
- The smallest non-significant adjusted income-slope p-value is **{local_p_fdr[local_p_fdr > 0.05].min():.3f}**.

### Monte Carlo spatial-variability test

- H0: the coefficient is spatially stationary; its observed across-area variability is no greater than expected after randomly reassigning locations.
- H1: the coefficient exhibits greater spatial variability than expected under random location assignment.
- Method: **{int(slope_variability['permutations']):,} coordinate randomisations**, refitting GWR each time at the fixed, selected bandwidth of **{selected_neighbours} neighbours**. The test statistic is the sample standard deviation of the local coefficients, and the pseudo p-value uses the upper tail with the plus-one correction.

| Parameter | Observed SD | Null mean SD | Null 95th percentile | Pseudo p-value | Decision at 5% |
| --- | ---: | ---: | ---: | ---: | --- |
| Intercept | {intercept_variability['observed_coefficient_sd']:.2f} | {intercept_variability['null_mean_coefficient_sd']:.2f} | {intercept_variability['null_95th_percentile']:.2f} | {intercept_variability['pseudo_p_value_upper']:.3f} | {variability_conclusion(intercept_variability)} |
| Income slope | {slope_variability['observed_coefficient_sd']:.2f} | {slope_variability['null_mean_coefficient_sd']:.2f} | {slope_variability['null_95th_percentile']:.2f} | {slope_variability['pseudo_p_value_upper']:.3f} | {variability_conclusion(slope_variability)} |

The income-slope test is the primary test of the research hypothesis. Local t-values test whether individual coefficients differ from zero; they do **not** test whether the coefficient varies significantly across space.

Strongest local coefficients:

{rows(best)}

Weakest local coefficients:

{rows(weakest)}

## Residual spatial autocorrelation

- Global OLS residual Moran's I: **{ols_residual_moran[0]:.3f}**, permutation p = **{ols_residual_moran[1]:.3f}**.
- GWR residual Moran's I: **{gwr_residual_moran[0]:.3f}**, permutation p = **{gwr_residual_moran[1]:.3f}**.

## Limitations

There are only {len(data)} matched planning areas and one explanatory variable. Local estimates can therefore be sensitive to bandwidth choice, influential high-fee areas, and the grouped-income interpolation. The nursery data are explicitly from 2021, while the income CSV does not state its reference year. Provider type, subsidies, commercial rents, programme characteristics, and centre composition remain omitted variables. Interpret the coefficient surfaces as exploratory spatial heterogeneity rather than causal effects.
"""
    path.write_text(summary, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--income-csv",
        type=Path,
        default=Path("data/ResidentHouseholdsIncomebyPlanningArea.csv"),
    )
    parser.add_argument(
        "--nursery-csv",
        type=Path,
        default=Path(
            "output/spatial_autocorrelation_nursery_fee_planning_area/"
            "planning_area_nursery_fee_moran.csv"
        ),
    )
    parser.add_argument(
        "--boundaries",
        type=Path,
        default=Path("data/MasterPlanSubZones_2019.geojson"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/gwr_income_nursery_fee_planning_area"),
    )
    parser.add_argument("--minimum-neighbours", type=int, default=6)
    parser.add_argument("--permutations", type=int, default=999)
    parser.add_argument("--seed", type=int, default=4015)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    data, _ = prepare_data(args.income_csv, args.nursery_csv)
    subzones = prepare_subzones(load_geojson(args.boundaries), name_field="PLN_AREA_N")

    centroid_by_area = {}
    for area_name in sorted({item["planning_area"] for item in subzones}):
        pieces = [item for item in subzones if item["planning_area"] == area_name]
        areas_and_centres = []
        for piece in pieces:
            areas_and_centres.append(geometry_area_centroid(piece["geometry"]))
        total_area = sum(item[0] for item in areas_and_centres)
        centroid_by_area[area_name] = (
            sum(area * lon for area, lon, _ in areas_and_centres) / total_area,
            sum(area * lat for area, _, lat in areas_and_centres) / total_area,
        )

    data["planning_area"] = data["planning_area_name"].str.strip().str.upper()
    missing_centroids = sorted(set(data["planning_area"]) - set(centroid_by_area))
    if missing_centroids:
        raise ValueError(f"Planning areas missing centroids: {missing_centroids}")
    lonlat = np.asarray([centroid_by_area[name] for name in data["planning_area"]])
    data["centroid_lon"] = lonlat[:, 0]
    data["centroid_lat"] = lonlat[:, 1]
    coordinates_km = local_xy_km(lonlat[:, 0], lonlat[:, 1])
    distances = pairwise_distances(coordinates_km)

    income_thousands = data["estimated_median_income_sgd"].to_numpy() / 1_000
    outcome = data["median_fee_sgd"].to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(data)), income_thousands])
    bandwidth_results, gwr = select_bandwidth(
        design,
        outcome,
        distances,
        minimum_neighbours=args.minimum_neighbours,
    )
    selected_row = bandwidth_results.loc[bandwidth_results["selected_by_loocv"]].iloc[0]
    selected_neighbours = int(selected_row["adaptive_neighbours"])
    selected_loocv_rmse = float(selected_row["loocv_rmse_sgd"])

    ols = ols_fit(income_thousands, outcome)
    ols_sse = float(np.asarray(ols["residual"]) @ np.asarray(ols["residual"]))
    ols_rmse = float(np.sqrt(ols_sse / len(data)))
    _, ols_aicc = information_criteria(ols_sse, len(data), 2.0)

    coefficients = np.asarray(gwr["coefficients"])
    standard_errors = np.asarray(gwr["standard_errors"])
    t_values = np.asarray(gwr["t_values"])
    data["local_intercept_sgd"] = coefficients[:, 0]
    data["local_income_slope_sgd_per_1000"] = coefficients[:, 1]
    data["local_intercept_se"] = standard_errors[:, 0]
    data["local_income_slope_se"] = standard_errors[:, 1]
    data["local_intercept_t"] = t_values[:, 0]
    data["local_income_slope_t"] = t_values[:, 1]
    inference_df = float(gwr["effective_df"])
    data["local_inference_effective_df"] = inference_df
    data["local_intercept_p_two_sided"] = 2 * student_t.sf(
        np.abs(data["local_intercept_t"].to_numpy(dtype=float)), inference_df
    )
    data["local_income_slope_p_two_sided"] = 2 * student_t.sf(
        np.abs(data["local_income_slope_t"].to_numpy(dtype=float)), inference_df
    )
    data["local_intercept_p_fdr_bh"] = benjamini_hochberg(
        data["local_intercept_p_two_sided"].to_numpy(dtype=float)
    )
    data["local_income_slope_p_fdr_bh"] = benjamini_hochberg(
        data["local_income_slope_p_two_sided"].to_numpy(dtype=float)
    )
    data["local_intercept_significant_fdr_0_05"] = (
        data["local_intercept_p_fdr_bh"] <= 0.05
    )
    data["local_income_slope_significant_fdr_0_05"] = (
        data["local_income_slope_p_fdr_bh"] <= 0.05
    )
    data["local_r_squared"] = np.asarray(gwr["local_r2"])
    data["gwr_fitted_fee_sgd"] = np.asarray(gwr["fitted"])
    data["gwr_residual_sgd"] = np.asarray(gwr["residual"])
    data["local_bandwidth_km"] = np.asarray(gwr["bandwidth_km"])
    data["selected_adaptive_neighbours"] = selected_neighbours

    ols_residual_moran = residual_moran_test(
        np.asarray(ols["residual"]), lonlat, args.permutations, args.seed
    )
    gwr_residual_moran = residual_moran_test(
        np.asarray(gwr["residual"]), lonlat, args.permutations, args.seed + 1
    )
    spatial_variability, spatial_variability_distribution = (
        monte_carlo_spatial_variability(
            design,
            outcome,
            distances,
            selected_neighbours,
            coefficients,
            args.permutations,
            args.seed + 2,
        )
    )

    data.to_csv(args.output_dir / "gwr_local_results.csv", index=False)
    bandwidth_results.to_csv(args.output_dir / "gwr_bandwidth_selection.csv", index=False)
    spatial_variability.to_csv(
        args.output_dir / "gwr_monte_carlo_spatial_variability.csv", index=False
    )
    spatial_variability_distribution.to_csv(
        args.output_dir / "gwr_monte_carlo_null_distribution.csv", index=False
    )
    slope_variability = spatial_variability.loc[
        spatial_variability["parameter"].eq("income_slope")
    ].iloc[0]
    intercept_variability = spatial_variability.loc[
        spatial_variability["parameter"].eq("intercept")
    ].iloc[0]
    summary_rows = [
        ("matched_planning_areas", len(data)),
        ("selected_adaptive_neighbours", selected_neighbours),
        ("gwr_effective_parameters_trace_s", gwr["trace_s"]),
        ("gwr_inference_effective_df", gwr["effective_df"]),
        ("gwr_r_squared", gwr["r_squared"]),
        ("gwr_adjusted_r_squared", gwr["adjusted_r_squared"]),
        ("gwr_rmse_sgd", gwr["rmse"]),
        ("gwr_aic", gwr["aic"]),
        ("gwr_aicc", gwr["aicc"]),
        ("ols_r_squared", ols["r_squared"]),
        ("ols_rmse_sgd", ols_rmse),
        ("ols_aicc", ols_aicc),
        ("ols_residual_moran_i", ols_residual_moran[0]),
        ("ols_residual_moran_p", ols_residual_moran[1]),
        ("gwr_residual_moran_i", gwr_residual_moran[0]),
        ("gwr_residual_moran_p", gwr_residual_moran[1]),
        (
            "monte_carlo_income_slope_variability_sd",
            slope_variability["observed_coefficient_sd"],
        ),
        (
            "monte_carlo_income_slope_variability_p",
            slope_variability["pseudo_p_value_upper"],
        ),
        (
            "monte_carlo_intercept_variability_sd",
            intercept_variability["observed_coefficient_sd"],
        ),
        (
            "monte_carlo_intercept_variability_p",
            intercept_variability["pseudo_p_value_upper"],
        ),
        (
            "local_income_slopes_significant_raw_0_05",
            int((data["local_income_slope_p_two_sided"] <= 0.05).sum()),
        ),
        (
            "local_income_slopes_significant_fdr_bh_0_05",
            int(data["local_income_slope_significant_fdr_0_05"].sum()),
        ),
        (
            "local_intercepts_significant_fdr_bh_0_05",
            int(data["local_intercept_significant_fdr_0_05"].sum()),
        ),
    ]
    pd.DataFrame(summary_rows, columns=["metric", "value"]).to_csv(
        args.output_dir / "gwr_model_summary.csv", index=False
    )

    plot_fit_maps(data, subzones, args.output_dir / "gwr_fit_maps.png")
    plot_bandwidth_selection(
        bandwidth_results, args.output_dir / "gwr_bandwidth_selection.png"
    )
    plot_monte_carlo_spatial_variability(
        spatial_variability,
        spatial_variability_distribution,
        args.output_dir / "gwr_monte_carlo_spatial_variability.png",
    )
    plot_local_regression_lines(
        data,
        ols,
        args.output_dir / "gwr_local_regression_lines.png",
    )
    write_summary(
        args.output_dir / "gwr_analysis_summary.md",
        data,
        selected_neighbours,
        gwr,
        ols,
        ols_rmse,
        ols_aicc,
        selected_loocv_rmse,
        spatial_variability,
        gwr_residual_moran,
        ols_residual_moran,
    )

    print(f"Matched planning areas: {len(data)}")
    print(f"Selected adaptive neighbours: {selected_neighbours}")
    print(f"GWR R-squared: {float(gwr['r_squared']):.4f}")
    print(f"GWR AICc: {float(gwr['aicc']):.3f}; OLS AICc: {ols_aicc:.3f}")
    print(
        "Income-slope spatial-variability Monte Carlo p-value: "
        f"{slope_variability['pseudo_p_value_upper']:.4f}"
    )
    print(f"Wrote outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
