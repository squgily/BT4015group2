"""
Figures for the supply-pressure index (reframed H-c). Run after pressure_index.py and
planned_centre_impact.py.

  figures/pressure_index_lisa.png        subzone pressure choropleth (left) + LISA cluster map (right)
  figures/pressure_vs_fee.png            subzone scatter: pressure vs median listed Nursery fee, quadrants
  figures/planned_centres_on_pressure.png pressure choropleth with ECDA's planned centres sized by catchment

Palette: one-hue blue ramp for magnitude; LISA HH red / LL blue with light tints for HL / LH and grey
for not significant; planned centres orange. Text in ink tokens, never series colour.
"""
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyogrio  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT, FIG = ROOT / "output", ROOT / "figures"
MIRROR = Path("/Users/anhminhhoang/GIS/New-Project-BT4015/figures")
INK, INK2, INK3, SURF, GRID = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb", "#e6e5e1"
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
LISA = {"HH": "#e34948", "HL": "#f3b3b2", "LH": "#b7d3f6", "LL": "#2a78d6", "ns": "#efeeea"}
ORANGE = "#eb6834"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "savefig.facecolor": SURF})


def base_map(ax, sz):
    sz.plot(ax=ax, color="#f4f3f0", edgecolor="white", linewidth=0.3)
    ax.set_axis_off()


def choropleth(ax, sp, col, title, bins):
    cmap = ListedColormap(BLUES[:len(bins) - 1])
    norm = BoundaryNorm(bins, cmap.N)
    h = sp[sp[col].notna()]
    h.plot(ax=ax, column=col, cmap=cmap, norm=norm, edgecolor="white", linewidth=0.3)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=8)
    handles = [Patch(facecolor=BLUES[i], edgecolor="none", label=f"{bins[i]:g}–{bins[i + 1]:g}") for i in range(len(bins) - 1)]
    ax.legend(handles=handles, title="children 0–6 per reachable centre", loc="lower right", frameon=False,
              fontsize=8, title_fontsize=8, ncol=1)


def numbered_key(ax, gdf, title, col=None, n=None, point=False, extra=None, loc=(0.01, 0.30)):
    """Small numbered circles on the map + a key in the empty sea area, so labels never collide."""
    g = gdf.sort_values(col, ascending=False).head(n) if col else gdf
    lines = []
    for k, (_, r) in enumerate(g.iterrows(), 1):
        c = r.geometry if point else r.geometry.representative_point()
        ax.annotate(str(k), (c.x, c.y), fontsize=6.5, color="white", ha="center", va="center", fontweight="bold",
                    bbox=dict(boxstyle="circle,pad=0.18", fc=INK, ec="white", lw=0.6), zorder=8)
        lines.append(f"{k:>2}  {r['SUBZONE_N'].title()}" + (f"  {extra(r)}" if extra else ""))
    ax.text(loc[0], loc[1], title + "\n" + "\n".join(lines), transform=ax.transAxes, fontsize=7, color=INK,
            va="top", ha="left", family="DejaVu Sans Mono", linespacing=1.35)


