"""Moran's I helpers shared by the hypothesis-testing notebooks (3_01, 3_03, 3_04).

Everything here is Daryl's code from ``scripts/spatial_autocorrelation_nursery_fee.py`` (pure
numpy / matplotlib, no GeoPandas), moved into a module so that 3_01 (nursery fees), 3_03 (GWR
residual Moran) and 3_04 (child density, Kenneth) use one copy.  The statistical logic is
unchanged.  Two deliberate edits, both dated 2026-11-10:

* ``knn_weights`` takes ``lonlat`` so the same function serves Daryl's lon/lat centroids (cosine
  correction of longitude) and Kenneth's EPSG:3414 metre centroids (no correction).
* The map and plot colours follow the project palette in ``docs/notebook_style.md`` (LISA
  high-high red, low-low blue, light tints for the spatial outliers, grey for not significant;
  text in dark grey).  Daryl's original ``#d7191c`` / ``#2c7bb6`` colours are replaced.

Moran's I is computed as I = (n / S0) * z' W z / z' z on standardised values z, with a
row-standardised symmetric k-nearest-neighbour weights matrix W.  Global inference is a
permutation test; local inference uses conditional randomisation (Anselin 1995) with the
smaller-tail pseudo p-value convention used for LISA maps.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.colors import BoundaryNorm, ListedColormap, Normalize
from matplotlib.patches import Patch, Polygon as MplPolygon

# Project palette (docs/notebook_style.md).  changed 2026-11-10: replaces Daryl's ColorBrewer set.
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#8a8984"
BLUE, ORANGE = "#2a78d6", "#eb6834"
CLUSTER_COLORS = {
    "Not significant": "#efeeea",
    "High-High": "#e34948",
    "Low-Low": "#2a78d6",
    "High-Low": "#f3b3b2",
    "Low-High": "#b7d3f6",
    "No data": "#f7f7f7",
}

# Fee class breaks for the subzone choropleth (Daryl's stepped scale).
FEE_BOUNDS = np.asarray([600, 620, 640, 700, 1200, 1700, 2200, 3000], dtype=float)
FEE_BIN_LABELS = [
    "S$600–619",
    "S$620–639",
    "S$640–699",
    "S$700–1,199",
    "S$1,200–1,699",
    "S$1,700–2,199",
    "S$2,200–2,999",
]


# ── GeoJSON geometry utilities ───────────────────────────────────────────────

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
    """True if (x, y) is inside any polygon of the geometry and outside its holes."""
    for polygon in iter_polygons(geometry):
        if point_in_ring(x, y, polygon[0]) and not any(
            point_in_ring(x, y, hole) for hole in polygon[1:]
        ):
            return True
    return False


def ring_area_centroid(ring: list[list[float]]) -> tuple[float, float, float]:
    """Return absolute area and centroid for a ring in lon/lat planar units (shoelace formula)."""
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
    """Area-weighted centroid of a (Multi)Polygon; holes subtract from the outer ring."""
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
    """Read a GeoJSON file into a dict."""
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def prepare_subzones(subzones_geojson: dict, name_field: str = "PLN_AREA_N") -> list[dict]:
    """One record per subzone feature: the aggregation name, raw geometry and a bounding box.

    ``name_field`` is ``PLN_AREA_N`` for a planning-area analysis (several subzone pieces share a
    name and are merged later) or ``SUBZONE_N`` for a subzone analysis.
    """
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


# ── Point-in-polygon assignment and area centroids ───────────────────────────

def assign_centres(centres_geojson: dict, subzones: list[dict]) -> tuple[pd.DataFrame, dict]:
    """Assign each centre with a valid ``FULL_DAY_SC_NURSERY_FEE`` to the polygon containing it.

    Returns a DataFrame (planning_area, centre_name, fee, longitude, latitude) and a diagnostics
    dict counting the features, the null/invalid fees and the points outside every polygon.
    """
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
    """Area-weighted centroid per aggregation name, merging the subzone pieces of each area."""
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


# ── Spatial weights and Moran statistics ─────────────────────────────────────

def knn_weights(centroids: np.ndarray, k: int = 4, lonlat: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Symmetric KNN graph and its row-standardised weights matrix.

    ``centroids`` is an (n, 2) array.  With ``lonlat=True`` (Daryl's planning-area and subzone
    runs) longitude is scaled by cos(mean latitude) so that distances are roughly isotropic; with
    ``lonlat=False`` (Kenneth's EPSG:3414 centroids, already in metres) the coordinates are used as
    they are.  changed 2026-11-10: the flag merges the two teammates' identical functions.
    The graph is symmetrised (i-j if either is in the other's k nearest), so some units have more
    than k neighbours.
    """
    xy = np.asarray(centroids, dtype=float).copy()
    if lonlat:
        lat0 = np.radians(xy[:, 1].mean())
        xy[:, 0] *= math.cos(lat0)
    squared = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2)
    np.fill_diagonal(squared, np.inf)
    binary = np.zeros_like(squared)
    for i in range(len(xy)):
        nearest = np.argsort(squared[i])[:k]
        binary[i, nearest] = 1.0
    binary = np.maximum(binary, binary.T)
    weights = binary / binary.sum(axis=1, keepdims=True)
    return binary, weights


