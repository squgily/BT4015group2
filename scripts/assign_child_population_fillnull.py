"""
BT4015 Group 2 - preprocessing step 2 (type-of-dwelling version)
Assign children aged 0-4 and 5-9 to each residential HDB block by dasymetric
disaggregation of subzone counts, split by flat type.

Why flat type: SingStat's "Resident Population by Planning Area/Subzone, Age Group and
Type of Dwelling" gives, per subzone, how many children live in 1-2 room, 3-room,
4-room and 5-room/executive HDB flats. HDB Property Information counts each block's
flats with the same split, so children in 4-room flats are spread over the subzone's
4-room flats, and so on. No floor-area estimate or resale download is needed
(compare assign_child_population.py, which uses the floor-area table instead).

    child_pop(block, age, type) = subzone_children(age, type)
                                  x block_units(type) / subzone_hdb_units(type)

Fallback: if a subzone has children in a flat type but none of its matched blocks has
that type, those children are spread by the block's total dwelling units instead
(used_fallback = True). Subzones with HDB children but no matched residential block
are listed as unassigned.

Inputs  (relative to repo root)
  output/hdb_blocks.gpkg                 join_hdb_nationwide.py output
  data/MasterPlanSubZones_2019.geojson   subzone polygons
  data/subzone_child_population_2026.xlsx  SingStat respopagesextod2026e.xlsx, June 2026,
                                           sheet "2026(Total)"

Outputs (output/)
  hdb_blocks_children_final.gpkg, layer "hdb_blocks_children"
      residential blocks + child_0_4, child_5_9, child_pop_0_9, used_fallback
  child_population_unassigned.csv
      subzone x age x flat type cells whose children could not be placed on any block

Run:  python scripts/assign_child_population_fillnull.py
Requires: geopandas, pandas, openpyxl
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "output"

HDB_GPKG = OUT / "hdb_blocks.gpkg"
SUBZONE_GEOJSON = DATA / "MasterPlanSubZones_2019.geojson"
POP_XLSX = DATA / "subzone_child_population_2026.xlsx"
POP_SHEET = "2026(Total)"

OUT_GPKG = OUT / "hdb_blocks_children_final.gpkg"
OUT_LAYER = "hdb_blocks_children"
UNASSIGNED_CSV = OUT / "child_population_unassigned.csv"

AGE_GROUPS = {"0 - 4": "child_0_4", "5 - 9": "child_5_9"}

# SingStat flat type -> HDB Property Information unit columns.
# "1- and 2-Room Flats" includes studio apartments (SingStat footnote *).
FLAT_TYPES = {
    "1- and 2-Room Flats*": ["1room_sold", "2room_sold", "studio_apartment_sold",
                             "1room_rental", "2room_rental", "other_room_rental"],
    "3-Room Flats": ["3room_sold", "3room_rental"],
    "4-Room Flats": ["4room_sold"],
    "5-Room and Executive Flats": ["5room_sold", "exec_sold", "multigen_sold"],
}


def load_child_pop(path):
    """Children by subzone x age group x flat type, long format."""
    df = pd.read_excel(path, sheet_name=POP_SHEET, header=2)
    df.columns = ["planning_area", "subzone", "age", "flat_type", "pop"]
    df = df[df["age"].isin(AGE_GROUPS) & df["flat_type"].isin(FLAT_TYPES)
            & df["subzone"].ne("Total")].copy()
    df["pop"] = pd.to_numeric(df["pop"].replace("-", 0))  # "-" means nil
    df["subzone"] = df["subzone"].str.strip().str.upper()
    return df[["subzone", "age", "flat_type", "pop"]]


def main():
    OUT.mkdir(exist_ok=True)

    hdb = gpd.read_file(HDB_GPKG, layer="hdb_blocks")
    hdb = hdb[hdb["is_residential"]].reset_index(drop=True)
    hdb["block_id"] = hdb.index
    for flat_type, cols in FLAT_TYPES.items():
        hdb[flat_type] = hdb[cols].fillna(0).sum(axis=1)
    print(f"Residential HDB blocks: {len(hdb):,}")

    subzones = gpd.read_file(SUBZONE_GEOJSON)[["SUBZONE_N", "PLN_AREA_N", "geometry"]].to_crs(hdb.crs)
    centroids = gpd.GeoDataFrame(hdb[["block_id"]], geometry=hdb.centroid, crs=hdb.crs)
    located = gpd.sjoin(centroids, subzones, how="left", predicate="within").drop_duplicates("block_id")
    hdb = hdb.merge(located[["block_id", "SUBZONE_N", "PLN_AREA_N"]], on="block_id", how="left")
    hdb = hdb.rename(columns={"SUBZONE_N": "subzone", "PLN_AREA_N": "planning_area"})
    print(f"Blocks with no subzone (centroid outside every polygon): {int(hdb['subzone'].isna().sum())}")

    pop = load_child_pop(POP_XLSX)
    missing_names = set(pop["subzone"]) - set(subzones["SUBZONE_N"])
    if missing_names:
        print(f"WARNING: {len(missing_names)} population subzones not in the subzone map: {sorted(missing_names)}")

    # One row per block x age x flat type, so every share is computed by key, not row order.
    units = hdb.melt(id_vars=["block_id", "subzone", "total_dwelling_units"],
                     value_vars=list(FLAT_TYPES), var_name="flat_type", value_name="units")
    cells = units.merge(pop, on=["subzone", "flat_type"], how="inner")
    cells["type_total"] = cells.groupby(["subzone", "age", "flat_type"])["units"].transform("sum")
    cells["all_total"] = cells.groupby(["subzone", "age", "flat_type"])["total_dwelling_units"].transform("sum")
    cells["used_fallback"] = cells["type_total"].eq(0) & cells["pop"].gt(0)
    cells["share"] = (cells["units"] / cells["type_total"]).where(
        ~cells["used_fallback"], cells["total_dwelling_units"] / cells["all_total"]
    ).fillna(0)
    cells["children"] = cells["pop"] * cells["share"]

    per_block = cells.pivot_table(index="block_id", columns="age", values="children", aggfunc="sum")
    per_block = per_block.rename(columns=AGE_GROUPS).reindex(columns=list(AGE_GROUPS.values()))
    hdb = hdb.merge(per_block, left_on="block_id", right_index=True, how="left")
    hdb["child_pop_0_9"] = hdb["child_0_4"] + hdb["child_5_9"]
    fallback_blocks = set(cells.loc[cells["used_fallback"] & cells["children"].gt(0), "block_id"])
    hdb["used_fallback"] = hdb["block_id"].isin(fallback_blocks)

    # Children that reached no block: cells whose subzone has no matched residential block.
    placed = cells.groupby(["subzone", "age", "flat_type"])["children"].sum()
    totals = pop.set_index(["subzone", "age", "flat_type"])["pop"]
    lost = (totals - placed.reindex(totals.index).fillna(0)).round(6)
    lost = lost[lost > 0].rename("unassigned_children").reset_index()
    lost.to_csv(UNASSIGNED_CSV, index=False)

    total = pop["pop"].sum()
    assigned = hdb["child_pop_0_9"].sum()
    fb_children = cells.loc[cells["used_fallback"], "children"].sum()
    print(f"\nHDB children aged 0-9 (sum of flat types): {total:,.0f}")
    print(f"  assigned to blocks : {assigned:,.0f} ({assigned / total:.2%})")
    print(f"    via fallback     : {fb_children:,.0f} children, {len(fallback_blocks)} blocks")
    print(f"  unassigned         : {lost['unassigned_children'].sum():,.0f} "
          f"in {lost['subzone'].nunique()} subzones -> {UNASSIGNED_CSV.name}")
    print(f"Blocks with null child_pop_0_9: {int(hdb['child_pop_0_9'].isna().sum())}")
    print(f"Blocks with zero child_pop_0_9: {int(hdb['child_pop_0_9'].eq(0).sum())}")

    keep = ["join_key", "BLK_NO", "POSTAL_COD", "subzone", "planning_area", "match_status",
            "review_flag", "total_dwelling_units", "gfa_m2", *FLAT_TYPES, "child_0_4", "child_5_9",
            "child_pop_0_9", "used_fallback", "geometry"]
    hdb[keep].to_file(OUT_GPKG, layer=OUT_LAYER, driver="GPKG")
    print(f"\nWrote layer '{OUT_LAYER}' ({len(hdb):,} blocks) to {OUT_GPKG}")


if __name__ == "__main__":
    main()
