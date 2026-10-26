"""Spatial autocorrelation of childcare nursery fees across Singapore planning areas.

The script uses only pandas, numpy, and matplotlib. GeoJSON parsing and the
point-in-polygon join are implemented here so it does not require GeoPandas.

Outputs (under output/spatial_autocorrelation_nursery_fee by default):
  - planning_area_nursery_fee_moran.csv
  - global_moran_permutations.csv
  - analysis_summary.md
  - nursery_fee_choropleth.png
  - global_moran_scatterplot.png
  - global_moran_permutation.png
  - local_moran_lisa_map.png
  - spatial_autocorrelation_overview.png
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, Polygon as MplPolygon
from matplotlib.collections import LineCollection, PatchCollection
import numpy as np
import pandas as pd


def iter_polygons(geometry: dict):
    """Yield polygons as lists of rings for Polygon and MultiPolygon GeoJSON."""
    if geometry["type"] == "Polygon":
        yield geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        yield from geometry["coordinates"]
    else:
        raise ValueError(f"Unsupported geometry type: {geometry['type']}")


def point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-ring test; boundary behaviour is adequate for points."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][:2]
        xj, yj = ring[j][:2]
        crosses = (yi > y) != (yj > y)
        if crosses:
            x_at_y = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_at_y:
                inside = not inside
        j = i
    return inside


def point_in_geometry(x: float, y: float, geometry: dict) -> bool:
    for polygon in iter_polygons(geometry):
        if point_in_ring(x, y, polygon[0]) and not any(
            point_in_ring(x, y, hole) for hole in polygon[1:]
        ):
            return True
    return False


def ring_area_centroid(ring: list[list[float]]) -> tuple[float, float, float]:
    """Return absolute area and centroid for a ring in lon/lat planar units."""
    cross_sum = cx_sum = cy_sum = 0.0
    for p1, p2 in zip(ring, ring[1:] + ring[:1]):
        x1, y1 = p1[:2]
        x2, y2 = p2[:2]
        cross = x1 * y2 - x2 * y1
        cross_sum += cross
        cx_sum += (x1 + x2) * cross
        cy_sum += (y1 + y2) * cross
    signed_area = cross_sum / 2.0
    if abs(signed_area) < 1e-15:
        arr = np.asarray(ring, dtype=float)
        return 0.0, float(arr[:, 0].mean()), float(arr[:, 1].mean())
    return (
        abs(signed_area),
        cx_sum / (6.0 * signed_area),
        cy_sum / (6.0 * signed_area),
    )


def geometry_area_centroid(geometry: dict) -> tuple[float, float, float]:
    weighted_x = weighted_y = total_area = 0.0
    for polygon in iter_polygons(geometry):
        for ring_index, ring in enumerate(polygon):
            area, cx, cy = ring_area_centroid(ring)
            sign = 1.0 if ring_index == 0 else -1.0
            total_area += sign * area
            weighted_x += sign * area * cx
            weighted_y += sign * area * cy
    return total_area, weighted_x / total_area, weighted_y / total_area


def load_geojson(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def prepare_subzones(subzones_geojson: dict, name_field: str = "PLN_AREA_N") -> list[dict]:
    result = []
    for feature in subzones_geojson["features"]:
        coords = [
            p[:2]
            for polygon in iter_polygons(feature["geometry"])
            for ring in polygon
            for p in ring
        ]
        arr = np.asarray(coords, dtype=float)
        result.append(
            {
                "planning_area": feature["properties"][name_field].strip(),
                "geometry": feature["geometry"],
                "bounds": (
                    float(arr[:, 0].min()),
                    float(arr[:, 1].min()),
                    float(arr[:, 0].max()),
                    float(arr[:, 1].max()),
                ),
            }
        )
    return result


def assign_centres(centres_geojson: dict, subzones: list[dict]) -> tuple[pd.DataFrame, dict]:
    rows = []
    diagnostics = {"total_centres": 0, "null_or_invalid_fee": 0, "outside_subzones": 0}
    for feature in centres_geojson["features"]:
        diagnostics["total_centres"] += 1
        raw_fee = feature["properties"].get("FULL_DAY_SC_NURSERY_FEE")
        try:
            fee = float(raw_fee)
        except (TypeError, ValueError):
            diagnostics["null_or_invalid_fee"] += 1
            continue
        if not math.isfinite(fee):
            diagnostics["null_or_invalid_fee"] += 1
            continue

        x, y = feature["geometry"]["coordinates"][:2]
        area_name = None
        for subzone in subzones:
            xmin, ymin, xmax, ymax = subzone["bounds"]
            if xmin <= x <= xmax and ymin <= y <= ymax and point_in_geometry(
                x, y, subzone["geometry"]
            ):
                area_name = subzone["planning_area"]
                break
        if area_name is None:
            diagnostics["outside_subzones"] += 1
            continue
        rows.append(
            {
                "planning_area": area_name,
                "centre_name": feature["properties"].get("NAME", ""),
                "fee": fee,
                "longitude": x,
                "latitude": y,
            }
        )
    return pd.DataFrame(rows), diagnostics


def planning_area_centroids(subzones: list[dict]) -> dict[str, tuple[float, float]]:
    pieces: dict[str, list[tuple[float, float, float]]] = {}
    for subzone in subzones:
        area, cx, cy = geometry_area_centroid(subzone["geometry"])
        pieces.setdefault(subzone["planning_area"], []).append((area, cx, cy))
    centroids = {}
    for name, values in pieces.items():
        total = sum(v[0] for v in values)
        centroids[name] = (
            sum(a * x for a, x, _ in values) / total,
            sum(a * y for a, _, y in values) / total,
        )
    return centroids


def knn_weights(centroids: np.ndarray, k: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Symmetric KNN graph and its row-standardised weights matrix."""
    lat0 = np.radians(centroids[:, 1].mean())
    xy = centroids.copy()
    xy[:, 0] *= math.cos(lat0)
    squared = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2)
    np.fill_diagonal(squared, np.inf)
    binary = np.zeros_like(squared)
    for i in range(len(centroids)):
        nearest = np.argsort(squared[i])[:k]
        binary[i, nearest] = 1.0
    binary = np.maximum(binary, binary.T)
    weights = binary / binary.sum(axis=1, keepdims=True)
    return binary, weights


