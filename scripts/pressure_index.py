"""
BT4015 - supply-pressure index (reframed H-c): where do many young children share few reachable centres?

Method: two-step floating catchment (2SFCA) on the OSRM walking matrix, binary 10-minute catchment.
  step 1  for each centre j:  pool_j = sum of children 0-6 in HDB blocks within D0 minutes;  R_j = 1 / pool_j
          (every centre counts as one unit: capacity is not used, per the proposal; a centre with no
          HDB block within D0 serves private housing only and contributes nothing here)
  step 2  for each block i:   A_i = sum of R_j over centres within D0  (centres per child reachable)
          supply_per_1000 = 1000 * A_i;  pressure = 1 / A_i = children per reachable centre
          (A_i = 0 -> no centre within D0: pressure undefined, flagged in no_centre_<variant>)
  subzone: children-weighted mean of A_i, pressure = 1 / that mean; children with no centre in reach;
           centres in polygon; median listed Nursery fee; planned centres in polygon.
  LISA:    global + local Moran's I (esda, Lecture 8) on log pressure, HDB subzones with >= MIN_CHILDREN
           children 0-6, Queen contiguity with islands patched (scripts/spatial_weights.py),
           PERMS permutations.  HH = high pressure surrounded by high pressure = weak-link cluster.
Variants:  base    D0 = 10 min, all 1,796 centres
           s15     D0 = 15 min, all centres                       (catchment sensitivity)
           fullday D0 = 10 min, service_model != KN               (183 kindergartens excluded)
           future  D0 = 10 min, all centres + ECDA's 13 planned   (needs walk_planned_*.parquet)

Inputs   large_data/walk_centres_time_min.parquet   blocks x centres (minutes), scripts/build_walk_matrix.py
         large_data/walk_planned_time_min.parquet   blocks x planned centres
         output/hdb_access_children.csv             child_0_6 per block (scripts/build_subzone_stats.py)
         output/childcare_centres_2026.gpkg         layers centres (service_model, fee, SUBZONE_C) and planned
         output/hdb_blocks.gpkg                     layers subzones, subzone_stats
Outputs  output/hdb_pressure_index.csv              per block, all variants
         output/subzone_pressure.csv + gpkg layer "subzone_pressure"
         output/weak_links_top15.csv                ranked weak links with LISA label and planned-centre effect
Limitation: the demand pool is HDB children only, so centres beside private estates look under-pressured.

Run:  python scripts/pressure_index.py
"""
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_walk_matrix import load_dest  # noqa: E402
from spatial_weights import queen_with_islands_patched  # noqa: E402
from esda.moran import Moran, Moran_Local  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
LARGE, OUT = ROOT / "large_data", ROOT / "output"
GPKG = OUT / "hdb_blocks.gpkg"
D0, D0_SENS = 10, 15
MIN_CHILDREN, PERMS, SEED = 100, 9999, 4015
LAB = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
VARIANTS = ("base", "s15", "fullday", "future")


def two_sfca(T, demand, d0):
    """T: blocks x centres walking minutes (NaN = unreachable); demand: children per block (same index).
    Returns A (centres per child, per block), R (per centre), pool (children within d0, per centre)."""
    M = T.to_numpy(float) <= d0                       # NaN compares False
    P = demand.reindex(T.index).fillna(0).to_numpy(float)
    pool = M.T @ P
    R = np.divide(1.0, pool, out=np.zeros_like(pool), where=pool > 0)
    A = M @ R
    return (pd.Series(A, index=T.index), pd.Series(R, index=T.columns), pd.Series(pool, index=T.columns))


def wmean(v, w):
    v, w = np.asarray(v, float), np.asarray(w, float)
    ok = ~np.isnan(v) & (w > 0)
    return np.average(v[ok], weights=w[ok]) if ok.any() else np.nan


