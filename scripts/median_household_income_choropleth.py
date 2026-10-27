"""Plot median monthly household income ranges by Singapore planning area."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Patch, Polygon as MplPolygon
import numpy as np
import pandas as pd


INCOME_BANDS = [
    ("NoEmployedPerson", "No employed person"),
    ("Below_1_000", "Below $1,000"),
    ("1_000_1_999", "$1,000–$1,999"),
    ("2_000_2_999", "$2,000–$2,999"),
    ("3_000_3_999", "$3,000–$3,999"),
    ("4_000_4_999", "$4,000–$4,999"),
    ("5_000_5_999", "$5,000–$5,999"),
    ("6_000_6_999", "$6,000–$6,999"),
    ("7_000_7_999", "$7,000–$7,999"),
    ("8_000_8_999", "$8,000–$8,999"),
    ("9_000_9_999", "$9,000–$9,999"),
    ("10_000_10_999", "$10,000–$10,999"),
    ("11_000_11_999", "$11,000–$11,999"),
    ("12_000_12_999", "$12,000–$12,999"),
    ("13_000_13_999", "$13,000–$13,999"),
    ("14_000_14_999", "$14,000–$14,999"),
    ("15_000_17_499", "$15,000–$17,499"),
    ("17_500_19_999", "$17,500–$19,999"),
    ("20_000andOver", "$20,000 & over"),
]


def iter_polygons(geometry: dict):
    if geometry["type"] == "Polygon":
        yield geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        yield from geometry["coordinates"]
    else:
        raise ValueError(f"Unsupported geometry type: {geometry['type']}")


def planning_area_boundary_segments(features: list[dict]) -> list[list[tuple[float, float]]]:
    """Dissolve subzone edges into planning-area outlines."""
    segments_by_area: dict[str, dict[tuple, tuple]] = {}
    counts_by_area: dict[str, dict[tuple, int]] = {}
    for feature in features:
        area_name = feature["properties"]["PLN_AREA_N"].strip().upper()
        segments_by_area.setdefault(area_name, {})
        counts_by_area.setdefault(area_name, {})
        for polygon in iter_polygons(feature["geometry"]):
            for ring in polygon:
                for p1, p2 in zip(ring, ring[1:]):
                    a = (round(p1[0], 10), round(p1[1], 10))
                    b = (round(p2[0], 10), round(p2[1], 10))
                    key = tuple(sorted((a, b)))
                    counts_by_area[area_name][key] = counts_by_area[area_name].get(key, 0) + 1
                    segments_by_area[area_name][key] = (tuple(p1[:2]), tuple(p2[:2]))
    return [
        list(segments_by_area[area_name][key])
        for area_name, counts in counts_by_area.items()
        for key, count in counts.items()
        if count == 1
    ]


def calculate_median_ranges(income_csv: Path) -> pd.DataFrame:
    income = pd.read_csv(income_csv)
    income = income.loc[~income["Number"].str.casefold().isin({"total", "others"})].copy()
    band_columns = [column for column, _ in INCOME_BANDS]

    missing_columns = [column for column in band_columns if column not in income.columns]
    if missing_columns:
        raise ValueError(f"Missing income-band columns: {missing_columns}")

    band_counts = income[band_columns].apply(pd.to_numeric, errors="raise")
    band_totals = band_counts.sum(axis=1)
    cumulative = band_counts.cumsum(axis=1)
    median_band_index = cumulative.ge(band_totals / 2, axis=0).to_numpy().argmax(axis=1)

    result = pd.DataFrame(
        {
            "planning_area": income["Number"].str.strip(),
            "reported_total_households": pd.to_numeric(income["Total"], errors="raise"),
            "band_total_households": band_totals.astype(int),
            "median_income_range": [INCOME_BANDS[index][1] for index in median_band_index],
            "median_income_band_order": median_band_index,
        }
    )
    return result.sort_values("planning_area").reset_index(drop=True)


def plot_choropleth(boundaries_geojson: Path, median_df: pd.DataFrame, output_png: Path) -> None:
    with boundaries_geojson.open("r", encoding="utf-8") as source:
        features = json.load(source)["features"]

    median_df = median_df.copy()
    median_df["join_name"] = median_df["planning_area"].str.upper()
    polygon_names = {feature["properties"]["PLN_AREA_N"].strip().upper() for feature in features}
    unmatched = sorted(set(median_df["join_name"]) - polygon_names)
    if unmatched:
        raise ValueError(f"Income planning areas missing from boundary file: {unmatched}")

    band_order = dict(zip((label for _, label in INCOME_BANDS), range(len(INCOME_BANDS))))
    used_ranges = sorted(median_df["median_income_range"].unique(), key=band_order.get)
    # Use one sequential hue: lighter blue indicates a lower median income
    # range and darker blue indicates a higher median income range.
    colour_scale = plt.colormaps["Blues"]
    colour_values = np.linspace(0.32, 0.92, len(used_ranges))
    colour_by_range = {
        label: colour_scale(value) for label, value in zip(used_ranges, colour_values)
    }
    range_by_area = dict(zip(median_df["join_name"], median_df["median_income_range"]))

    patches: list[MplPolygon] = []
    face_colours = []
    no_data_colour = "#E6E6E6"
    for feature in features:
        area_name = feature["properties"]["PLN_AREA_N"].strip().upper()
        colour = colour_by_range.get(range_by_area.get(area_name), no_data_colour)
        for polygon in iter_polygons(feature["geometry"]):
            patches.append(MplPolygon(np.asarray(polygon[0])[:, :2], closed=True))
            face_colours.append(colour)

    fig, ax = plt.subplots(figsize=(14, 9))
    collection = PatchCollection(
        patches,
        facecolor=face_colours,
        # The source contains subzones, but hiding their edges and drawing only
        # the dissolved outlines below produces a planning-area basemap.
        edgecolor="none",
        linewidth=0,
        antialiased=False,
    )
    ax.add_collection(collection)
    ax.add_collection(
        LineCollection(
            planning_area_boundary_segments(features),
            colors="#FFFFFF",
            linewidths=0.9,
            zorder=3,
        )
    )
    ax.autoscale_view()
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()
    fig.suptitle(
        "Median Monthly Household Income Range by Planning Area",
        fontsize=17,
        fontweight="bold",
        x=0.5,
        y=0.88,
        ha="center",
    )

    counts = median_df["median_income_range"].value_counts().to_dict()
    legend_handles = [
        Patch(facecolor=colour_by_range[label], edgecolor="none", label=f"{label} ({counts[label]})")
        for label in reversed(used_ranges)
    ]
    legend_handles.append(Patch(facecolor=no_data_colour, edgecolor="#BBBBBB", label="No data"))
    ax.legend(
        handles=legend_handles,
        title="Median monthly income range\n(planning areas)",
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        frameon=False,
        fontsize=10,
        title_fontsize=10,
    )
    fig.tight_layout(rect=(0.02, 0.02, 0.83, 0.93))
    plot_position = ax.get_position()
    ax.set_position(
        [
            plot_position.x0,
            plot_position.y0 + 0.055,
            plot_position.width,
            plot_position.height,
        ]
    )
    output_png.parent.mkdir(parents=True, exist_ok=True)
    # Keep the full canvas so x=0.5 is the true visual centre of the exported image.
    fig.savefig(output_png, dpi=240, facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--income-csv",
        type=Path,
        default=Path("data/ResidentHouseholdsIncomebyPlanningArea.csv"),
    )
    parser.add_argument(
        "--boundaries",
        type=Path,
        default=Path("data/MasterPlanSubZones_2019.geojson"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/median_household_income_planning_area"),
    )
    args = parser.parse_args()

    median_df = calculate_median_ranges(args.income_csv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = args.output_dir / "planning_area_median_household_income_range.csv"
    output_png = args.output_dir / "median_household_income_choropleth.png"
    median_df.to_csv(output_csv, index=False)
    plot_choropleth(args.boundaries, median_df, output_png)
    print(f"Wrote {output_csv}")
    print(f"Wrote {output_png}")
    print(median_df[["planning_area", "median_income_range"]].to_string(index=False))


if __name__ == "__main__":
    main()
