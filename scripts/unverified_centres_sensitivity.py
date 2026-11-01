"""
Sensitivity of subzone supply to the unverified dropped records (status 'unverified' in
output/excluded_centres_verification_2026.csv). 19 of the 23 have a location; the other 4
cannot be placed and are left out of every scenario.

Scenarios (centres added to the shared layer):
  base          the layer as built (1,796 centres)
  plausible     + unverified records not judged likely duplicates (likely != 'duplicate')
  upper_bound   + all 19 located unverified records

Children per subzone come from output/subzone_stats.csv (read only). H-c labels come from
output/subzone_lisa_hc.csv (read only). Nothing in the analysis is rerun.

Output: output/childcare_centres_2026_sensitivity.gpkg, layers "plausible", "upper_bound"
        (the layer plus the added rows, record_source 'unverified_sensitivity')
        output/unverified_centres_sensitivity_by_subzone.csv
Run:    python scripts/unverified_centres_sensitivity.py
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LAYER = ROOT / "output" / "childcare_centres_2026.gpkg"
VERIFICATION = ROOT / "output" / "excluded_centres_verification_2026.csv"
SUBZONES = ROOT / "data" / "MasterPlanSubZones_2019.geojson"
STATS = ROOT / "output" / "subzone_stats.csv"
LISA = ROOT / "output" / "subzone_lisa_hc.csv"
OUT_GPKG = ROOT / "output" / "childcare_centres_2026_sensitivity.gpkg"
OUT_CSV = ROOT / "output" / "unverified_centres_sensitivity_by_subzone.csv"


def main():
    base = gpd.read_file(LAYER, layer="centres")
    v = pd.read_csv(VERIFICATION, dtype=str)
    u = v[(v["status"] == "unverified") & v["lat"].notna()].copy()
    print(f"unverified: {(v['status'] == 'unverified').sum()}, located: {len(u)}")

    sz = gpd.read_file(SUBZONES).to_crs(3414)[["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "REGION_N", "geometry"]]
    pts = gpd.GeoDataFrame(u, geometry=gpd.points_from_xy(u["lon"].astype(float), u["lat"].astype(float)),
                           crs=4326).to_crs(3414)
    pts = gpd.sjoin(pts.drop(columns=["SUBZONE_N", "PLN_AREA_N"]), sz, predicate="within").drop(columns="index_right")
    pts["lon"], pts["lat"] = pts["lon"].astype(float), pts["lat"].astype(float)
    pts["record_source"] = "unverified_sensitivity"
    pts["location_source"] = "onemap_qa"
    keep = [c for c in base.columns if c in pts.columns]

    scenarios = {"plausible": pts[pts["likely"].fillna("") != "duplicate"], "upper_bound": pts}
    counts = {"base": base.groupby("SUBZONE_C").size()}
    for name, add in scenarios.items():
        layer = pd.concat([base, add[keep]], ignore_index=True)
        gpd.GeoDataFrame(layer, crs=base.crs).to_file(OUT_GPKG, layer=name, driver="GPKG")
        counts[name] = layer.groupby("SUBZONE_C").size()
        print(f"{name}: +{len(add)} -> {len(layer)} centres")

    stats = pd.read_csv(STATS)[["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "children_0_9"]]
    lisa = pd.read_csv(LISA)[["SUBZONE_C", "bv_sup_q", "bv_sup_p", "bv_walk_q", "bv_walk_p"]]
    t = stats.merge(pd.DataFrame(counts).fillna(0).astype(int), left_on="SUBZONE_C",
                    right_index=True, how="left").fillna({k: 0 for k in counts})
    for k in counts:
        t[f"per_1000_{k}"] = 1000 * t[k] / t["children_0_9"].where(t["children_0_9"] > 0)
    t["added_upper_bound"] = t["upper_bound"] - t["base"]
    t["pct_change_upper_bound"] = 100 * t["added_upper_bound"] / t["base"].where(t["base"] > 0)
    t = t.merge(lisa, on="SUBZONE_C", how="left")
    t = t.sort_values(["added_upper_bound", "pct_change_upper_bound"], ascending=False)
    t.to_csv(OUT_CSV, index=False)

    hit = t[t["added_upper_bound"] > 0]
    print(f"\nsubzones gaining a centre: {len(hit)}")
    print(hit[["SUBZONE_N", "PLN_AREA_N", "children_0_9", "base", "plausible", "upper_bound",
               "per_1000_base", "per_1000_upper_bound", "pct_change_upper_bound",
               "bv_sup_q", "bv_walk_q"]].round(2).to_string(index=False))
    sig = t[(t["bv_sup_q"] == "HL") | (t["bv_walk_q"] == "HH")]
    print("\nH-c subzones (supply HL or walk HH):")
    print(sig[["SUBZONE_N", "base", "upper_bound", "bv_sup_q", "bv_sup_p", "bv_walk_q"]].to_string(index=False))
    print(f"wrote {OUT_GPKG.relative_to(ROOT)} and {OUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
