"""
Figures the presentation deck is missing (one per hypothesis slide that currently has only a claim).

  figures/ha_centres_vs_children.png   H-a  centres vs children 0-6 per subzone, log-log, slope 0.65
  figures/hb_access_by_ses.png         H-b  walk time / fee / pressure by income tercile and by flat-type tercile: flat
  figures/hc_bivariate_moran.png       H-c  Moran scatter, child density vs spatially lagged walk time: negative
  figures/lisa_robustness.png          H-c  which HH subzones survive each cut-off and Rook contiguity
  figures/planned_centre_relief.png    planned centres: % change in own-subzone pressure

Same palette and ink tokens as make_pressure_figures.py. Run after pressure_index.py.
"""
import shutil, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyogrio  # noqa: E402
import statsmodels.api as sm  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spatial_weights import queen_with_islands_patched  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT, FIG = ROOT / "output", ROOT / "figures"
MIRROR = Path("/Users/anhminhhoang/GIS/New-Project-BT4015/figures")
INK, INK2, INK3, SURF, GRID = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb", "#e6e5e1"
BLUE, BLUE_L, RED, ORANGE = "#2a78d6", "#9ec5f4", "#e34948", "#eb6834"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "savefig.facecolor": SURF})
MIN_CHILDREN = 100


def tidy(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(color=GRID, lw=0.5); ax.set_axisbelow(True)


def main():
    FIG.mkdir(exist_ok=True)
    sp = pyogrio.read_dataframe(OUT / "hdb_blocks.gpkg", layer="subzone_pressure")
    st = pd.read_csv(OUT / "subzone_stats.csv")[["SUBZONE_C", "pct_1to3room", "child_density_0_6_km2"]]
    h = sp[sp["has_hdb"] & (sp["children_0_6"] >= MIN_CHILDREN) & sp["pressure_base"].notna()].merge(st, on="SUBZONE_C").reset_index(drop=True)

    # ---- H-a: centres vs children, log-log
    x, y = np.log(h["children_0_6"]), np.log(h["centres_n"].clip(lower=1))
    m = sm.OLS(y, sm.add_constant(x)).fit()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(h["children_0_6"], h["centres_n"], s=28, color=BLUE, alpha=0.75, edgecolor="white", linewidth=0.8)
    xs = np.linspace(x.min(), x.max(), 50)
    ax.plot(np.exp(xs), np.exp(m.params.iloc[0] + m.params.iloc[1] * xs), color=INK, lw=2)
    ax.plot(np.exp(xs), np.exp(xs) * np.exp(y.mean() - x.mean()), color=INK3, lw=1, ls="--")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Children aged 0–6 in HDB blocks (log scale)")
    ax.set_ylabel("Childcare centres in subzone (log scale)")
    ax.set_title("H-a: supply follows demand, at two-thirds the rate", loc="left", fontsize=11, pad=8)
    ax.text(0.02, 0.97, f"log-log slope {m.params.iloc[1]:.2f} (SE {m.bse.iloc[1]:.2f}), R² {m.rsquared:.2f}, n = {len(h)}\n"
            "dashed = proportional (slope 1)", transform=ax.transAxes, va="top", fontsize=8, color=INK2)
    for name in ["TAMPINES NORTH", "PLANTATION", "GARDEN", "BRICKWORKS", "YISHUN EAST"]:
        r = h[h["SUBZONE_N"] == name]
        if len(r):
            r = r.iloc[0]
            ax.annotate(name.title(), (r["children_0_6"], r["centres_n"]), fontsize=7, color=INK, xytext=(4, 3), textcoords="offset points")
    tidy(ax)
    fig.text(0.01, 0.01, "HDB subzones with ≥100 children 0–6. Centres = all ECDA service models, Oct 2026.", fontsize=7, color=INK3)
    fig.tight_layout(); fig.savefig(FIG / "ha_centres_vs_children.png", dpi=170); plt.close(fig)

    # ---- H-b: access by SES tercile
    i = h[h["pa_median_income_sgd"].notna()].copy()
    i["Income tercile (planning area)"] = pd.qcut(i["pa_median_income_sgd"], 3, labels=["low", "mid", "high"])
    i["Share of 1–3-room flats (tercile)"] = pd.qcut(i["pct_1to3room"], 3, labels=["low", "mid", "high"])
    metrics = [("walk_nearest_min_cw", "Median walk to nearest centre (min)"),
               ("median_fee_listed", "Median listed full-day fee (S$)"),
               ("pressure_base", "Median children per reachable centre")]
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.2))
    for r_, grp in enumerate(["Income tercile (planning area)", "Share of 1–3-room flats (tercile)"]):
        for c_, (col, lab) in enumerate(metrics):
            ax = axes[r_, c_]
            med = i.groupby(grp, observed=True)[col].median()
            ax.bar(med.index.astype(str), med.values, color=BLUE, width=0.55)
            for k, v in enumerate(med.values):
                ax.text(k, v, f"{v:,.1f}" if col != "median_fee_listed" else f"{v:,.0f}", ha="center", va="bottom", fontsize=8, color=INK)
            ax.set_ylim(0, med.max() * 1.25)
            ax.set_title(lab, loc="left", fontsize=9, color=INK)
            ax.set_xlabel(grp if r_ == 1 else "")
            if r_ == 0:
                ax.set_xlabel(grp)
            tidy(ax)
    fig.suptitle("H-b: neither distance nor price varies with neighbourhood SES inside HDB estates", x=0.01, ha="left", fontsize=11)
    fig.text(0.01, 0.01, f"n = {len(i)} HDB subzones with ≥100 children and planning-area income. Spearman income vs walk −0.16, vs fee −0.04, vs pressure +0.10.",
             fontsize=7, color=INK3)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96)); fig.savefig(FIG / "hb_access_by_ses.png", dpi=170); plt.close(fig)

    # ---- H-c: bivariate Moran scatter, child density vs lagged walk time
    w = queen_with_islands_patched(h)
    zx = (h["child_density_0_6_km2"] - h["child_density_0_6_km2"].mean()) / h["child_density_0_6_km2"].std()
    zy = (h["walk_nearest_min_cw"] - h["walk_nearest_min_cw"].mean()) / h["walk_nearest_min_cw"].std()
    lag = w.sparse @ zy.to_numpy()
    I_bv = float((zx * lag).sum() / (zx ** 2).sum())
    fig, ax = plt.subplots(figsize=(7.5, 6))
    ax.scatter(zx, lag, s=26, color=BLUE, alpha=0.75, edgecolor="white", linewidth=0.8)
    b = np.polyfit(zx, lag, 1)
    xs = np.linspace(zx.min(), zx.max(), 20)
    ax.plot(xs, np.polyval(b, xs), color=INK, lw=2)
    ax.axhline(0, color=GRID, lw=1); ax.axvline(0, color=GRID, lw=1)
    ax.set_xlabel("Child density 0–6 (standardised)")
    ax.set_ylabel("Neighbours' mean walk time to nearest centre (standardised)")
    ax.set_title("H-c as proposed: children do not cluster where walking is poor", loc="left", fontsize=11, pad=8)
    ax.text(0.98, 0.97, f"bivariate Moran's I = {I_bv:+.2f} (negative: dense-child subzones sit among well-served ones)\n"
            "→ distance cannot locate the weak links; reframed as supply pressure", transform=ax.transAxes, va="top", ha="right", fontsize=8, color=INK2)
    tidy(ax)
    fig.text(0.01, 0.01, "Queen contiguity, row-standardised, islands patched to nearest neighbour. Permutation p < 0.001 (scripts/lisa_hc.py).", fontsize=7, color=INK3)
    fig.tight_layout(); fig.savefig(FIG / "hc_bivariate_moran.png", dpi=170); plt.close(fig)

    # ---- LISA robustness matrix
    sens = pd.read_csv(OUT / "lisa_threshold_sensitivity.csv")
    cols = {f"min {int(r.min_children_0_6)} children\n(I {r.morans_I:+.2f}, {r.n_HH} HH)": set(s.strip() for s in r.HH_subzones.split(";"))
            for r in sens.itertuples()}
    rook = {"Brickworks", "Garden", "Hong Kah North", "Jelebu", "Park", "Plantation", "Punggol Town Centre", "Woodgrove"}
    cols["Rook contiguity\n(I +0.21, 8 HH)"] = rook
    names = sorted(set().union(*cols.values()), key=lambda n: (-sum(n in s for s in cols.values()), n))
    M = np.array([[n in s for s in cols.values()] for n in names])
    fig, ax = plt.subplots(figsize=(9, 6.5))
    for r_, n in enumerate(names):
        for c_ in range(M.shape[1]):
            ax.add_patch(plt.Rectangle((c_ + 0.06, r_ + 0.06), 0.88, 0.88, color=RED if M[r_, c_] else "#efeeea"))
    ax.set_xlim(0, M.shape[1]); ax.set_ylim(len(names), 0)
    ax.set_xticks(np.arange(M.shape[1]) + 0.5); ax.set_xticklabels(list(cols.keys()), fontsize=8)
    ax.set_yticks(np.arange(len(names)) + 0.5); ax.set_yticklabels(names, fontsize=8.5)
    ax.tick_params(length=0); ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("LISA high-high membership under each specification (reported run = min 100, Queen)", loc="left", fontsize=11, pad=8)
    core = [n for n in names if M[names.index(n)].sum() == M.shape[1]]
    fig.text(0.01, 0.01, "Red = high-high at p < 0.05. Always flagged: " + ", ".join(core) + ".", fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(FIG / "lisa_robustness.png", dpi=170); plt.close(fig)

    # ---- planned centre relief
    imp = pd.read_csv(OUT / "planned_centre_impact.csv").sort_values("own_subzone_pct_change")
    lab = [f"{r.SUBZONE_N.title()} ({r.expected_opening})" for r in imp.itertuples()]
    fig, ax = plt.subplots(figsize=(9, 5.8))
    ax.barh(lab, -imp["own_subzone_pct_change"], color=ORANGE, height=0.6)
    for k, (v, pool) in enumerate(zip(imp["own_subzone_pct_change"], imp["pool_children_0_6"])):
        ax.text(-v + 0.3, k, f"−{-v:.0f}%   ({pool:,.0f} children within 10 min)", va="center", fontsize=7.5, color=INK)
    ax.invert_yaxis(); ax.set_xlim(0, 30)
    ax.set_xlabel("Reduction in own-subzone pressure when the centre opens (%)")
    ax.set_title("ECDA's 13 planned centres: how much relief, and where", loc="left", fontsize=11, pad=8)
    tidy(ax)
    fig.text(0.01, 0.01, "One unit per centre. Tampines North's planned centre faces a pool at the 98th percentile of existing centres.\n"
             "No planned centre within 10 min of Park, Brickworks, Matilda, Waterway East, Hong Kah North or Woodgrove.", fontsize=7, color=INK3)
    fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(FIG / "planned_centre_relief.png", dpi=170); plt.close(fig)

    MIRROR.mkdir(exist_ok=True)
    files = ["ha_centres_vs_children.png", "hb_access_by_ses.png", "hc_bivariate_moran.png", "lisa_robustness.png", "planned_centre_relief.png"]
    for f in files:
        shutil.copy(FIG / f, MIRROR / f)
    print("written:", ", ".join(files), f"| bivariate I = {I_bv:+.3f}, H-a slope = {m.params.iloc[1]:.2f}")


if __name__ == "__main__":
    main()
