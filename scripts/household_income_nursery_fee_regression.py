"""Analyse median household income and median nursery fees by planning area."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# The final open-ended class is assigned the same width as the preceding class.
# This is required only to interpolate Tanglin's median within the $20,000+ band.
INCOME_BANDS = [
    ("NoEmployedPerson", "No employed person", 0.0, 0.0),
    ("Below_1_000", "Below $1,000", 0.0, 1_000.0),
    ("1_000_1_999", "$1,000-$1,999", 1_000.0, 1_000.0),
    ("2_000_2_999", "$2,000-$2,999", 2_000.0, 1_000.0),
    ("3_000_3_999", "$3,000-$3,999", 3_000.0, 1_000.0),
    ("4_000_4_999", "$4,000-$4,999", 4_000.0, 1_000.0),
    ("5_000_5_999", "$5,000-$5,999", 5_000.0, 1_000.0),
    ("6_000_6_999", "$6,000-$6,999", 6_000.0, 1_000.0),
    ("7_000_7_999", "$7,000-$7,999", 7_000.0, 1_000.0),
    ("8_000_8_999", "$8,000-$8,999", 8_000.0, 1_000.0),
    ("9_000_9_999", "$9,000-$9,999", 9_000.0, 1_000.0),
    ("10_000_10_999", "$10,000-$10,999", 10_000.0, 1_000.0),
    ("11_000_11_999", "$11,000-$11,999", 11_000.0, 1_000.0),
    ("12_000_12_999", "$12,000-$12,999", 12_000.0, 1_000.0),
    ("13_000_13_999", "$13,000-$13,999", 13_000.0, 1_000.0),
    ("14_000_14_999", "$14,000-$14,999", 14_000.0, 1_000.0),
    ("15_000_17_499", "$15,000-$17,499", 15_000.0, 2_500.0),
    ("17_500_19_999", "$17,500-$19,999", 17_500.0, 2_500.0),
    ("20_000andOver", "$20,000 & over", 20_000.0, 2_500.0),
]


def estimate_grouped_median(row: pd.Series) -> tuple[float, str, int, float]:
    """Estimate a median using linear interpolation within its grouped band."""
    counts = np.asarray([float(row[column]) for column, *_ in INCOME_BANDS])
    total = counts.sum()
    target = total / 2.0
    cumulative = np.cumsum(counts)
    band_index = int(np.searchsorted(cumulative, target, side="left"))
    column, label, lower, width = INCOME_BANDS[band_index]
    previous = cumulative[band_index - 1] if band_index else 0.0
    frequency = counts[band_index]
    if frequency <= 0:
        raise ValueError(f"Median band has zero frequency for {row['Number']}")
    estimate = lower if width == 0 else lower + ((target - previous) / frequency) * width
    midpoint = lower if width == 0 else lower + width / 2.0
    return estimate, label, band_index, midpoint


def prepare_data(income_csv: Path, nursery_csv: Path) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    income = pd.read_csv(income_csv)
    income = income.loc[~income["Number"].str.casefold().isin({"total", "others"})].copy()
    required_bands = [column for column, *_ in INCOME_BANDS]
    income[required_bands] = income[required_bands].apply(pd.to_numeric, errors="raise")

    estimates = income.apply(estimate_grouped_median, axis=1, result_type="expand").reset_index(drop=True)
    estimates.columns = [
        "estimated_median_income_sgd",
        "median_income_range",
        "median_income_band_order",
        "median_income_band_midpoint_sgd",
    ]
    income = pd.concat([income[["Number"]].reset_index(drop=True), estimates], axis=1)
    income["join_name"] = income["Number"].str.strip().str.upper()

    nursery = pd.read_csv(nursery_csv)
    required_nursery = {"planning_area", "median_fee_sgd", "centre_count"}
    missing = sorted(required_nursery - set(nursery.columns))
    if missing:
        raise ValueError(f"Missing nursery columns: {missing}")
    nursery = nursery[["planning_area", "median_fee_sgd", "centre_count"]].copy()
    nursery["join_name"] = nursery["planning_area"].str.strip().str.upper()

    merged = income.merge(nursery, on="join_name", how="inner", validate="one_to_one")
    merged = merged.rename(columns={"Number": "planning_area_name"})
    merged = merged[
        [
            "planning_area_name",
            "median_income_range",
            "median_income_band_order",
            "median_income_band_midpoint_sgd",
            "estimated_median_income_sgd",
            "median_fee_sgd",
            "centre_count",
        ]
    ].sort_values("planning_area_name").reset_index(drop=True)

    coverage = {
        "income_without_fee": sorted(set(income["join_name"]) - set(nursery["join_name"])),
        "fee_without_income": sorted(set(nursery["join_name"]) - set(income["join_name"])),
    }
    if len(merged) < 3:
        raise ValueError("Fewer than three matched planning areas; regression is not possible")
    return merged, coverage


def ols_fit(x: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray | float]:
    design = np.column_stack([np.ones(len(x)), x])
    inverse = np.linalg.inv(design.T @ design)
    beta = inverse @ design.T @ y
    fitted = design @ beta
    residual = y - fitted
    sse = float(residual @ residual)
    tss = float(((y - y.mean()) ** 2).sum())
    mse = sse / (len(x) - 2)
    leverage = np.sum((design @ inverse) * design, axis=1)
    cooks = (residual**2 / (2 * mse)) * leverage / ((1 - leverage) ** 2)
    return {
        "intercept": float(beta[0]),
        "slope": float(beta[1]),
        "fitted": fitted,
        "residual": residual,
        "r_squared": 1 - sse / tss,
        "rmse": float(np.sqrt(mse)),
        "leverage": leverage,
        "cooks_distance": cooks,
    }


def correlation(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.corrcoef(x, y)[0, 1])


def rank_values(values: np.ndarray) -> np.ndarray:
    return pd.Series(values).rank(method="average").to_numpy(dtype=float)


def theil_sen_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Return the median pairwise slope and its median-residual intercept."""
    slopes = []
    for left in range(len(x)):
        for right in range(left + 1, len(x)):
            if x[right] != x[left]:
                slopes.append((y[right] - y[left]) / (x[right] - x[left]))
    slope = float(np.median(slopes))
    intercept = float(np.median(y - slope * x))
    return intercept, slope