def moran_i(z: np.ndarray, weights: np.ndarray) -> float:
    n = len(z)
    s0 = weights.sum()
    return float((n / s0) * (z @ weights @ z) / (z @ z))


def permutation_inference(
    z: np.ndarray, weights: np.ndarray, permutations: int, seed: int
) -> tuple[float, float, np.ndarray, np.ndarray, np.ndarray]:
    observed = moran_i(z, weights)
    observed_local = z * (weights @ z)
    rng = np.random.default_rng(seed)
    global_perm = np.empty(permutations)
    for p in range(permutations):
        zp = rng.permutation(z)
        global_perm[p] = moran_i(zp, weights)
    expected = -1.0 / (len(z) - 1)
    if observed >= expected:
        global_p = (1 + np.count_nonzero(global_perm >= observed)) / (permutations + 1)
    else:
        global_p = (1 + np.count_nonzero(global_perm <= observed)) / (permutations + 1)
    # Conditional randomisation for each Local Moran statistic: keep z_i fixed
    # and draw its observed number of neighbours from all other locations.
    # The pseudo-p follows the smaller-tail convention used for LISA inference.
    local_p = np.empty(len(z))
    all_indices = np.arange(len(z))
    for i in range(len(z)):
        neighbour_indices = np.flatnonzero(weights[i])
        pool = all_indices[all_indices != i]
        simulated = np.empty(permutations)
        for p in range(permutations):
            sampled = rng.choice(pool, size=len(neighbour_indices), replace=False)
            simulated[p] = z[i] * np.dot(weights[i, neighbour_indices], z[sampled])
        upper_count = np.count_nonzero(simulated >= observed_local[i])
        smaller_tail = min(upper_count, permutations - upper_count)
        local_p[i] = (smaller_tail + 1) / (permutations + 1)
    return observed, float(global_p), global_perm, observed_local, local_p


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    order = np.argsort(p_values)
    ranked = p_values[order]
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.minimum(adjusted, 1.0)
    return result


