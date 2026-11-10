"""
Ripley's K for HDB blocks and childcare centres vs CSR (Karis, notebook cell 23), as a script.
Rerun 2026-11-10 on the canonical centre layer output/childcare_centres_2026.gpkg (1,796 centres).
Outputs: output/k_function/*.  Run: python scripts/k_function.py
"""
import matplotlib
matplotlib.use("Agg")
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from scipy.spatial import cKDTree
import matplotlib.pyplot as plt

K_RADII = np.arange(100, 1501, 100, dtype=float)
K_NSIM = 199
K_SEED = 4015
ROOT = Path(__file__).resolve().parent.parent
k_output = ROOT / "output/k_function"
k_output.mkdir(parents=True, exist_ok=True)

k_subzones = gpd.read_file(ROOT / "data/MasterPlanSubZones_2019.geojson").to_crs(3414)
k_window = shapely.union_all(shapely.make_valid(k_subzones.geometry.to_numpy()))
if k_window.is_empty or k_window.area <= 0:
    raise ValueError("Study window must have positive area.")
# Precompute eroded windows for fast, exact border eligibility checks.
k_inner_windows = [k_window.buffer(-float(r)) for r in K_RADII]
for inner in k_inner_windows:
    if inner.is_empty:
        raise ValueError("A radius exceeds the available interior of the study window.")
    shapely.prepare(inner)
shapely.prepare(k_window)
k_area = k_window.area
k_bounds = k_window.bounds


def k_load_points(path, layer=None):
    frame = gpd.read_file(path, **({"layer": layer} if layer else {})).to_crs(3414)
    valid = frame.geometry.notna() & ~frame.geometry.is_empty & frame.geom_type.eq("Point")
    candidates = frame.loc[valid]
    inside = shapely.covers(k_window, candidates.geometry.to_numpy())
    kept = candidates.loc[inside]
    xy = np.column_stack([kept.geometry.x, kept.geometry.y])
    if len(xy) < 2:
        raise ValueError("At least two in-window points are required.")
    audit = {"input_n": len(frame), "invalid_or_nonpoint_n": int((~valid).sum()),
             "outside_window_n": int((~inside).sum()), "analysed_n": len(xy),
             "coincident_extra_records": len(xy) - len(np.unique(xy, axis=0))}
    return xy, audit


def k_border(xy):
    tree = cKDTree(xy)
    values, eligible_counts = [], []
    for radius, inner in zip(K_RADII, k_inner_windows):
        eligible = shapely.contains_xy(inner, xy[:, 0], xy[:, 1])
        count = int(eligible.sum())
        if count == 0:
            raise ValueError(f"No eligible focal points at radius {radius} m.")
        # Subtract each focal point itself, retaining other coincident records.
        neighbours = tree.query_ball_point(xy[eligible], radius, return_length=True) - 1
        values.append(k_area * neighbours.sum() / ((len(xy) - 1) * count))
        eligible_counts.append(count)
    return np.asarray(values), np.asarray(eligible_counts)


def k_uniform_points(n, rng):
    xmin, ymin, xmax, ymax = k_bounds
    acceptance = k_area / ((xmax - xmin) * (ymax - ymin))
    chunks, remaining = [], n
    while remaining:
        size = max(256, int(np.ceil(remaining / acceptance * 1.1)))
        batch = rng.uniform([xmin, ymin], [xmax, ymax], size=(size, 2))
        accepted = batch[shapely.contains_xy(k_window, batch[:, 0], batch[:, 1])][:remaining]
        chunks.append(accepted)
        remaining -= len(accepted)
    return np.vstack(chunks)