def permutation_p_values(
    x: np.ndarray, y: np.ndarray, permutations: int, seed: int
) -> tuple[float, float, float, float]:
    pearson = correlation(x, y)
    x_rank = rank_values(x)
    y_rank = rank_values(y)
    spearman = correlation(x_rank, y_rank)

    rng = np.random.default_rng(seed)
    pearson_extreme = 0
    spearman_extreme = 0
    for _ in range(permutations):
        permuted = rng.permutation(len(y))
        pearson_extreme += abs(correlation(x, y[permuted])) >= abs(pearson)
        spearman_extreme += abs(correlation(x_rank, y_rank[permuted])) >= abs(spearman)
    pearson_p = (pearson_extreme + 1) / (permutations + 1)
    spearman_p = (spearman_extreme + 1) / (permutations + 1)
    return pearson, pearson_p, spearman, spearman_p


def bootstrap_coefficients(
    x: np.ndarray, y: np.ndarray, samples: int, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(x), size=(samples, len(x)))
    bx = x[indices]
    by = y[indices]
    x_mean = bx.mean(axis=1)
    y_mean = by.mean(axis=1)
    denominator = ((bx - x_mean[:, None]) ** 2).sum(axis=1)
    valid = denominator > 0
    slope = ((bx - x_mean[:, None]) * (by - y_mean[:, None])).sum(axis=1)[valid]
    slope = slope / denominator[valid]
    intercept = y_mean[valid] - slope * x_mean[valid]
    return intercept, slope


