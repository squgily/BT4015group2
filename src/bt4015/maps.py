"""Map helpers for the pressure-index figures (3_07, 3_08), from Minh's
``scripts/make_pressure_figures.py`` and ``scripts/make_deck_figures.py``.

Palette: one-hue blue ramp for magnitude; LISA HH red / LL blue with light tints for HL / LH and grey
for not significant; planned centres orange. Text in ink tokens, never series colour.
"""
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

INK, INK2, INK3, SURF, GRID = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb", "#e6e5e1"
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
LISA = {"HH": "#e34948", "HL": "#f3b3b2", "LH": "#b7d3f6", "LL": "#2a78d6", "ns": "#efeeea"}
LISA_NAMES = {"HH": "High-high: weak-link cluster", "HL": "High-low: isolated hotspot", "LH": "Low-high",
              "LL": "Low-low: well supplied", "ns": "Not significant (p ≥ 0.05)"}
BLUE, BLUE_L, RED, ORANGE = "#2a78d6", "#9ec5f4", "#e34948", "#eb6834"


def use_deck_style():
    """Apply the deck's rcParams (DejaVu Sans, ink text, off-white surface)."""
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURF,
                         "axes.facecolor": SURF, "savefig.facecolor": SURF})


def tidy(ax):
    """Drop the top/right spines and draw a light grid behind the data."""
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(color=GRID, lw=0.5)
    ax.set_axisbelow(True)


def pressure_bins(values):
    """Class breaks for the pressure choropleth: quantiles rounded to tens, floor/ceil at the ends."""
    q = values.quantile([0, .2, .4, .6, .8, .95, 1]).to_numpy()
    bins = np.unique(np.round(q, -1))
    bins[0], bins[-1] = np.floor(q[0]), np.ceil(q[-1])
    return bins


def base_map(ax, sz):
    """All subzones in light grey, no axes."""
    sz.plot(ax=ax, color="#f4f3f0", edgecolor="white", linewidth=0.3)
    ax.set_axis_off()


def choropleth(ax, sp, col, title, bins, legend_title="children 0–6 per reachable centre"):
    """Classed single-hue choropleth of `col` with a patch legend."""
    cmap = ListedColormap(BLUES[:len(bins) - 1])
    norm = BoundaryNorm(bins, cmap.N)
    h = sp[sp[col].notna()]
    h.plot(ax=ax, column=col, cmap=cmap, norm=norm, edgecolor="white", linewidth=0.3)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=8)
    handles = [Patch(facecolor=BLUES[i], edgecolor="none", label=f"{bins[i]:g}–{bins[i + 1]:g}") for i in range(len(bins) - 1)]
    ax.legend(handles=handles, title=legend_title, loc="lower right", frameon=False, fontsize=8, title_fontsize=8, ncol=1)


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


def lisa_map(ax, h, col="lisa_q", title="LISA clusters of (log) pressure, Queen contiguity, 9,999 permutations"):
    """Categorical LISA map (HH / HL / LH / LL / ns) with the standard legend."""
    for lab, colr in LISA.items():
        g = h[h[col].eq(lab)]
        if len(g):
            g.plot(ax=ax, color=colr, edgecolor="white", linewidth=0.3)
    ax.set_title(title, loc="left", fontsize=11, pad=8)
    ax.legend(handles=[Patch(facecolor=LISA[k], edgecolor="none", label=LISA_NAMES[k]) for k in LISA],
              loc="lower right", frameon=False, fontsize=8)