def feature_patches(subzones: list[dict], value_by_area: dict, missing=np.nan):
    patches, values = [], []
    for subzone in subzones:
        value = value_by_area.get(subzone["planning_area"], missing)
        for polygon in iter_polygons(subzone["geometry"]):
            # Singapore subzones have no consequential holes for these maps.
            patches.append(MplPolygon(np.asarray(polygon[0])[:, :2], closed=True))
            values.append(value)
    return patches, np.asarray(values)


def planning_area_boundary_segments(subzones: list[dict]) -> list[list[tuple[float, float]]]:
    """Return dissolved planning-area boundaries by cancelling shared segments."""
    segments_by_area: dict[str, dict[tuple, tuple]] = {}
    counts_by_area: dict[str, dict[tuple, int]] = {}
    for subzone in subzones:
        area_name = subzone["planning_area"]
        segments_by_area.setdefault(area_name, {})
        counts_by_area.setdefault(area_name, {})
        for polygon in iter_polygons(subzone["geometry"]):
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


def add_planning_area_boundaries(ax, subzones):
    boundaries = planning_area_boundary_segments(subzones)
    ax.add_collection(
        LineCollection(boundaries, colors="#f5f5f5", linewidths=0.55, zorder=3)
    )


def set_map_style(ax):
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()


def draw_fee_map(ax, subzones, area_df, spatial_unit_label="Planning Area"):
    lookup = dict(zip(area_df["planning_area"], area_df["mean_fee_sgd"]))
    patches, values = feature_patches(subzones, lookup)
    # Reverse viridis so higher (more expensive) fees use darker colours.
    collection = PatchCollection(patches, cmap="viridis_r", edgecolor="none", linewidth=0)
    collection.set_antialiased(False)
    collection.set_array(np.ma.masked_invalid(values))
    ax.add_collection(collection)
    add_planning_area_boundaries(ax, subzones)
    ax.autoscale_view()
    set_map_style(ax)
    ax.set_title(
        f"Mean Full-Day SC Nursery Fee by {spatial_unit_label}",
        fontweight="bold",
    )
    cbar = ax.figure.colorbar(collection, ax=ax, fraction=0.032, pad=0.01)
    cbar.set_label("Mean monthly fee (SGD)")
    return collection


CLUSTER_COLORS = {
    "Not significant": "#d9d9d9",
    "High-High": "#d7191c",
    "Low-Low": "#2c7bb6",
    "High-Low": "#fdae61",
    "Low-High": "#abd9e9",
    "No data": "#f7f7f7",
}


def draw_lisa_map(ax, subzones, area_df, spatial_unit_label=None):
    lookup = dict(zip(area_df["planning_area"], area_df["lisa_cluster_p05"]))
    patches, clusters = feature_patches(subzones, lookup, missing="No data")
    colors = [CLUSTER_COLORS[c] for c in clusters]
    collection = PatchCollection(patches, facecolor=colors, edgecolor="none", linewidth=0)
    collection.set_antialiased(False)
    ax.add_collection(collection)
    add_planning_area_boundaries(ax, subzones)
    ax.autoscale_view()
    set_map_style(ax)
    title_suffix = f" by {spatial_unit_label}" if spatial_unit_label else ""
    ax.set_title(f"Local Moran (LISA) Clusters{title_suffix}", fontweight="bold")
    order = ["High-High", "Low-Low", "High-Low", "Low-High", "Not significant"]
    counts = area_df["lisa_cluster_p05"].value_counts().to_dict()
    ax.legend(
        handles=[
            Patch(facecolor=CLUSTER_COLORS[c], label=f"{c} ({counts.get(c, 0)})")
            for c in order
        ],
        loc="lower left",
        frameon=True,
        fontsize=8,
    )