def moran_i(z: np.ndarray, weights: np.ndarray) -> float:
    """Global Moran's I of standardised values z under weights matrix W."""
    n = len(z)
    s0 = weights.sum()
    return float((n / s0) * (z @ weights @ z) / (z @ z))


def permutation_inference(
    z: np.ndarray, weights: np.ndarray, permutations: int, seed: int
) -> tuple[float, float, np.ndarray, np.ndarray, np.ndarray]:
    """Global and local Moran's I with permutation pseudo p-values.

    Returns (observed I, global pseudo-p, permuted I values, local I_i, local pseudo-p_i).
    The global p is one-sided in the direction of the observed statistic relative to the
    expectation -1/(n-1).  Local p uses conditional randomisation: z_i is held fixed and its
    neighbours' values are drawn from all other locations; the pseudo-p takes the smaller tail.
    """
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
    """Benjamini-Hochberg FDR-adjusted p-values (q-values), capped at 1."""
    p_values = np.asarray(p_values, dtype=float)
    order = np.argsort(p_values)
    ranked = p_values[order]
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.minimum(adjusted, 1.0)
    return result


def lisa_quadrants(z: np.ndarray, lag: np.ndarray) -> np.ndarray:
    """Moran-scatter quadrant label per unit from standardised value and spatial lag."""
    return np.where(
        (z >= 0) & (lag >= 0), "High-High",
        np.where((z < 0) & (lag < 0), "Low-Low", np.where(z >= 0, "High-Low", "Low-High")),
    )


# ── Map helpers (GeoJSON dict based) ─────────────────────────────────────────

def feature_patches(subzones: list[dict], value_by_area: dict, missing=np.nan):
    """Matplotlib polygon patches for every subzone piece, with the value of its aggregation name."""
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


def add_planning_area_boundaries(ax, subzones, color="#f5f5f5", linewidth=0.55):
    """Overlay the dissolved outlines as a faint geographic reference."""
    boundaries = planning_area_boundary_segments(subzones)
    ax.add_collection(
        LineCollection(boundaries, colors=color, linewidths=linewidth, zorder=3)
    )


def set_map_style(ax):
    """Equal aspect, no axes: a map."""
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()


# ── Draw functions ───────────────────────────────────────────────────────────