def main():
    FIG.mkdir(exist_ok=True)
    sz = pyogrio.read_dataframe(OUT / "hdb_blocks.gpkg", layer="subzones")
    sp = pyogrio.read_dataframe(OUT / "hdb_blocks.gpkg", layer="subzone_pressure")
    h = sp[sp["has_hdb"] & sp["pressure_base"].notna()]
    q = h["pressure_base"].quantile([0, .2, .4, .6, .8, .95, 1]).to_numpy()
    bins = np.unique(np.round(q, -1)); bins[0], bins[-1] = np.floor(q[0]), np.ceil(q[-1])

    # ---- figure 1: pressure + LISA
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5))
    for ax in axes:
        base_map(ax, sz)
    choropleth(axes[0], h, "pressure_base", "Supply pressure: children 0–6 per centre within a 10-min walk", bins)
    numbered_key(axes[0], h, "Highest pressure (children per centre)", col="pressure_base", n=10,
                 extra=lambda r: f"{r['pressure_base']:,.0f}")
    ax = axes[1]
    for lab, colr in LISA.items():
        g = h[h["lisa_q"].eq(lab)]
        if len(g):
            g.plot(ax=ax, color=colr, edgecolor="white", linewidth=0.3)
    ax.set_title("LISA clusters of (log) pressure, Queen contiguity, 9,999 permutations", loc="left", fontsize=11, pad=8)
    names = {"HH": "High-high: weak-link cluster", "HL": "High-low: isolated hotspot", "LH": "Low-high", "LL": "Low-low: well supplied", "ns": "Not significant (p ≥ 0.05)"}
    ax.legend(handles=[Patch(facecolor=LISA[k], edgecolor="none", label=names[k]) for k in LISA], loc="lower right", frameon=False, fontsize=8)
    numbered_key(ax, h[h["lisa_q"].eq("HH")], "High-high cluster", col="pressure_base",
                 extra=lambda r: f"{r['PLN_AREA_N'].title()}")
    fig.text(0.01, 0.01, "HDB blocks only; each centre = one unit (capacity not used). Subzones without HDB in light grey. "
             "Sources: ECDA Oct 2026 centres (1,796), HDB blocks, SingStat 2026, OSRM foot network.", fontsize=7, color=INK3)
    fig.tight_layout()
    fig.savefig(FIG / "pressure_index_lisa.png", dpi=170)
    plt.close(fig)

    # ---- figure 2: pressure vs fee scatter
    s = h[h["median_fee_listed"].notna()].copy()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(s["median_fee_listed"], s["pressure_base"], s=np.clip(s["children_0_6"] / 40, 10, 160), color="#2a78d6",
               alpha=0.75, edgecolor="white", linewidth=0.8)
    xm, ym = s["median_fee_listed"].median(), s["pressure_base"].median()
    ax.axvline(xm, color=GRID, lw=1); ax.axhline(ym, color=GRID, lw=1)
    ax.set_ylim(0, s["pressure_base"].max() * 1.18)
    ax.set_xlabel("Median listed full-day Nursery fee in subzone (S$/month)")
    ax.set_ylabel("Children 0–6 per reachable centre (10-min walk)")
    ax.set_title("Where is the barrier cost, and where is it capacity?", loc="left", fontsize=11, pad=8)
    ax.text(0.98, 0.97, "high pressure, high fee\n→ anchor-operator candidates", transform=ax.transAxes, ha="right", va="top", fontsize=8, color=INK2)
    ax.text(0.02, 0.97, "high pressure, low fee\n→ capacity, not affordability", transform=ax.transAxes, ha="left", va="top", fontsize=8, color=INK2)
    ax.text(0.02, 0.03, "low pressure, low fee", transform=ax.transAxes, ha="left", va="bottom", fontsize=8, color=INK3)
    ax.text(0.98, 0.03, "low pressure, high fee", transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=INK3)
    for _, r in s.sort_values("pressure_base", ascending=False).head(8).iterrows():
        ax.annotate(r["SUBZONE_N"].title(), (r["median_fee_listed"], r["pressure_base"]), fontsize=7, color=INK,
                    xytext=(4, 3), textcoords="offset points")
    for sp_ in ("top", "right"):
        ax.spines[sp_].set_visible(False)
    ax.grid(color=GRID, lw=0.5); ax.set_axisbelow(True)
    fig.text(0.01, 0.01, "Point size = children 0–6 in subzone. Lines = medians. HDB subzones with ≥100 children and a listed fee.", fontsize=7, color=INK3)
    fig.tight_layout()
    fig.savefig(FIG / "pressure_vs_fee.png", dpi=170)
    plt.close(fig)

    # ---- figure 3: planned centres on pressure
    imp = pd.read_csv(OUT / "planned_centre_impact.csv")
    pl = pyogrio.read_dataframe(OUT / "childcare_centres_2026.gpkg", layer="planned").merge(imp[["tp_code", "pool_children_0_6"]], on="tp_code")
    fig, ax = plt.subplots(figsize=(9, 6.5))
    base_map(ax, sz)
    choropleth(ax, h, "pressure_base", "ECDA's 13 planned centres against today's supply pressure", bins)
    pl.plot(ax=ax, color=ORANGE, markersize=np.clip(pl["pool_children_0_6"] / 12, 12, 220), edgecolor="white", linewidth=0.8, zorder=5)
    pl = pl.sort_values("pool_children_0_6", ascending=False).reset_index(drop=True)
    numbered_key(ax, pl, "Planned centres (children 0–6 within 10 min)", point=True,
                 extra=lambda r: f"{r['pool_children_0_6']:,.0f}  {r['expected_opening']}", loc=(0.01, 0.42))
    ax.scatter([], [], color=ORANGE, s=60, label="planned centre (size = children 0–6 within 10 min)")
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    fig.text(0.01, 0.01, "Planned list: ECDA Oct 2026, verified by Jessie (output/childcare_centres_2026.gpkg, layer planned).", fontsize=7, color=INK3)
    fig.tight_layout()
    fig.savefig(FIG / "planned_centres_on_pressure.png", dpi=170)
    plt.close(fig)

    MIRROR.mkdir(exist_ok=True)
    for f in ("pressure_index_lisa.png", "pressure_vs_fee.png", "planned_centres_on_pressure.png"):
        shutil.copy(FIG / f, MIRROR / f)
    print("figures written:", ", ".join(str(FIG / f) for f in ("pressure_index_lisa.png", "pressure_vs_fee.png", "planned_centres_on_pressure.png")))


if __name__ == "__main__":
    main()
