"""
BT4015 Group 2 — Spatial autocorrelation of child population density (ages 0-6) by subzone.

Mirrors spatial_autocorrelation_nursery_fee.py but uses child_density_0_6_km2
(children aged 0-6 per km2) from subzone_stats.csv rather than nursery fee data.
Only the 159 HDB subzones (has_hdb == True) are analysed.

Spatial weights: symmetric 4-nearest-neighbour graph on EPSG:3414 subzone centroids,
row-standardised. Inference: 999 permutations, seed 4015.

Outputs  output/spatial_autocorrelation_child_population/
  child_density_choropleth.png
  global_moran_cluster_map.png
  global_moran_scatterplot.png
  global_moran_permutation.png
  local_moran_lisa_map.png
  global_moran_clusters_lisa_side_by_side.png
  spatial_autocorrelation_overview.png
  subzone_child_moran.csv
  global_moran_permutations.csv
  analysis_summary.md

Inputs
  output/subzone_stats.csv
  data/MasterPlanSubZones_2019.geojson

Run:  python scripts/spatial_autocorrelation_child_population.py
Requires: geopandas, pandas, numpy, matplotlib
"""
from __future__ import annotations

import copy
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Polygon as MplPolygon
from matplotlib.collections import PatchCollection
import numpy as np
import pandas as pd
import geopandas as gpd

ROOT    = Path(__file__).resolve().parent.parent
OUT     = ROOT / "output"
OUT_DIR = OUT / "spatial_autocorrelation_child_population"
OUT_DIR.mkdir(parents=True, exist_ok=True)

VARIABLE     = "child_density_0_6_km2"
VAR_LABEL    = "Children aged 0-6 per km\u00b2"
K            = 4
PERMUTATIONS = 999
SEED         = 4015

CLUSTER_COLORS = {
    "Not significant": "#d9d9d9",
    "High-High":       "#d7191c",
    "Low-Low":         "#2c7bb6",
    "High-Low":        "#fdae61",
    "Low-High":        "#abd9e9",
    "No data":         "#eeeeee",
}


# ── Spatial weights ───────────────────────────────────────────────────────────