def draw_fee_map(ax, subzones, area_df, spatial_unit_label="Planning Area"):
    """Choropleth of median fee: continuous blues at planning-area level, stepped at subzone level."""
    lookup = dict(zip(area_df["planning_area"], area_df["median_fee_sgd"]))
    patches, values = feature_patches(subzones, lookup)
    is_planning_area = spatial_unit_label == "Planning Area"
    if is_planning_area:
        # Planning-area values are repeated over their constituent subzone
        # pieces.  Suppressing polygon edges and drawing only the dissolved
        # planning-area outline makes those pieces read as one merged area.
        cmap = plt.cm.Blues.copy()
        norm = Normalize(
            vmin=float(np.nanmin(values)),
            vmax=float(np.nanmax(values)),
        )
        edgecolor = "none"
        linewidth = 0
    else:
        # Preserve the enhanced stepped scale on the more granular subzone map.
        blue_shades = plt.cm.Blues(np.linspace(0.25, 0.95, len(FEE_BIN_LABELS)))
        cmap = ListedColormap(blue_shades, name="nursery_fee_blues")
        norm = BoundaryNorm(FEE_BOUNDS, cmap.N, clip=True)
        edgecolor = "white"
        linewidth = 0.25
    cmap.set_bad("#e0e0e0")
    collection = PatchCollection(
        patches,
        cmap=cmap,
        norm=norm,
        edgecolor=edgecolor,
        linewidth=linewidth,
    )
    collection.set_antialiased(False)
    collection.set_array(np.ma.masked_invalid(values))
    ax.add_collection(collection)
    add_planning_area_boundaries(
        ax,
        subzones,
        color="#ffffff" if is_planning_area else "#f5f5f5",
        linewidth=0.8 if is_planning_area else 0.55,
    )
    ax.autoscale_view()
    set_map_style(ax)
    title = f"Median Full-Day SC Nursery Fee by {spatial_unit_label}"
    if is_planning_area:
        title += "\n(median monthly fee, SGD)"
    ax.set_title(title, fontweight="bold", pad=11 if is_planning_area else None)
    if is_planning_area:
        # Match the child-density choropleth's narrow continuous scale and
        # map-to-legend proportions.
        cbar = ax.figure.colorbar(collection, ax=ax, fraction=0.032, pad=0.01)
        cbar.set_label("Median monthly nursery fee (SGD)")
    else:
        tick_positions = (FEE_BOUNDS[:-1] + FEE_BOUNDS[1:]) / 2
        cbar = ax.figure.colorbar(
            collection,
            ax=ax,
            boundaries=FEE_BOUNDS,
            ticks=tick_positions,
            fraction=0.05,
            pad=0.018,
            spacing="uniform",
            drawedges=True,
        )
        cbar.ax.set_yticklabels(FEE_BIN_LABELS)
        cbar.ax.tick_params(labelsize=8, length=0, pad=5)
        cbar.set_label("Median monthly nursery fee", fontweight="bold", labelpad=10)
        cbar.outline.set_linewidth(0.8)
        cbar.dividers.set_color("white")
        cbar.dividers.set_linewidth(0.8)
    return collection


def draw_global_moran_cluster_map(ax, subzones, area_df, spatial_unit_label="Planning Area"):
    """Map each polygon to its quadrant in the Global Moran scatterplot (no significance filter)."""
    lookup = dict(zip(area_df["planning_area"], area_df["lisa_quadrant"]))
    patches, clusters = feature_patches(subzones, lookup, missing="No data")
    colors = [CLUSTER_COLORS[cluster] for cluster in clusters]
    collection = PatchCollection(patches, facecolor=colors, edgecolor="none", linewidth=0)
    collection.set_antialiased(False)
    ax.add_collection(collection)
    add_planning_area_boundaries(ax, subzones)
    ax.autoscale_view()
    set_map_style(ax)
    ax.set_title(f"Global Moran Clusters by {spatial_unit_label}", fontweight="bold")
    order = ["High-High", "Low-Low", "High-Low", "Low-High"]
    counts = area_df["lisa_quadrant"].value_counts().to_dict()
    ax.legend(
        handles=[
            Patch(facecolor=CLUSTER_COLORS[cluster], label=f"{cluster} ({counts.get(cluster, 0)})")
            for cluster in order
        ],
        loc="lower left",
        frameon=True,
        fontsize=8,
    )
    return collection


