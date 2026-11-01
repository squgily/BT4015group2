"""
BT4015 - integrate accessibility, demand and supply into block- and subzone-level tables.

Inputs
  output/hdb_walk_access.csv                 per-block walk measures (scripts/summarise_walk_matrix.py)
  output/hdb_blocks.gpkg                     layers hdb_blocks (join_key), subzones (geometry, area_km2)
  output/hdb_blocks_children_final.gpkg      children 0-4 / 5-9 per block (Jessie)
  output/childcare_centres_2026.gpkg         canonical centre layer, layer "centres" (Jessie; 1,796, all
                                             service models; subzone already attached)
  data/SubzoneSingleYearAge_2026.csv         SingStat single-year-of-age resident population by subzone,
                                             used for the per-subzone share of 5-9 that is aged 5-6
  output/resident-household-income_regression/planning_area_median_household_income_range.csv
                                             planning-area median household income band (Daryl)

Outputs
  output/hdb_access_children.csv             one row per residential block: access + children + flat mix.
      Demand band (prof-approved 2026-10-30): children 0-6 = child_0_4 + share_5_6 * child_5_9, where
      share_5_6 is the subzone's share of ages 5-6 within 5-9 (fallback 0.40). child_0_6_flat40 uses
      the flat 40% rule as a robustness column.
  output/subzone_stats.csv  and  layer "subzone_stats" in output/hdb_blocks.gpkg
      per subzone (all 332; has_hdb flags the 159 with residential HDB):
      children_0_4 / 5_9 / 0_9, children_0_6 (+ _flat40, share_5_6), dwelling_units, pct_1to3room,
      centres_n / _cc / _kn / _fullday (points in polygon), centres_per_1000_children (0-9, legacy),
      centres_per_1000_children_0_6, centre_density_km2, child_density_km2, child_density_0_6_km2,
      walk_nearest_min_cw (weighted by children 0-6), share_children_within_10min,
      share_children_within_15min, centres_within_10min_cw, mrt_nearest_min_cw,
      share_children_mrt_within_15min, pa_median_income_sgd (planning-area band midpoint).

Run:  python scripts/build_subzone_stats.py
"""
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
GPKG = OUT / "hdb_blocks.gpkg"
ACCESS = OUT / "hdb_walk_access.csv"
CHILDREN = OUT / "hdb_blocks_children_final.gpkg"
CENTRES = OUT / "childcare_centres_2026.gpkg"  # layer "centres"
SINGLE_YEAR = ROOT / "data" / "SubzoneSingleYearAge_2026.csv"
FLAT_SHARE = 0.40        # prof-approved rule of thumb; national single-year share is 0.388
MIN_POP_5_9 = 100        # SingStat rounds cells to 10: below this the subzone share is noise -> fallback
INCOME = OUT / "resident-household-income_regression" / "planning_area_median_household_income_range.csv"


def income_midpoint(band):
    nums = [int(x.replace(",", "")) for x in re.findall(r"\$([\d,]+)", str(band))]
    if not nums:
        return np.nan
    return nums[0] + 1250 if "over" in str(band).lower() else (nums[0] + nums[-1] + 1) / 2


def share_5_6_by_subzone():
    """Share of residents aged 5-6 among ages 5-9, per subzone (SUBZONE_N), from the SingStat
    single-year table. Subzones with fewer than MIN_POP_5_9 residents aged 5-9 get NaN (caller falls
    back to FLAT_SHARE), because SingStat rounds to 10 and small cells give shares of 0 or 1."""
    a = pd.read_csv(SINGLE_YEAR)
    a["Pop"] = pd.to_numeric(a["Pop"], errors="coerce")
    a["Age"] = pd.to_numeric(a["Age"], errors="coerce")
    a = a[a["Age"].between(5, 9)]
    g = a.groupby(a["SZ"].str.upper().str.strip())["Pop"]
    pop59 = g.sum()
    pop56 = a[a["Age"] <= 6].groupby(a["SZ"].str.upper().str.strip())["Pop"].sum().reindex(pop59.index).fillna(0)
    return (pop56 / pop59.where(pop59 >= MIN_POP_5_9)).rename("share_5_6")