def knn_weights(xy: np.ndarray, k: int = 4):
    """Symmetric KNN graph and row-standardised weights matrix (coords in metres)."""
    sq = ((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2)
    np.fill_diagonal(sq, np.inf)
    binary = np.zeros_like(sq)
    for i in range(len(xy)):
        binary[i, np.argsort(sq[i])[:k]] = 1.0
    binary = np.maximum(binary, binary.T)
    weights = binary / binary.sum(axis=1, keepdims=True)
    return binary, weights


# ── Moran statistics ──────────────────────────────────────────────────────────

def moran_i(z: np.ndarray, w: np.ndarray) -> float:
    n, s0 = len(z), w.sum()
    return float((n / s0) * (z @ w @ z) / (z @ z))


def permutation_inference(z, w, permutations, seed):
    observed       = moran_i(z, w)
    observed_local = z * (w @ z)
    rng            = np.random.default_rng(seed)

    global_perm = np.empty(permutations)
    for p in range(permutations):
        global_perm[p] = moran_i(rng.permutation(z), w)

    expected = -1.0 / (len(z) - 1)
    if observed >= expected:
        global_p = (1 + np.count_nonzero(global_perm >= observed)) / (permutations + 1)
    else:
        global_p = (1 + np.count_nonzero(global_perm <= observed)) / (permutations + 1)

    local_p  = np.empty(len(z))
    all_idx  = np.arange(len(z))
    for i in range(len(z)):
        nb_idx = np.flatnonzero(w[i])
        pool   = all_idx[all_idx != i]
        sims   = np.empty(permutations)
        for p in range(permutations):
            sampled = rng.choice(pool, size=len(nb_idx), replace=False)
            sims[p] = z[i] * np.dot(w[i, nb_idx], z[sampled])
        upper     = np.count_nonzero(sims >= observed_local[i])
        local_p[i] = (min(upper, permutations - upper) + 1) / (permutations + 1)

    return observed, float(global_p), global_perm, observed_local, local_p


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    order    = np.argsort(p_values)
    ranked   = p_values[order]
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result   = np.empty_like(adjusted)
    result[order] = np.minimum(adjusted, 1.0)
    return result


# ── Geometry / plotting helpers ───────────────────────────────────────────────

def feature_patches(gdf: gpd.GeoDataFrame, value_lookup: dict, missing=np.nan):
    """Return (list[MplPolygon], np.ndarray) from a GeoDataFrame + value lookup."""
    patches, values = [], []
    for _, row in gdf.iterrows():
        val  = value_lookup.get(row["SUBZONE_N"], missing)
        geom = row.geometry
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            patches.append(MplPolygon(np.array(poly.exterior.coords), closed=True))
            values.append(val)
    return patches, np.asarray(values)


def set_map_style(ax):
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()


def add_pa_boundaries(ax, gdf_all):
    """Overlay dissolved planning-area outlines as faint geographic reference."""
    gdf_all.dissolve(by="PLN_AREA_N").boundary.plot(
        ax=ax, color="#f5f5f5", linewidth=0.6, zorder=3,
    )


# ── Individual map / plot draw functions ──────────────────────────────────────

def draw_density_map(ax, gdf, area_df):
    lookup = dict(zip(area_df["SUBZONE_N"], area_df[VARIABLE]))
    patches, values = feature_patches(gdf, lookup)
    cmap = copy.copy(plt.cm.YlOrRd)
    cmap.set_bad("#e0e0e0")
    coll = PatchCollection(patches, cmap=cmap, edgecolor="none", linewidth=0)
    coll.set_antialiased(False)
    coll.set_array(np.ma.masked_invalid(values))
    ax.add_collection(coll)
    add_pa_boundaries(ax, gdf)
    ax.autoscale_view()
    set_map_style(ax)
    ax.set_title(f"Child Population Density by Subzone\n(ages 0-6, per km\u00b2)",
                 fontweight="bold")
    cbar = ax.figure.colorbar(coll, ax=ax, fraction=0.032, pad=0.01)
    cbar.set_label(VAR_LABEL)
    return coll


def draw_global_moran_cluster_map(ax, gdf, area_df, observed_i, expected_i, p_value):
    lookup  = dict(zip(area_df["SUBZONE_N"], area_df["lisa_quadrant"]))
    patches, clusters = feature_patches(gdf, lookup, missing="No data")
    colors  = [CLUSTER_COLORS[str(c)] for c in clusters]
    coll    = PatchCollection(patches, facecolor=colors, edgecolor="none", linewidth=0)
    coll.set_antialiased(False)
    ax.add_collection(coll)
    add_pa_boundaries(ax, gdf)
    ax.autoscale_view()
    set_map_style(ax)
    ax.set_title("Global Moran Clusters by Subzone\n(child density 0-6)", fontweight="bold")
    order  = ["High-High", "Low-Low", "High-Low", "Low-High"]
    counts = area_df["lisa_quadrant"].value_counts().to_dict()
    ax.legend(
        handles=[Patch(facecolor=CLUSTER_COLORS[c], label=f"{c} ({counts.get(c, 0)})")
                 for c in order],
        loc="lower left", frameon=True, fontsize=8,
    )


def draw_lisa_map(ax, gdf, area_df):
    lookup  = dict(zip(area_df["SUBZONE_N"], area_df["lisa_cluster_p05"]))
    patches, clusters = feature_patches(gdf, lookup, missing="No data")
    colors  = [CLUSTER_COLORS[str(c)] for c in clusters]
    coll    = PatchCollection(patches, facecolor=colors, edgecolor="none", linewidth=0)
    coll.set_antialiased(False)
    ax.add_collection(coll)
    add_pa_boundaries(ax, gdf)
    ax.autoscale_view()
    set_map_style(ax)
    ax.set_title("Local Moran (LISA) Clusters by Subzone\n(child density 0-6)", fontweight="bold")
    order  = ["High-High", "Low-Low", "High-Low", "Low-High", "Not significant"]
    counts = area_df["lisa_cluster_p05"].value_counts().to_dict()
    ax.legend(
        handles=[Patch(facecolor=CLUSTER_COLORS[c], label=f"{c} ({counts.get(c, 0)})")
                 for c in order],
        loc="lower left", frameon=True, fontsize=8,
    )


def draw_moran_scatter(ax, z, lag, observed_i, p_value, names):
    colors = []
    for zi, lagi in zip(z, lag):
        if   zi >= 0 and lagi >= 0: colors.append(CLUSTER_COLORS["High-High"])
        elif zi <  0 and lagi <  0: colors.append(CLUSTER_COLORS["Low-Low"])
        elif zi >= 0:                colors.append(CLUSTER_COLORS["High-Low"])
        else:                        colors.append(CLUSTER_COLORS["Low-High"])
    ax.scatter(z, lag, c=colors, edgecolor="white", linewidth=0.5, s=42)
    extent = max(np.abs(z).max(), np.abs(lag).max()) * 1.08
    xline  = np.array([-extent, extent])
    ax.plot(xline, observed_i * xline, color="black", linewidth=1.2)
    ax.axhline(0, color="#777777", linewidth=0.7)
    ax.axvline(0, color="#777777", linewidth=0.7)
    ax.set_xlim(-extent, extent)
    ax.set_ylim(-extent, extent)
    ax.set_xlabel("Standardised child density (0-6 per km\u00b2)")
    ax.set_ylabel("Spatial lag")
    ax.set_title(f"Moran Scatterplot  (I = {observed_i:.3f},  p = {p_value:.3f})",
                 fontweight="bold")
    for label, (xa, ya), (ha, va) in [
        ("High-High", (0.97, 0.96), ("right", "top")),
        ("Low-High",  (0.03, 0.96), ("left",  "top")),
        ("Low-Low",   (0.03, 0.04), ("left",  "bottom")),
        ("High-Low",  (0.97, 0.04), ("right", "bottom")),
    ]:
        ax.text(xa, ya, label, transform=ax.transAxes, ha=ha, va=va,
                fontsize=10, fontweight="bold", color=CLUSTER_COLORS[label],
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 2})
    # Annotate outliers with |z| > 2
    for zi, lagi, name in zip(z, lag, names):
        if abs(zi) > 2 or abs(lagi) > 2:
            ax.annotate(
                name.title(), xy=(zi, lagi), xytext=(5, 4),
                textcoords="offset points", fontsize=7, fontweight="bold",
                bbox={"boxstyle": "round,pad=0.18", "facecolor": "white",
                      "edgecolor": "none", "alpha": 0.9},
            )