def plot_scatter(
    data: pd.DataFrame,
    model: dict[str, np.ndarray | float],
    boot_intercept: np.ndarray,
    boot_slope: np.ndarray,
    theil_sen: tuple[float, float],
    pearson: float,
    pearson_p: float,
    output_path: Path,
) -> None:
    x = data["estimated_median_income_sgd"].to_numpy() / 1_000.0
    y = data["median_fee_sgd"].to_numpy()
    x_grid = np.linspace(max(0, x.min() - 0.5), x.max() + 0.5, 240)
    regression = float(model["intercept"]) + float(model["slope"]) * x_grid
    robust_regression = theil_sen[0] + theil_sen[1] * x_grid
    boot_prediction = boot_intercept[:, None] + boot_slope[:, None] * x_grid[None, :]
    lower, upper = np.percentile(boot_prediction, [2.5, 97.5], axis=0)

    sizes = 30 + 8 * np.sqrt(data["centre_count"].to_numpy())
    fig, ax = plt.subplots(figsize=(11, 7.2))
    ax.fill_between(x_grid, lower, upper, color="#86B6D8", alpha=0.32, linewidth=0)
    ax.plot(x_grid, regression, color="#B23A2B", linewidth=2.2, label="OLS regression")
    ax.plot(
        x_grid,
        robust_regression,
        color="#555555",
        linewidth=1.8,
        linestyle="--",
        label="Theil-Sen robust sensitivity",
    )
    ax.scatter(
        x,
        y,
        s=sizes,
        color="#2166AC",
        edgecolor="white",
        linewidth=0.8,
        alpha=0.9,
        zorder=3,
    )

    top_influence = np.argsort(np.asarray(model["cooks_distance"]))[-5:]
    offsets = [(6, 6), (6, -13), (6, 6), (-6, 7), (6, 6)]
    for index, offset in zip(top_influence, offsets):
        ax.annotate(
            data.loc[index, "planning_area_name"],
            (x[index], y[index]),
            xytext=offset,
            textcoords="offset points",
            fontsize=8.5,
            ha="right" if offset[0] < 0 else "left",
        )

    ax.text(
        0.025,
        0.965,
        f"n = {len(data)} planning areas\n"
        f"Fee change per SGD 1,000 income = SGD {float(model['slope']):,.1f}\n"
        f"R² = {float(model['r_squared']):.3f}\n"
        f"Pearson r = {pearson:.3f} (p = {pearson_p:.4f})",
        transform=ax.transAxes,
        va="top",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "white", "edgecolor": "#BBBBBB", "alpha": 0.94},
    )
    ax.set_title(
        "Median Household Income and Nursery Fees by Planning Area",
        fontsize=16,
        fontweight="bold",
        pad=15,
    )
    ax.set_xlabel("Estimated median monthly household income (SGD thousands)")
    ax.set_ylabel("Median monthly full-day nursery fee (SGD)")
    ax.grid(axis="both", color="#D9D9D9", linewidth=0.7, alpha=0.65)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower right", frameon=False)
    ax.text(
        0.02,
        0.02,
        "Marker size reflects the number of nursery centres",
        transform=ax.transAxes,
        ha="left",
        fontsize=8.5,
        color="#555555",
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=240, facecolor="white")
    plt.close(fig)


def plot_diagnostics(
    data: pd.DataFrame, model: dict[str, np.ndarray | float], output_path: Path
) -> None:
    fitted = np.asarray(model["fitted"])
    residual = np.asarray(model["residual"])
    cooks = np.asarray(model["cooks_distance"])
    names = data["planning_area_name"].to_numpy()

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4))
    axes[0].scatter(fitted, residual, color="#2166AC", edgecolor="white", s=70, alpha=0.9)
    axes[0].axhline(0, color="#555555", linestyle="--", linewidth=1)
    axes[0].set_title("Residuals versus Fitted Fees", fontweight="bold")
    axes[0].set_xlabel("Fitted nursery fee (SGD)")
    axes[0].set_ylabel("Residual (SGD)")
    axes[0].grid(color="#E2E2E2", linewidth=0.7, alpha=0.7)

    order = np.argsort(cooks)[::-1]
    shown = order[:10][::-1]
    axes[1].barh(names[shown], cooks[shown], color="#4C92C3")
    axes[1].axvline(4 / len(data), color="#B23A2B", linestyle="--", linewidth=1.2, label="4/n guide")
    axes[1].set_title("Most Influential Planning Areas", fontweight="bold")
    axes[1].set_xlabel("Cook's distance")
    axes[1].legend(frameon=False, loc="lower right")
    axes[1].grid(axis="x", color="#E2E2E2", linewidth=0.7, alpha=0.7)

    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Regression Diagnostics", fontsize=16, fontweight="bold", y=0.99)
    fig.tight_layout()
    fig.savefig(output_path, dpi=240, facecolor="white")
    plt.close(fig)