def draw_moran_scatter(
    ax, z, lag, observed_i, p_value, area_names, annotate_names=True
):
    colors = []
    for x, y in zip(z, lag):
        if x >= 0 and y >= 0:
            colors.append(CLUSTER_COLORS["High-High"])
        elif x < 0 and y < 0:
            colors.append(CLUSTER_COLORS["Low-Low"])
        elif x >= 0 and y < 0:
            colors.append(CLUSTER_COLORS["High-Low"])
        else:
            colors.append(CLUSTER_COLORS["Low-High"])
    ax.scatter(z, lag, c=colors, edgecolor="white", linewidth=0.5, s=42)
    extent = max(np.abs(z).max(), np.abs(lag).max()) * 1.08
    xline = np.array([-extent, extent])
    ax.plot(xline, observed_i * xline, color="black", linewidth=1.2)
    ax.axhline(0, color="#777777", linewidth=0.7)
    ax.axvline(0, color="#777777", linewidth=0.7)
    ax.set_xlim(-extent, extent)
    ax.set_ylim(-extent, extent)
    ax.set_xlabel("Standardised mean nursery fee")
    ax.set_ylabel("Spatial lag")
    ax.set_title(
        f"Moran Scatterplot (I: {observed_i:.3f}, p = {p_value:.3f})",
        fontweight="bold",
    )
    quadrant_definitions = [
        ("High-High", (z >= 0) & (lag >= 0), (0.97, 0.96), "right", "top"),
        ("Low-High", (z < 0) & (lag >= 0), (0.03, 0.96), "left", "top"),
        ("Low-Low", (z < 0) & (lag < 0), (0.03, 0.04), "left", "bottom"),
        ("High-Low", (z >= 0) & (lag < 0), (0.97, 0.04), "right", "bottom"),
    ]
    for label, mask, position, horizontal, vertical in quadrant_definitions:
        ax.text(
            *position,
            label,
            transform=ax.transAxes,
            ha=horizontal,
            va=vertical,
            fontsize=10,
            fontweight="bold",
            color=CLUSTER_COLORS[label],
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 2},
        )
    if not annotate_names:
        return

    # Tailored point offsets keep labels close to their markers while avoiding
    # the markers, nearby labels, and the Moran regression line.
    label_layout = {
        "BUKIT MERAH": ((-5, 6), "right", "bottom"),
        "OUTRAM": ((-5, -6), "right", "top"),
        "CHOA CHU KANG": ((5, -7), "left", "top"),
        "BUKIT BATOK": ((-5, 7), "right", "bottom"),
        "MANDAI": ((-5, -6), "right", "top"),
        "SELETAR": ((5, -6), "left", "top"),
        "NEWTON": ((-5, 6), "right", "bottom"),
        "ORCHARD": ((5, 5), "left", "bottom"),
        "RIVER VALLEY": ((-5, -7), "right", "top"),
    }
    index_by_name = {name: i for i, name in enumerate(area_names)}
    for name, (text_offset, horizontal, vertical) in label_layout.items():
        if name not in index_by_name:
            continue
        i = index_by_name[name]
        ax.annotate(
            name.title(),
            xy=(z[i], lag[i]),
            xycoords="data",
            xytext=text_offset,
            textcoords="offset points",
            fontsize=7.3,
            fontweight="bold",
            ha=horizontal,
            va=vertical,
            bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": "none", "alpha": 0.9},
        )


def draw_permutation(ax, permutations, observed_i, expected_i, p_value):
    ax.hist(permutations, bins=30, color="#8da0cb", edgecolor="white")
    ax.axvline(observed_i, color="#d7191c", linewidth=2, label=f"Observed I = {observed_i:.3f}")
    ax.axvline(expected_i, color="black", linestyle="--", linewidth=1.2, label=f"Expected I = {expected_i:.3f}")
    ax.set_xlabel("Moran's I under permutation")
    ax.set_ylabel("Count")
    ax.set_title(
        f"Global Moran's I Monte Carlo Permutation Test (p = {p_value:.3f})",
        fontweight="bold",
    )
    ax.legend(fontsize=8)