def main():
    np.random.seed(SEED)
    T = pd.read_parquet(LARGE / "walk_centres_time_min.parquet")
    centres, ids = load_dest("centres")
    assert set(T.columns) == set(ids), "matrix columns do not match the canonical centre layer"
    T = T[ids]                                           # canonical column order
    kn = centres["service_model"].eq("KN").to_numpy()
    blk = pd.read_csv(OUT / "hdb_access_children.csv").set_index("OBJECTID")
    demand = blk["child_0_6"]
    print(f"{T.shape[0]:,} blocks x {T.shape[1]:,} centres; children 0-6 = {demand.sum():,.0f}")

    TP = None
    if (LARGE / "walk_planned_time_min.parquet").exists():
        TP = pd.read_parquet(LARGE / "walk_planned_time_min.parquet").reindex(T.index)
        print(f"planned centres routed: {TP.shape[1]}")

    specs = {"base": (T, D0), "s15": (T, D0_SENS), "fullday": (T.loc[:, ~kn], D0)}
    if TP is not None:
        specs["future"] = (pd.concat([T, TP], axis=1), D0)

    res, pools = {}, {}
    for v, (Tv, d0) in specs.items():
        A, R, pool = two_sfca(Tv, demand, d0)
        res[v], pools[v] = A, pool
        n_served = int((pool > 0).sum())
        identity = float((demand.reindex(A.index).fillna(0) * A).sum())
        print(f"{v:8s} d0={d0:2d} min, {Tv.shape[1]:,} centres: {n_served:,} with HDB demand in reach "
              f"(sum P*A = {identity:,.1f}, should equal {n_served:,}); blocks with no centre: {int((A == 0).sum()):,}; "
              f"median supply per 1,000 children = {1000 * A.median():.2f}")
        blk[f"supply_per_1000_{v}"] = 1000 * A.reindex(blk.index)
        blk[f"pressure_{v}"] = np.where(A.reindex(blk.index) > 0, 1 / A.reindex(blk.index), np.nan)
        blk[f"no_centre_{v}"] = A.reindex(blk.index).eq(0)
    keep = ["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "child_0_6", "centres_nearest_min"] + \
           [c for c in blk.columns if c.startswith(("supply_per_1000_", "pressure_", "no_centre_"))]
    blk[keep].to_csv(OUT / "hdb_pressure_index.csv")
    print(f"block table -> output/hdb_pressure_index.csv ({len(blk):,} rows)")

    # ---- per-centre catchment pools (base): how much HDB demand each centre faces
    cpool = pd.DataFrame({"centre_id": ids, "service_model": centres["service_model"].to_numpy(),
                          "SUBZONE_C": centres["SUBZONE_C"].to_numpy(), "pool_children_0_6_10min": pools["base"].to_numpy()})
    cpool.to_csv(OUT / "centre_catchment_pools.csv", index=False)
    print(f"centre pools (base): median {cpool.pool_children_0_6_10min.median():,.0f} children within 10 min, "
          f"p90 {cpool.pool_children_0_6_10min.quantile(.9):,.0f}, {int((cpool.pool_children_0_6_10min == 0).sum())} centres with none")

    # ---- subzone aggregation
    rows = []
    for code, g in blk.groupby("SUBZONE_C"):
        w = g["child_0_6"].to_numpy(float)
        r = {"SUBZONE_C": code, "children_0_6": w.sum()}
        for v in res:
            a = (g[f"supply_per_1000_{v}"] / 1000).to_numpy(float)
            m = wmean(a, w)
            r[f"supply_per_1000_{v}"] = 1000 * m
            r[f"pressure_{v}"] = 1 / m if m and m > 0 else np.nan
            r[f"children_no_centre_{v}"] = w[g[f"no_centre_{v}"].to_numpy(bool)].sum()
        rows.append(r)
    sp = pd.DataFrame(rows)

    sz = pyogrio.read_dataframe(GPKG, layer="subzone_stats")
    base_cols = ["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "REGION_N", "area_km2", "has_hdb", "centres_n",
                 "centres_fullday", "walk_nearest_min_cw", "share_children_within_10min", "pa_median_income_sgd", "geometry"]
    sp = sz[base_cols].merge(sp, on="SUBZONE_C", how="left")
    fee = centres[centres["fee_status"].eq("listed")].groupby("SUBZONE_C")["FULL_DAY_SC_NURSERY_FEE"].median()
    sp["median_fee_listed"] = sp["SUBZONE_C"].map(fee)
    planned = pyogrio.read_dataframe(OUT / "childcare_centres_2026.gpkg", layer="planned", read_geometry=False)
    sp["planned_centres_n"] = sp["SUBZONE_C"].map(planned.groupby("SUBZONE_C").size()).fillna(0).astype(int)
    if "pressure_future" in sp:
        sp["pct_change_future"] = 100 * (sp["pressure_future"] / sp["pressure_base"] - 1)

    # ---- LISA on log pressure (base), HDB subzones with enough children
    h = sp[sp["has_hdb"] & (sp["children_0_6"] >= MIN_CHILDREN) & sp["pressure_base"].notna()].reset_index(drop=True)
    w = queen_with_islands_patched(h)
    y = np.log(h["pressure_base"].to_numpy(float))
    mi = Moran(y, w, permutations=PERMS)
    loc = Moran_Local(y, w, permutations=PERMS, seed=SEED)
    sig = loc.p_sim < 0.05
    h["lisa_q"] = [LAB[q] if s_ else "ns" for q, s_ in zip(loc.q, sig)]
    h["lisa_p"] = loc.p_sim
    sp = sp.merge(h[["SUBZONE_C", "lisa_q", "lisa_p"]], on="SUBZONE_C", how="left")
    counts = h["lisa_q"].value_counts().to_dict()
    print(f"\nLISA on log pressure (base), {len(h)} HDB subzones with >= {MIN_CHILDREN} children 0-6: "
          f"global Moran's I = {mi.I:+.3f} (p = {mi.p_sim:.4f}); significant local: {counts}")

    sp = gpd.GeoDataFrame(sp, geometry="geometry", crs=sz.crs)
    sp.drop(columns="geometry").to_csv(OUT / "subzone_pressure.csv", index=False)
    sp.to_file(GPKG, layer="subzone_pressure", driver="GPKG")
    print(f"subzone table -> output/subzone_pressure.csv + gpkg layer subzone_pressure ({len(sp)} rows)")

    # ---- weak links
    cols = ["SUBZONE_N", "PLN_AREA_N", "children_0_6", "centres_n", "walk_nearest_min_cw", "pressure_base",
            "supply_per_1000_base", "children_no_centre_base", "median_fee_listed", "lisa_q", "lisa_p",
            "planned_centres_n"] + (["pressure_future", "pct_change_future"] if "pressure_future" in sp else [])
    top = h.sort_values("pressure_base", ascending=False).head(15)
    top[["SUBZONE_C"] + cols].to_csv(OUT / "weak_links_top15.csv", index=False)
    print("\nTop 15 weak links (children 0-6 per reachable centre, 10-min walk):")
    print(top[cols].round(1).to_string(index=False))
    hh = h[h["lisa_q"] == "HH"].sort_values("pressure_base", ascending=False)
    print(f"\nHH cluster ({len(hh)} subzones): " + ", ".join(hh["SUBZONE_N"]))
    print("\nCompare: Spearman rank, pressure_base vs pressure_s15 = {:.3f}; vs pressure_fullday = {:.3f}".format(
        h["pressure_base"].corr(h["pressure_s15"], method="spearman"), h["pressure_base"].corr(h["pressure_fullday"], method="spearman")))


if __name__ == "__main__":
    main()