def wmean(values, weights):
    v, w = np.asarray(values, float), np.asarray(weights, float)
    ok = ~np.isnan(v) & ~np.isnan(w) & (w > 0)
    return np.average(v[ok], weights=w[ok]) if ok.any() and w[ok].sum() > 0 else np.nan


def main():
    acc = pd.read_csv(ACCESS)
    blocks = pyogrio.read_dataframe(GPKG, layer="hdb_blocks", read_geometry=False,
                                    columns=["OBJECTID", "join_key"])
    kids = pyogrio.read_dataframe(CHILDREN, read_geometry=False)
    kids = kids.rename(columns={"1- and 2-Room Flats*": "units_1_2room", "3-Room Flats": "units_3room",
                                "4-Room Flats": "units_4room", "5-Room and Executive Flats": "units_5room_exec"})
    kcols = ["join_key", "child_0_4", "child_5_9", "child_pop_0_9",
             "units_1_2room", "units_3room", "units_4room", "units_5room_exec", "review_flag"]
    blk = acc.merge(blocks, on="OBJECTID", how="left").merge(kids[kcols], on="join_key", how="left")
    assert blk["child_pop_0_9"].notna().all(), "blocks without child counts"
    share = share_5_6_by_subzone()
    blk["share_5_6"] = blk["SUBZONE_N"].str.upper().map(share)
    n_fallback = blk["share_5_6"].isna().sum()
    blk["share_5_6"] = blk["share_5_6"].fillna(FLAT_SHARE)
    blk["child_0_6"] = blk["child_0_4"] + blk["share_5_6"] * blk["child_5_9"]
    blk["child_0_6_flat40"] = blk["child_0_4"] + FLAT_SHARE * blk["child_5_9"]
    print(f"share_5_6: {blk['share_5_6'].min():.3f}-{blk['share_5_6'].max():.3f} across blocks; "
          f"{n_fallback} blocks fell back to {FLAT_SHARE}; "
          f"children 0-6 = {blk['child_0_6'].sum():,.0f} ({blk['child_0_6'].sum() / blk['child_pop_0_9'].sum():.1%} of 0-9)")
    blk["has_centre_10min"] = blk["centres_n_within_10min"] >= 1
    blk["has_centre_15min"] = blk["centres_n_within_15min"] >= 1
    blk["mrt_within_15min"] = blk["mrt_exits_nearest_min"] <= 15
    blk.to_csv(OUT / "hdb_access_children.csv", index=False)
    print(f"block table: {len(blk):,} rows -> output/hdb_access_children.csv")

    sz = pyogrio.read_dataframe(GPKG, layer="subzones")
    centres = pyogrio.read_dataframe(CENTRES, layer="centres").to_crs(sz.crs)
    cj = gpd.sjoin(centres[["centre_name", "service_model", "geometry"]], sz[["SUBZONE_C", "geometry"]],
                   how="inner", predicate="within")
    csum = cj.groupby("SUBZONE_C").agg(centres_n=("centre_name", "size"),
                                       centres_cc=("service_model", lambda s: (s == "CC").sum()),
                                       centres_kn=("service_model", lambda s: (s == "KN").sum()),
                                       centres_fullday=("service_model", lambda s: (s != "KN").sum()))
    print(f"centres inside a subzone: {len(cj):,} of {len(centres):,}")

    rows = []
    for code, g in blk.groupby("SUBZONE_C"):
        w = g["child_0_6"].to_numpy(float)      # demand weight: children 0-6
        w09 = g["child_pop_0_9"].to_numpy(float)
        units = g["total_dwelling_units"].sum()
        small = g["units_1_2room"].sum() + g["units_3room"].sum()
        rows.append({
            "SUBZONE_C": code, "n_blocks": len(g), "dwelling_units": int(units),
            "pct_1to3room": 100 * small / units if units else np.nan,
            "children_0_4": g["child_0_4"].sum(), "children_5_9": g["child_5_9"].sum(),
            "children_0_9": w09.sum(),
            "children_0_6": w.sum(), "children_0_6_flat40": g["child_0_6_flat40"].sum(),
            "share_5_6": g["share_5_6"].iloc[0],
            "walk_nearest_min_cw": wmean(g["centres_nearest_min"], w),
            "walk_nearest_min_mean": g["centres_nearest_min"].mean(),
            "centres_within_10min_cw": wmean(g["centres_n_within_10min"], w),
            "share_children_within_10min": w[g["has_centre_10min"].to_numpy()].sum() / w.sum() if w.sum() else np.nan,
            "share_children_within_15min": w[g["has_centre_15min"].to_numpy()].sum() / w.sum() if w.sum() else np.nan,
            "mrt_nearest_min_cw": wmean(g["mrt_exits_nearest_min"], w),
            "share_children_mrt_within_15min": w[g["mrt_within_15min"].to_numpy()].sum() / w.sum() if w.sum() else np.nan,
        })
    hdb = pd.DataFrame(rows)

    stats = sz[["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "REGION_N", "area_km2", "geometry"]].merge(
        hdb, on="SUBZONE_C", how="left").merge(csum, on="SUBZONE_C", how="left")
    stats["has_hdb"] = stats["n_blocks"].notna()
    for c in ["centres_n", "centres_cc", "centres_kn", "centres_fullday"]:
        stats[c] = stats[c].fillna(0).astype(int)
    stats["centres_per_1000_children"] = np.where(stats["children_0_9"] > 0,
                                                  1000 * stats["centres_n"] / stats["children_0_9"], np.nan)
    stats["centres_per_1000_children_0_6"] = np.where(stats["children_0_6"] > 0,
                                                      1000 * stats["centres_n"] / stats["children_0_6"], np.nan)
    stats["centre_density_km2"] = stats["centres_n"] / stats["area_km2"]
    stats["child_density_km2"] = stats["children_0_9"] / stats["area_km2"]
    stats["child_density_0_6_km2"] = stats["children_0_6"] / stats["area_km2"]

    inc = pd.read_csv(INCOME)
    inc["PLN_AREA_N"] = inc["planning_area"].str.upper().str.strip()
    inc["pa_median_income_sgd"] = inc["median_income_range"].map(income_midpoint)
    stats = stats.merge(inc[["PLN_AREA_N", "pa_median_income_sgd"]], on="PLN_AREA_N", how="left")
    miss_inc = stats.loc[stats["has_hdb"] & stats["pa_median_income_sgd"].isna(), "PLN_AREA_N"].unique()
    if len(miss_inc):
        print(f"no planning-area income for: {sorted(miss_inc)}")

    stats = gpd.GeoDataFrame(stats, geometry="geometry", crs=sz.crs)
    stats.drop(columns="geometry").to_csv(OUT / "subzone_stats.csv", index=False)
    stats.to_file(GPKG, layer="subzone_stats", driver="GPKG")
    h = stats[stats["has_hdb"]]
    print(f"subzone table: {len(stats)} subzones ({h.shape[0]} with HDB) -> output/subzone_stats.csv + gpkg layer")
    print("HDB subzones, child-weighted nearest walk (min): median {:.1f}, p90 {:.1f}, max {:.1f}".format(
        h["walk_nearest_min_cw"].median(), h["walk_nearest_min_cw"].quantile(.9), h["walk_nearest_min_cw"].max()))
    print("share of children within 10 min of a centre: median {:.0%}, min {:.0%}".format(
        h["share_children_within_10min"].median(), h["share_children_within_10min"].min()))
    print("centres per 1,000 children 0-6: median {:.1f}, min {:.1f}, max {:.1f}".format(
        h["centres_per_1000_children_0_6"].median(), h["centres_per_1000_children_0_6"].min(), h["centres_per_1000_children_0_6"].max()))
    worst = h.sort_values("share_children_within_10min").head(8)
    print("\nlowest share of children 0-6 within 10-min walk (HDB subzones):")
    print(worst[["SUBZONE_N", "PLN_AREA_N", "children_0_6", "centres_n", "walk_nearest_min_cw",
                 "share_children_within_10min"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