def save_individual_plot(draw_function, path: Path, figsize=(9, 7)):
    fig, ax = plt.subplots(figsize=figsize)
    draw_function(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    """Small dependency-free Markdown table formatter."""
    if df.empty:
        return ""
    formatted = df.copy()
    for column in formatted.select_dtypes(include=[np.number]).columns:
        formatted[column] = formatted[column].map(lambda value: f"{value:.4f}")
    headers = [str(column) for column in formatted.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in formatted.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--centres", type=Path, default=Path("data/ChildCareServices_2021.geojson"))
    parser.add_argument("--subzones", type=Path, default=Path("data/MasterPlanSubZones_2019.geojson"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--spatial-unit",
        choices=("planning_area", "subzone"),
        default="planning_area",
        help="Polygon level used to aggregate centre fees",
    )
    parser.add_argument(
        "--skip-overview",
        action="store_true",
        help="Generate only the four standalone plots",
    )
    parser.add_argument("--k", type=int, default=4, help="Number of nearest neighbours")
    parser.add_argument("--permutations", type=int, default=999)
    parser.add_argument("--seed", type=int, default=4015)
    args = parser.parse_args()

    if args.spatial_unit == "subzone":
        name_field = "SUBZONE_N"
        unit_label = "Subzone"
        unit_label_plural = "subzones"
        unit_slug = "subzone"
        default_output_dir = Path("output/spatial_autocorrelation_nursery_fee_subzone")
    else:
        name_field = "PLN_AREA_N"
        unit_label = "Planning Area"
        unit_label_plural = "planning areas"
        unit_slug = "planning_area"
        default_output_dir = Path("output/spatial_autocorrelation_nursery_fee")

    if args.output_dir is None:
        args.output_dir = default_output_dir
    args.output_dir.mkdir(parents=True, exist_ok=True)

    centres_json = load_geojson(args.centres)
    subzones = prepare_subzones(load_geojson(args.subzones), name_field=name_field)
    centre_df, diagnostics = assign_centres(centres_json, subzones)
    area_df = (
        centre_df.groupby("planning_area")["fee"]
        .agg(mean_fee_sgd="mean", median_fee_sgd="median", centre_count="size", fee_sd_sgd="std")
        .reset_index()
        .sort_values("planning_area")
        .reset_index(drop=True)
    )

    centroid_lookup = planning_area_centroids(subzones)
    centroid_array = np.asarray([centroid_lookup[name] for name in area_df["planning_area"]])
    area_df["centroid_lon"] = centroid_array[:, 0]
    area_df["centroid_lat"] = centroid_array[:, 1]
    binary, weights = knn_weights(centroid_array, args.k)

    fees = area_df["mean_fee_sgd"].to_numpy()
    z = (fees - fees.mean()) / fees.std(ddof=0)
    lag = weights @ z
    observed_i, global_p, global_perm, local_i, local_p = permutation_inference(
        z, weights, args.permutations, args.seed
    )
    expected_i = -1.0 / (len(z) - 1)
    local_q = benjamini_hochberg(local_p)

    raw_clusters = np.where(
        (z >= 0) & (lag >= 0), "High-High",
        np.where((z < 0) & (lag < 0), "Low-Low", np.where(z >= 0, "High-Low", "Low-High")),
    )
    area_df["standardised_fee"] = z
    area_df["spatial_lag"] = lag
    area_df["local_moran_i"] = local_i
    area_df["local_permutation_p"] = local_p
    area_df["local_fdr_q"] = local_q
    area_df["lisa_quadrant"] = raw_clusters
    area_df["lisa_cluster_p05"] = np.where(local_p < 0.05, raw_clusters, "Not significant")
    area_df["lisa_cluster_fdr05"] = np.where(local_q < 0.05, raw_clusters, "Not significant")
    area_df["neighbour_count"] = binary.sum(axis=1).astype(int)
    try:
        area_df.rename(columns={"planning_area": unit_slug}).to_csv(
            args.output_dir / f"{unit_slug}_nursery_fee_moran.csv",
            index=False,
        )
    except PermissionError:
        print(f"Warning: {unit_label.lower()} CSV is open/locked; retained the existing copy.")
    try:
        pd.DataFrame({"permutation": np.arange(1, args.permutations + 1), "moran_i": global_perm}).to_csv(
            args.output_dir / "global_moran_permutations.csv", index=False
        )
    except PermissionError:
        print("Warning: permutation CSV is open/locked; retained the existing copy.")

    save_individual_plot(lambda ax: draw_fee_map(ax, subzones, area_df, unit_label), args.output_dir / "nursery_fee_choropleth.png")
    save_individual_plot(
        lambda ax: draw_moran_scatter(
            ax,
            z,
            lag,
            observed_i,
            global_p,
            area_df["planning_area"].to_numpy(),
            annotate_names=args.spatial_unit == "planning_area",
        ),
        args.output_dir / "global_moran_scatterplot.png",
    )
    save_individual_plot(lambda ax: draw_permutation(ax, global_perm, observed_i, expected_i, global_p), args.output_dir / "global_moran_permutation.png")
    save_individual_plot(lambda ax: draw_lisa_map(ax, subzones, area_df, unit_label), args.output_dir / "local_moran_lisa_map.png")

    if not args.skip_overview:
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        draw_fee_map(axes[0, 0], subzones, area_df, unit_label)
        draw_moran_scatter(
            axes[0, 1],
            z,
            lag,
            observed_i,
            global_p,
            area_df["planning_area"].to_numpy(),
            annotate_names=args.spatial_unit == "planning_area",
        )
        draw_permutation(axes[1, 0], global_perm, observed_i, expected_i, global_p)
        draw_lisa_map(axes[1, 1], subzones, area_df, unit_label)
        fig.suptitle(
            "Spatial autocorrelation of FULL_DAY_SC_NURSERY_FEE",
            fontsize=16,
            fontweight="bold",
        )
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        fig.savefig(args.output_dir / "spatial_autocorrelation_overview.png", dpi=220, bbox_inches="tight")
        plt.close(fig)

    significant = area_df.loc[area_df["local_permutation_p"] < 0.05, [
        "planning_area", "mean_fee_sgd", "centre_count", "lisa_cluster_p05", "local_moran_i", "local_permutation_p", "local_fdr_q"
    ]].rename(columns={"planning_area": unit_slug}).sort_values(
        ["lisa_cluster_p05", "local_permutation_p"]
    )
    direction = "positive" if observed_i > expected_i else "negative"
    decision = "statistically significant" if global_p < 0.05 else "not statistically significant"
    summary = f"""# Spatial autocorrelation of full-day SC nursery fees by {unit_label.lower()}

## Method

- Source points: `{args.centres.as_posix()}`; null/non-numeric `FULL_DAY_SC_NURSERY_FEE` records excluded.
- Spatial unit: 2019 {unit_label_plural} (`{name_field}`) from `{args.subzones.as_posix()}`.
- Area statistic: mean centre fee in SGD. The centre count and median are retained for context.
- Spatial weights: symmetric {args.k}-nearest-neighbour graph based on area-weighted {unit_label.lower()} centroids, row-standardised.
- Inference: {args.permutations:,} random permutations, seed {args.seed}. Local p-values are exploratory; Benjamini-Hochberg FDR q-values are also reported.

## Data coverage

- Centre features: {diagnostics['total_centres']:,}
- Excluded null/invalid fees: {diagnostics['null_or_invalid_fee']:,}
- Valid fee points outside a {unit_label.lower()} polygon: {diagnostics['outside_subzones']:,}
- Centres analysed: {len(centre_df):,}
- {unit_label_plural.capitalize()} with at least one valid centre: {len(area_df)}

## Global Moran's I

- Observed I: **{observed_i:.4f}**
- Randomisation expectation: **{expected_i:.4f}**
- Permutation pseudo-p: **{global_p:.4f}**

The area-level mean fees show **{direction} spatial autocorrelation**, and the result is **{decision} at the 5% level** under this weights specification.

## Local Moran clusters (raw permutation p < 0.05)

{dataframe_to_markdown(significant) if len(significant) else f'No {unit_label.lower()} is locally significant at raw p < 0.05.'}

Note: local results involve multiple comparisons. Prefer `local_fdr_q` / `lisa_cluster_fdr05` when confirmatory control of false discoveries is required. Results describe {unit_label.lower()} means, not individual-centre fee similarity.
"""
    (args.output_dir / "analysis_summary.md").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