def draw_permutation(ax, perm, observed_i, expected_i, p_value):
    ax.hist(perm, bins=30, color="#8da0cb", edgecolor="white")
    ax.axvline(observed_i, color="#d7191c", linewidth=2,
               label=f"Observed I = {observed_i:.3f}")
    ax.axvline(expected_i, color="black", linestyle="--", linewidth=1.2,
               label=f"Expected I = {expected_i:.3f}")
    ax.set_xlabel("Moran's I under permutation")
    ax.set_ylabel("Count")
    ax.set_title(f"Global Moran's I Permutation Test  (p = {p_value:.3f})", fontweight="bold")
    ax.legend(fontsize=8)


def save_plot(draw_fn, path, figsize=(9, 7)):
    fig, ax = plt.subplots(figsize=figsize)
    draw_fn(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path.name}")


def save_side_by_side(path, gdf, area_df, observed_i, expected_i, p_value):
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5))
    draw_global_moran_cluster_map(axes[0], gdf, area_df, observed_i, expected_i, p_value)
    draw_lisa_map(axes[1], gdf, area_df)
    fig.suptitle(
        "Global and Local Moran Analysis — Child Population Density (ages 0-6) by Subzone",
        fontsize=15, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path.name}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # ── Load data ─────────────────────────────────────────────────────────────
    print("Loading subzone stats...")
    stats   = pd.read_csv(OUT / "subzone_stats.csv")
    area_df = stats[stats["has_hdb"] == True].copy()
    area_df["SUBZONE_N"] = area_df["SUBZONE_N"].str.strip().str.upper()
    area_df = area_df.dropna(subset=[VARIABLE]).reset_index(drop=True)
    print(f"  {len(area_df)} HDB subzones with {VARIABLE}")

    print("Loading subzone geometries...")
    gdf = gpd.read_file(ROOT / "data" / "MasterPlanSubZones_2019.geojson").to_crs(epsg=3414)
    gdf["SUBZONE_N"] = gdf["SUBZONE_N"].str.strip().str.upper()

    # Centroids for spatial weights (EPSG:3414, metres)
    centroids = gdf.copy()
    centroids["cx"] = gdf.geometry.centroid.x
    centroids["cy"] = gdf.geometry.centroid.y
    area_df = area_df.merge(
        centroids[["SUBZONE_N", "cx", "cy"]], on="SUBZONE_N", how="left"
    )
    missing_geom = area_df["cx"].isna().sum()
    if missing_geom:
        print(f"  WARNING: {missing_geom} subzones have no matching geometry — dropped")
        area_df = area_df.dropna(subset=["cx", "cy"]).reset_index(drop=True)

    # ── Spatial weights ───────────────────────────────────────────────────────
    print(f"Building k={K} nearest-neighbour weights ({len(area_df)} subzones)...")
    xy = area_df[["cx", "cy"]].to_numpy(float)
    binary, weights = knn_weights(xy, K)

    # ── Moran statistics ──────────────────────────────────────────────────────
    vals = area_df[VARIABLE].to_numpy(float)
    z    = (vals - vals.mean()) / vals.std(ddof=0)
    lag  = weights @ z

    print(f"Running {PERMUTATIONS} permutations (seed={SEED})...")
    observed_i, global_p, global_perm, local_i, local_p = permutation_inference(
        z, weights, PERMUTATIONS, SEED
    )
    expected_i = -1.0 / (len(z) - 1)
    local_q    = benjamini_hochberg(local_p)

    raw_clusters = np.where(
        (z >= 0) & (lag >= 0), "High-High",
        np.where((z < 0) & (lag < 0), "Low-Low",
                 np.where(z >= 0, "High-Low", "Low-High"))
    )
    area_df["standardised_density"] = z
    area_df["spatial_lag"]          = lag
    area_df["local_moran_i"]        = local_i
    area_df["local_permutation_p"]  = local_p
    area_df["local_fdr_q"]          = local_q
    area_df["lisa_quadrant"]        = raw_clusters
    area_df["lisa_cluster_p05"]     = np.where(local_p < 0.05, raw_clusters, "Not significant")
    area_df["lisa_cluster_fdr05"]   = np.where(local_q < 0.05, raw_clusters, "Not significant")
    area_df["neighbour_count"]      = binary.sum(axis=1).astype(int)

    # ── Save CSVs ─────────────────────────────────────────────────────────────
    out_cols = [
        "SUBZONE_N", "PLN_AREA_N", VARIABLE,
        "standardised_density", "spatial_lag", "local_moran_i",
        "local_permutation_p", "local_fdr_q",
        "lisa_quadrant", "lisa_cluster_p05", "lisa_cluster_fdr05", "neighbour_count",
    ]
    area_df[out_cols].to_csv(OUT_DIR / "subzone_child_moran.csv", index=False)
    pd.DataFrame({
        "permutation": np.arange(1, PERMUTATIONS + 1),
        "moran_i":     global_perm,
    }).to_csv(OUT_DIR / "global_moran_permutations.csv", index=False)

    # ── Plots ─────────────────────────────────────────────────────────────────
    print("Saving plots...")
    names = area_df["SUBZONE_N"].to_numpy()

    save_plot(lambda ax: draw_density_map(ax, gdf, area_df),
              OUT_DIR / "child_density_choropleth.png")
    save_plot(lambda ax: draw_global_moran_cluster_map(
                  ax, gdf, area_df, observed_i, expected_i, global_p),
              OUT_DIR / "global_moran_cluster_map.png")
    save_plot(lambda ax: draw_moran_scatter(ax, z, lag, observed_i, global_p, names),
              OUT_DIR / "global_moran_scatterplot.png")
    save_plot(lambda ax: draw_permutation(ax, global_perm, observed_i, expected_i, global_p),
              OUT_DIR / "global_moran_permutation.png")
    save_plot(lambda ax: draw_lisa_map(ax, gdf, area_df),
              OUT_DIR / "local_moran_lisa_map.png")
    save_side_by_side(
        OUT_DIR / "global_moran_clusters_lisa_side_by_side.png",
        gdf, area_df, observed_i, expected_i, global_p,
    )

    # 2x2 overview
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    draw_density_map(axes[0, 0], gdf, area_df)
    draw_moran_scatter(axes[0, 1], z, lag, observed_i, global_p, names)
    draw_permutation(axes[1, 0], global_perm, observed_i, expected_i, global_p)
    draw_lisa_map(axes[1, 1], gdf, area_df)
    fig.suptitle(
        "Spatial Autocorrelation of Child Population Density (ages 0-6) by Subzone",
        fontsize=14, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(OUT_DIR / "spatial_autocorrelation_overview.png", dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("  spatial_autocorrelation_overview.png")

    # ── Analysis summary ──────────────────────────────────────────────────────
    direction = "positive" if observed_i > expected_i else "negative"
    decision  = "statistically significant" if global_p < 0.05 else "not statistically significant"
    sig = area_df.loc[
        area_df["local_permutation_p"] < 0.05,
        ["SUBZONE_N", "PLN_AREA_N", VARIABLE, "lisa_cluster_p05",
         "local_moran_i", "local_permutation_p", "local_fdr_q"],
    ].sort_values(["lisa_cluster_p05", "local_permutation_p"])

    summary = f"""# Spatial autocorrelation of child population density (ages 0-6) by subzone

## Method

- Variable: `{VARIABLE}` (children aged 0-6 per km2, from subzone_stats.csv)
- child_0_6 = child_0_4 + per-subzone share_5_6 * child_5_9 (fallback: flat 40%).
- Spatial unit: 2019 subzones restricted to {len(area_df)} HDB subzones (has_hdb == True).
- Spatial weights: symmetric {K}-nearest-neighbour graph on EPSG:3414 centroids, row-standardised.
- Inference: {PERMUTATIONS:,} random permutations, seed {SEED}.
  Local p-values use conditional randomisation; Benjamini-Hochberg FDR q-values also reported.

## Global Moran's I

- Observed I: **{observed_i:.4f}**
- Expected I (under randomisation): **{expected_i:.4f}**
- Permutation pseudo-p: **{global_p:.4f}**

Child density (ages 0-6) shows **{direction} spatial autocorrelation** across HDB subzones,
and the result is **{decision} at the 5% level**.

## Local Moran clusters (raw permutation p < 0.05)

{sig.to_string(index=False) if len(sig) else "No subzone is locally significant at raw p < 0.05."}

Note: local results involve multiple comparisons. Prefer `local_fdr_q` / `lisa_cluster_fdr05`
for confirmatory inference.
"""
    (OUT_DIR / "analysis_summary.md").write_text(summary, encoding="utf-8")

    print(f"\n{summary}")
    print(f"All outputs -> {OUT_DIR}")


if __name__ == "__main__":
    main()
