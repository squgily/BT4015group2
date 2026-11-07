"""
BT4015 Group 2 — graduated symbol map: continuous child density surface + childcare centres.

Child population (ages 0–6) is rendered as a continuous KDE surface using weighted
Gaussian smoothing on ~13 k HDB block centroids. Childcare centres are shown as
uniform point symbols overlaid on the density surface.

Method
------
Block centroids are weighted by child_0_6 (= child_0_4 + 0.40 * child_5_9, flat-40%
approximation; visually equivalent to the data-driven per-subzone share for a smoothed map),
binned onto a 100 m grid, then convolved with a Gaussian kernel (sigma = BW_M / 100 cells).
Subzone boundaries are drawn at low opacity as geographic reference.

Outputs
  figures/child_centre_kde_map.png

Inputs
  output/hdb_blocks_children_final.gpkg   block polygons + child_0_4, child_5_9 (EPSG:3414)
  output/childcare_centres_2026.gpkg      centre points, layer "centres" (EPSG:3414)
  data/MasterPlanSubZones_2019.geojson    subzone boundaries

Run:  python scripts/plot_child_centre_kde_map.py
Requires: geopandas, pandas, numpy, scipy, matplotlib
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
import numpy as np
import geopandas as gpd
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parent.parent
OUT  = ROOT / "output"
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)

# ── Tuneable parameters ────────────────────────────────────────────────────────
GRID_RES     = 100     # grid cell size in metres
BW_M         = 1200   # Gaussian smoothing bandwidth (sigma) in metres
FLAT_SHARE   = 0.40   # fraction of 5–9 band counted as 5–6
MIN_FRAC     = 0.002  # cells below this fraction of peak are set to NaN (transparent)

CENTRE_COLOUR  = "#2166ac"
CENTRE_SIZE    = 7
CENTRE_ALPHA   = 0.75
BOUNDARY_ALPHA = 0.22
BOUNDARY_LW    = 0.4
LAND_FILL      = "#e8e8e8"
LAND_OUTLINE   = "#888888"
# ──────────────────────────────────────────────────────────────────────────────


def shapely_to_mpl_path(geom):
    """Convert a shapely Polygon or MultiPolygon to a matplotlib Path for clip masking."""
    polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    vertices, codes = [], []
    for poly in polys:
        for ring in [poly.exterior] + list(poly.interiors):
            coords = np.array(ring.coords)
            vertices.append(coords)
            ring_codes = (
                [MplPath.MOVETO]
                + [MplPath.LINETO] * (len(coords) - 2)
                + [MplPath.CLOSEPOLY]
            )
            codes.extend(ring_codes)
    return MplPath(np.vstack(vertices), codes)


def main():
    # ── Load blocks ───────────────────────────────────────────────────────────
    print("Loading HDB blocks...")
    blk = gpd.read_file(OUT / "hdb_blocks_children_final.gpkg", layer="hdb_blocks_children")
    # CRS is already EPSG:3414 (metres)
    blk["child_0_6"] = blk["child_0_4"] + FLAT_SHARE * blk["child_5_9"]
    blk = blk[blk["child_0_6"].fillna(0) > 0].copy()
    print(f"  {len(blk):,} residential blocks with children > 0")

    cx = blk.geometry.centroid.x.values
    cy = blk.geometry.centroid.y.values
    w  = blk["child_0_6"].values

    # ── Load centres ──────────────────────────────────────────────────────────
    print("Loading childcare centres...")
    centres = gpd.read_file(OUT / "childcare_centres_2026.gpkg", layer="centres")
    # CRS is already EPSG:3414
    print(f"  {len(centres):,} centres")

    # ── Load subzones ─────────────────────────────────────────────────────────
    print("Loading subzone boundaries...")
    subzones = gpd.read_file(ROOT / "data" / "MasterPlanSubZones_2019.geojson").to_crs(epsg=3414)
    sg_land  = subzones.union_all()

    # ── Build KDE grid ────────────────────────────────────────────────────────
    print(f"Building {GRID_RES} m grid with sigma = {BW_M} m ...")
    pad   = int(BW_M * 4)
    x_min = cx.min() - pad;  x_max = cx.max() + pad
    y_min = cy.min() - pad;  y_max = cy.max() + pad

    xi = np.arange(x_min, x_max, GRID_RES)
    yi = np.arange(y_min, y_max, GRID_RES)
    density = np.zeros((len(yi), len(xi)), dtype=np.float64)

    # Bin weighted centroids into grid
    ix_idx = ((cx - x_min) / GRID_RES).astype(int)
    iy_idx = ((cy - y_min) / GRID_RES).astype(int)
    valid  = (ix_idx >= 0) & (ix_idx < len(xi)) & (iy_idx >= 0) & (iy_idx < len(yi))
    np.add.at(density, (iy_idx[valid], ix_idx[valid]), w[valid])

    # Gaussian smooth
    sigma          = BW_M / GRID_RES
    density_smooth = gaussian_filter(density, sigma=sigma)
    peak           = density_smooth.max()
    density_plot   = np.where(density_smooth >= peak * MIN_FRAC, density_smooth, np.nan)
    print(f"  Grid: {len(xi)} × {len(yi)} cells; peak density = {peak:.2f}")

    # ── Compose figure ────────────────────────────────────────────────────────
    print("Composing figure...")
    fig, ax = plt.subplots(figsize=(14, 12))
    ax.set_aspect("equal")
    ax.set_axis_off()
    fig.patch.set_facecolor("white")

    # Land background
    subzones.plot(ax=ax, facecolor=LAND_FILL, edgecolor="none", zorder=0)

    # KDE raster
    extent = [x_min, x_max, y_min, y_max]
    im = ax.imshow(
        density_plot,
        extent=extent,
        origin="lower",
        cmap="YlOrRd",
        alpha=0.88,
        interpolation="bilinear",
        zorder=1,
    )

    # Clip raster to Singapore land (prevents bleed into sea)
    sg_mpl_path = shapely_to_mpl_path(sg_land)
    sg_patch    = PathPatch(sg_mpl_path, transform=ax.transData)
    im.set_clip_path(sg_patch)

    # Faint subzone boundaries as geographic reference
    subzones.plot(
        ax=ax, facecolor="none", edgecolor="white",
        linewidth=BOUNDARY_LW, alpha=BOUNDARY_ALPHA, zorder=2,
    )

    # Singapore land outline
    subzones.dissolve().boundary.plot(
        ax=ax, color=LAND_OUTLINE, linewidth=0.8, zorder=3,
    )

    # Childcare centres — uniform graduated symbols
    centres.plot(
        ax=ax,
        color=CENTRE_COLOUR,
        markersize=CENTRE_SIZE,
        alpha=CENTRE_ALPHA,
        zorder=5,
        marker="o",
    )

    # Colourbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.022, pad=0.01, shrink=0.55, aspect=30)
    cbar.set_label(
        f"Child population density (ages 0–6)\nGaussian KDE, σ = {BW_M // 1000}.{BW_M % 1000 // 100} km",
        fontsize=10,
    )
    cbar.set_ticks([])

    # Legend
    centre_patch = mpatches.Patch(color=CENTRE_COLOUR,
                                   label=f"Childcare centres  (n = {len(centres):,})")
    ax.legend(handles=[centre_patch], loc="lower left", fontsize=10,
              frameon=True, framealpha=0.9)

    ax.set_title(
        "Child Population Density (ages 0–6) and Childcare Centres — Singapore HDB",
        fontsize=14, fontweight="bold", pad=14,
    )

    out_path = FIGS / "child_centre_kde_map.png"
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    main()