def write_summary(
    output_path: Path,
    data: pd.DataFrame,
    coverage: dict[str, list[str]],
    model: dict[str, np.ndarray | float],
    midpoint_model: dict[str, np.ndarray | float],
    model_without_top_influence: dict[str, np.ndarray | float],
    top_influence_name: str,
    theil_sen: tuple[float, float],
    pearson: float,
    pearson_p: float,
    spearman: float,
    spearman_p: float,
    slope_ci: np.ndarray,
) -> None:
    cooks = np.asarray(model["cooks_distance"])
    influential = data.iloc[np.argsort(cooks)[::-1][:5]].copy()
    influential["cooks_distance"] = np.sort(cooks)[::-1][:5]
    influence_rows = "\n".join(
        f"- {row.planning_area_name}: median income ${row.estimated_median_income_sgd:,.0f}, "
        f"median fee ${row.median_fee_sgd:,.0f}, Cook's D {row.cooks_distance:.3f}"
        for row in influential.itertuples()
    )
    unmatched_fee = ", ".join(coverage["fee_without_income"]) or "None"
    unmatched_income = ", ".join(coverage["income_without_fee"]) or "None"
    direction = "positive" if float(model["slope"]) > 0 else "negative"
    evidence = "statistically detectable" if pearson_p < 0.05 else "not statistically detectable"

    summary = f"""# Median household income and nursery fee regression

## Data and method

- Unit of analysis: planning area; each of the {len(data)} matched areas has equal weight.
- Outcome: median full-day SC nursery fee from the planning-area nursery-fee analysis.
- Predictor: estimated median monthly household income from the grouped income counts. The estimate uses linear interpolation inside the median band.
- The open-ended $20,000-and-over band is treated as $20,000-$22,500 for interpolation; only Tanglin's estimate depends on this assumption.
- Model: ordinary least squares, with income expressed in SGD thousands.
- Inference: 95% paired bootstrap interval ({len(slope_ci) and 'percentile method'}) and two-sided permutation tests. Spearman correlation is included because the original income data are grouped.

## Results

- Regression equation: median nursery fee = **${float(model['intercept']):,.1f} + ${float(model['slope']):,.1f} x income in $1,000s**.
- Estimated change: **${float(model['slope']):,.1f} higher median nursery fee per additional $1,000 of median monthly household income**.
- 95% bootstrap interval for the slope: **${slope_ci[0]:,.1f} to ${slope_ci[1]:,.1f} per $1,000**.
- Pearson correlation: **r = {pearson:.3f}**, two-sided permutation **p = {pearson_p:.4f}**.
- Model fit: **R-squared = {float(model['r_squared']):.3f}**; the linear model explains about **{100 * float(model['r_squared']):.1f}%** of cross-area fee variation.
- Spearman rank correlation: **rho = {spearman:.3f}**, two-sided permutation **p = {spearman_p:.4f}**.
- Residual standard error: **${float(model['rmse']):,.1f}**.
- Using income-band midpoints instead of interpolation gives a slope of **${float(midpoint_model['slope']):,.1f} per $1,000** and **R-squared = {float(midpoint_model['r_squared']):.3f}**.
- The robust Theil-Sen sensitivity slope is **${theil_sen[1]:,.1f} per $1,000**.
- Removing the most influential area ({top_influence_name}) gives a slope of **${float(model_without_top_influence['slope']):,.1f} per $1,000** and **R-squared = {float(model_without_top_influence['r_squared']):.3f}**.

## Interpretation

The observed relationship is **{direction}** and is **{evidence} at the 5% level** under the permutation test. Planning areas with higher median household income generally have higher median nursery fees. However, the modest Spearman correlation and the much flatter robust slope show that the pattern is not a smooth increase across all areas: most middle-income planning areas cluster around $610-$650, while a small group of affluent areas have much higher fees. The association is descriptive, not causal: provider type, subsidies, programme characteristics, commercial rents, and the local mix of centres may affect fees. Nursery fees are spatially autocorrelated, so ordinary regression uncertainty should be interpreted cautiously.

## Influence and coverage

The most influential observations are:

{influence_rows}

- Income areas without a nursery-fee match: {unmatched_income}.
- Nursery-fee areas without household-income data: {unmatched_fee}.

The nursery source is explicitly 2021. The household-income CSV does not state its reference year, so this analysis cannot verify that both measures refer to the same period.
"""
    output_path.write_text(summary, encoding="utf-8")


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
        "--output-dir",
        type=Path,
        default=Path("output/household_income_nursery_fee_regression"),
    )
    parser.add_argument("--permutations", type=int, default=49_999)
    parser.add_argument("--bootstrap-samples", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=4015)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    data, coverage = prepare_data(args.income_csv, args.nursery_csv)
    income_thousands = data["estimated_median_income_sgd"].to_numpy() / 1_000.0
    midpoint_thousands = data["median_income_band_midpoint_sgd"].to_numpy() / 1_000.0
    fees = data["median_fee_sgd"].to_numpy()

    model = ols_fit(income_thousands, fees)
    midpoint_model = ols_fit(midpoint_thousands, fees)
    theil_sen = theil_sen_fit(income_thousands, fees)
    top_influence_index = int(np.argmax(np.asarray(model["cooks_distance"])))
    keep = np.arange(len(data)) != top_influence_index
    model_without_top_influence = ols_fit(income_thousands[keep], fees[keep])
    top_influence_name = str(data.loc[top_influence_index, "planning_area_name"])
    pearson, pearson_p, spearman, spearman_p = permutation_p_values(
        income_thousands, fees, args.permutations, args.seed
    )
    boot_intercept, boot_slope = bootstrap_coefficients(
        income_thousands, fees, args.bootstrap_samples, args.seed + 1
    )
    slope_ci = np.percentile(boot_slope, [2.5, 97.5])

    data["fitted_median_fee_sgd"] = np.asarray(model["fitted"])
    data["residual_sgd"] = np.asarray(model["residual"])
    data["cooks_distance"] = np.asarray(model["cooks_distance"])
    data.to_csv(args.output_dir / "planning_area_regression_data.csv", index=False)

    result_rows = [
        ("matched_planning_areas", len(data)),
        ("intercept_sgd", model["intercept"]),
        ("slope_sgd_per_1000_income", model["slope"]),
        ("slope_bootstrap_ci_95_low", slope_ci[0]),
        ("slope_bootstrap_ci_95_high", slope_ci[1]),
        ("r_squared", model["r_squared"]),
        ("residual_standard_error_sgd", model["rmse"]),
        ("pearson_r", pearson),
        ("pearson_permutation_p_two_sided", pearson_p),
        ("spearman_rho", spearman),
        ("spearman_permutation_p_two_sided", spearman_p),
        ("midpoint_sensitivity_slope", midpoint_model["slope"]),
        ("midpoint_sensitivity_r_squared", midpoint_model["r_squared"]),
        ("theil_sen_robust_slope", theil_sen[1]),
        ("slope_excluding_most_influential_area", model_without_top_influence["slope"]),
        ("r_squared_excluding_most_influential_area", model_without_top_influence["r_squared"]),
    ]
    pd.DataFrame(result_rows, columns=["metric", "value"]).to_csv(
        args.output_dir / "regression_summary.csv", index=False
    )

    plot_scatter(
        data,
        model,
        boot_intercept,
        boot_slope,
        theil_sen,
        pearson,
        pearson_p,
        args.output_dir / "income_nursery_fee_regression.png",
    )
    print(f"Matched planning areas: {len(data)}")
    print(f"Slope per $1,000: {float(model['slope']):.3f}")
    print(f"95% bootstrap CI: [{slope_ci[0]:.3f}, {slope_ci[1]:.3f}]")
    print(f"R-squared: {float(model['r_squared']):.4f}")
    print(f"Pearson r: {pearson:.4f}; permutation p: {pearson_p:.5f}")
    print(f"Spearman rho: {spearman:.4f}; permutation p: {spearman_p:.5f}")
    print(f"Wrote outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
