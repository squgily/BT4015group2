"""Planning-area income/fee regression pieces shared by 3_02 (OLS) and 3_03 (GWR).

Daryl's code from ``scripts/household_income_nursery_fee_regression.py``, unchanged:
``prepare_data`` estimates each planning area's median monthly household income from the grouped
SingStat counts (linear interpolation inside the median band) and joins it to the planning-area
median nursery fee written by notebook 3_01; ``ols_fit`` is a two-parameter least-squares fit
with leverage and Cook's distance for the influence check.
"""
from __future__ import annotations

from pathlib import Path

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
    """Estimate a median using linear interpolation within its grouped band.

    Returns (estimate, band label, band index, band midpoint) for one planning-area row of
    household counts per income band.
    """
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
    """Join estimated median household income to median nursery fee by planning area.

    ``income_csv`` is SingStat's resident households by income band and planning area (rows
    ``Total`` and ``Others`` dropped); ``nursery_csv`` is 3_01's planning-area Moran table
    (needs ``planning_area``, ``median_fee_sgd``, ``centre_count``).  Returns the matched table
    sorted by name and a coverage dict listing the areas present in only one source.
    """
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
    """Simple linear regression y = a + b x by least squares.

    Returns intercept, slope, fitted values, residuals, R-squared, residual standard error,
    leverage h_ii and Cook's distance (the influence diagnostic used in 3_02).
    """
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