k_patterns = {
    "HDBs": k_load_points(ROOT / "output/hdb_blocks.gpkg", layer="hdb_points"),
    "Childcare centres": k_load_points(ROOT / "output/childcare_centres_2026.gpkg", layer="centres"),
}
k_results, k_rows = {}, []
for (name, (xy, audit)), seed in zip(k_patterns.items(), np.random.SeedSequence(K_SEED).spawn(2)):
    rng = np.random.default_rng(seed)
    observed_k, eligible = k_border(xy)
    observed_l = np.sqrt(observed_k / np.pi) - K_RADII
    simulated_l = []
    for _ in range(K_NSIM):
        simulated_k, _ = k_border(k_uniform_points(len(xy), rng))
        simulated_l.append(np.sqrt(simulated_k / np.pi) - K_RADII)
    simulated_l = np.asarray(simulated_l)
    simulated_max = simulated_l.max(axis=1)
    observed_max = observed_l.max()
    p_value = (1 + np.count_nonzero(simulated_max >= observed_max)) / (K_NSIM + 1)
    # With 199 simulations, the fifth-largest maximum gives a 2.5% upper-tail test.
    tail_count = int(np.floor(0.025 * (K_NSIM + 1)))
    global_upper = np.sort(simulated_max)[-tail_count]
    lower, upper = np.quantile(simulated_l, [0.025, 0.975], axis=0)
    table = pd.DataFrame({"radius_m": K_RADII, "K_m2": observed_k,
                          "L_minus_r_m": observed_l, "eligible_focal_n": eligible,
                          "CSR_pointwise_lower_m": lower, "CSR_pointwise_upper_m": upper,
                          "global_upper_2pattern_m": global_upper})
    slug = name.lower().replace(" ", "_")
    table.to_csv(k_output / f"{slug}_k_curve.csv", index=False)
    np.savez_compressed(k_output / f"{slug}_csr_simulations.npz",
                        radii_m=K_RADII, simulated_L_minus_r_m=simulated_l)
    k_results[name] = table
    k_rows.append({"pattern": name, **audit, "window_km2": k_area / 1e6,
                   "simulations": K_NSIM, "max_L_minus_r_m": observed_max,
                   "global_p": p_value, "bonferroni_p": min(1.0, 2 * p_value),
                   "significant_clustering_5pct": min(1.0, 2 * p_value) <= 0.05})

k_summary = pd.DataFrame(k_rows).set_index("pattern")
k_summary.to_csv(k_output / "k_summary.csv")
print(k_summary.to_string())
fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharex=True)
for ax, (name, table) in zip(axes, k_results.items()):
    radius = table.radius_m.to_numpy()
    slug = name.lower().replace(" ", "_")
    # Convert each saved simulation back to K before computing its pointwise band.
    with np.load(k_output / f"{slug}_csr_simulations.npz") as saved:
        if not np.array_equal(saved["radii_m"], radius):
            raise ValueError("Saved simulations and K curve use different radii.")
        simulated_k = np.pi * (saved["simulated_L_minus_r_m"] + radius) ** 2
    lower_k, upper_k = np.quantile(simulated_k, [0.025, 0.975], axis=0)
    ax.fill_between(radius, lower_k, upper_k,
                    color="lightgrey", label="CSR 95% pointwise band")
    ax.plot(radius, np.pi * radius ** 2, color="crimson", linestyle="--",
            linewidth=1.5, label="Randomness reference: K(r) = πr²")
    # Same global test of max(L-r), expressed as its equivalent K-scale boundary.
    global_upper_k = np.pi * (radius + table.global_upper_2pattern_m.to_numpy()) ** 2
    ax.plot(radius, global_upper_k, color="darkorange", linestyle=":",
            label="Global upper boundary (L−r test)")
    ax.plot(radius, table.K_m2, color="steelblue", linewidth=2, label="Observed K(r)")
    ax.set_title(f"{name} (n={k_summary.loc[name, 'analysed_n']:,})\n"
                 f"Global p={k_summary.loc[name, 'global_p']:.3f}; "
                 f"adjusted p={k_summary.loc[name, 'bonferroni_p']:.3f}")
    ax.set_xlabel("Distance r (metres)")
    ax.set_ylabel("Border-corrected K(r) (m²)")
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)
fig.suptitle("Ripley’s K-function: HDBs and childcare centres")
fig.tight_layout()
fig.savefig(k_output / "k_function_comparison.png", dpi=180, bbox_inches="tight")
print("Observed K(r) above πr² indicates excess neighbours relative to homogeneous CSR.")
print("Global p-values retain the max(L(r)−r) test; only the display scale changed.")
print("No OSRM requests were made by this section.")