def draw_lisa_map(ax, subzones, area_df, spatial_unit_label=None, column="lisa_cluster_p05"):
    """Map of significant local Moran clusters (p < 0.05 by default)."""
    lookup = dict(zip(area_df["planning_area"], area_df[column]))
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
    counts = area_df[column].value_counts().to_dict()
    ax.legend(
        handles=[
            Patch(facecolor=CLUSTER_COLORS[c], label=f"{c} ({counts.get(c, 0)})")
            for c in order
        ],
        loc="lower left",
        frameon=True,
        fontsize=8,
    )


# Tailored point offsets keep the planning-area labels close to their markers while avoiding
# the markers, nearby labels, and the Moran regression line (Daryl's layout).
_SCATTER_LABEL_LAYOUT = {
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


def draw_moran_scatter(
    ax, z, lag, observed_i, p_value, area_names, annotate_names=True,
    xlabel="Standardised median nursery fee", label_layout=None, annotate_outliers=False,
):
    """Moran scatterplot (z against its spatial lag) with the I slope and quadrant colours.

    ``annotate_names`` labels the planning areas in ``label_layout`` (default: Daryl's layout);
    ``annotate_outliers`` labels every unit with |z| > 2 or |lag| > 2 (Kenneth's subzone rule).
    """
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
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Spatial lag")
    ax.set_title(
        f"Moran Scatterplot (I: {observed_i:.3f}, p = {p_value:.3f})",
        fontweight="bold",
    )
    quadrant_definitions = [
        ("High-High", (0.97, 0.96), "right", "top"),
        ("Low-High", (0.03, 0.96), "left", "top"),
        ("Low-Low", (0.03, 0.04), "left", "bottom"),
        ("High-Low", (0.97, 0.04), "right", "bottom"),
    ]
    for label, position, horizontal, vertical in quadrant_definitions:
        ax.text(
            *position,
            label,
            transform=ax.transAxes,
            ha=horizontal,
            va=vertical,
            fontsize=10,
            fontweight="bold",
            color=INK2,  # changed 2026-11-10: text in dark grey, not the series colour
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 2},
        )
    if annotate_outliers:
        for zi, lagi, name in zip(z, lag, area_names):
            if abs(zi) > 2 or abs(lagi) > 2:
                ax.annotate(
                    str(name).title(), xy=(zi, lagi), xytext=(5, 4),
                    textcoords="offset points", fontsize=7, fontweight="bold",
                    bbox={"boxstyle": "round,pad=0.18", "facecolor": "white",
                          "edgecolor": "none", "alpha": 0.9},
                )
    if not annotate_names:
        return
    layout = _SCATTER_LABEL_LAYOUT if label_layout is None else label_layout
    index_by_name = {name: i for i, name in enumerate(area_names)}
    for name, (text_offset, horizontal, vertical) in layout.items():
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
    """Histogram of Moran's I under permutation with the observed and expected values marked."""
    ax.hist(permutations, bins=30, color=BLUE, edgecolor="white")
    ax.axvline(observed_i, color=ORANGE, linewidth=2, label=f"Observed I = {observed_i:.3f}")
    ax.axvline(expected_i, color="black", linestyle="--", linewidth=1.2, label=f"Expected I = {expected_i:.3f}")
    ax.set_xlabel("Moran's I under permutation")
    ax.set_ylabel("Count")
    ax.set_title(
        f"Global Moran's I Monte Carlo Permutation Test (p = {p_value:.3f})",
        fontweight="bold",
    )
    ax.legend(fontsize=8)


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    """Small dependency-free Markdown table formatter (numbers to 4 d.p.)."""
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
