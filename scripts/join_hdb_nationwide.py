"""
BT4015 Group 2 - preprocessing step 1
Join HDB block polygons (HDB Existing Building) to HDB block attributes
(HDB Property Information) for all of Singapore.

Why a script is needed: the two datasets share no key. The polygon file identifies a
block by BLK_NO + ST_COD (an LTA road code); the CSV identifies it by blk_no + an
abbreviated street name (e.g. "BEDOK STH AVE 1"). We decode ST_COD with LTA's
road-code table, rewrite full-word suffixes into HDB's abbreviations (AVENUE -> AVE,
SOUTH -> STH, ROAD -> RD ...), and join on "BLK_STREET". Without the abbreviation
step only ~10% of blocks match; with it 98.8% match.

Inputs  (data/):
  HDBExistingBuilding_2026.geojson   data.gov.sg d_16b157c52ed637edd6ba1232e026258d (2026-06-21)
  HDBPropertyInformation_2026.csv    data.gov.sg d_17f5382f26140b1fdae0ba2ef6239d2f (2026-10-08)
  LTARoadNameCode_2019.xlsx          LTA DataMall road-code lookup, sheet GISDomainData

Outputs (output/):
  hdb_blocks.gpkg, layer "hdb_blocks"  all 13,436 blocks, EPSG:3414, with CSV attributes,
                                       footprint_m2, gfa_m2 (= footprint x max_floor_lvl),
                                       is_residential, match_status
  hdb_join_review.csv                  the ~156 blocks that did not match, for manual checking

Run from anywhere:  python scripts/join_hdb_nationwide.py
Requires: geopandas, pyogrio, pandas, openpyxl
"""
from pathlib import Path

import pandas as pd
import pyogrio

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "output"

HDB_GEOJSON = DATA / "HDBExistingBuilding_2026.geojson"
HDB_PROPERTY_CSV = DATA / "HDBPropertyInformation_2026.csv"
ROAD_CODE_XLSX = DATA / "LTARoadNameCode_2019.xlsx"

OUT_GPKG = OUT / "hdb_blocks.gpkg"
OUT_LAYER = "hdb_blocks"
REVIEW_CSV = OUT / "hdb_join_review.csv"

CRS_OUT = "EPSG:3414"  # SVY21 / Singapore TM, metres

# LTA spells suffixes in full; HDB Property Information abbreviates them.
ABBR = {
    "ROAD": "RD", "STREET": "ST", "AVENUE": "AVE", "DRIVE": "DR", "CRESCENT": "CRES",
    "JALAN": "JLN", "LORONG": "LOR", "NORTH": "NTH", "SOUTH": "STH", "CENTRAL": "CTRL",
    "PLACE": "PL", "TERRACE": "TER", "GARDENS": "GDNS", "GARDEN": "GDN", "PARK": "PK",
    "CLOSE": "CL", "HEIGHTS": "HTS", "GROVE": "GR", "BOULEVARD": "BLVD", "HIGHWAY": "HWY",
    "UPPER": "UPP", "BUKIT": "BT", "KAMPONG": "KG", "TANJONG": "TG", "TAMAN": "TMN",
    "GREEN": "GRN", "COMMONWEALTH": "C'WEALTH", "SQUARE": "SQ",
}

# Columns carried over from the CSV (beyond the join key).
PROPERTY_COLS = [
    "year_completed", "max_floor_lvl", "bldg_contract_town",
    "residential", "commercial", "market_hawker", "miscellaneous",
    "multistorey_carpark", "precinct_pavilion",
    "total_dwelling_units",
    "1room_sold", "2room_sold", "3room_sold", "4room_sold", "5room_sold",
    "exec_sold", "multigen_sold", "studio_apartment_sold",
    "1room_rental", "2room_rental", "3room_rental", "other_room_rental",
]


def normalize_street(name):
    if not isinstance(name, str):
        return None
    return " ".join(ABBR.get(w, w) for w in name.strip().upper().split())


def normalize_blk(blk):
    return str(blk).strip().upper() if pd.notna(blk) else blk


def main():
    OUT.mkdir(exist_ok=True)

    hdb = pyogrio.read_dataframe(HDB_GEOJSON)

    road = pd.read_excel(ROAD_CODE_XLSX, sheet_name="GISDomainData", skiprows=2)
    road.columns = ["S_No", "Road_Code", "Road_Name"]
    road = road.dropna(subset=["Road_Code"])
    road_lookup = dict(zip(road["Road_Code"], road["Road_Name"]))

    hdb["decoded_street"] = hdb["ST_COD"].map(road_lookup)
    hdb["norm_street"] = hdb["decoded_street"].map(normalize_street)
    hdb["blk_norm"] = hdb["BLK_NO"].map(normalize_blk)
    hdb["join_key"] = hdb["blk_norm"] + "_" + hdb["norm_street"].fillna("")

    prop = pd.read_csv(HDB_PROPERTY_CSV)
    prop["blk_norm"] = prop["blk_no"].map(normalize_blk)
    prop["street_norm"] = prop["street"].str.strip().str.upper()
    prop["join_key"] = prop["blk_norm"] + "_" + prop["street_norm"]
    dup = prop["join_key"].duplicated().sum()
    if dup:
        print(f"WARNING: {dup} duplicate keys in property CSV, keeping first")
        prop = prop.drop_duplicates("join_key")

    joined = hdb.merge(prop[["join_key"] + PROPERTY_COLS], on="join_key", how="left")

    def match_status(row):
        if pd.isna(row["decoded_street"]) or pd.isna(row["year_completed"]):
            return "unmatched"
        raw_key = row["blk_norm"] + "_" + row["decoded_street"].strip().upper()
        return "exact" if raw_key == row["join_key"] else "normalized"

    joined["match_status"] = joined.apply(match_status, axis=1)

    joined = joined.to_crs(CRS_OUT)
    joined["footprint_m2"] = joined.geometry.area
    joined["gfa_m2"] = joined["footprint_m2"] * joined["max_floor_lvl"]
    joined["is_residential"] = joined["residential"].eq("Y")

    n = len(joined)
    n_matched = int((joined["match_status"] != "unmatched").sum())
    print(f"Nationwide HDB join: {n_matched}/{n} matched ({n_matched / n:.1%})")
    print(joined["match_status"].value_counts().to_string())
    print(f"Residential blocks: {int(joined['is_residential'].sum())}, "
          f"dwelling units: {int(joined['total_dwelling_units'].sum())}")

    joined.to_file(OUT_GPKG, layer=OUT_LAYER, driver="GPKG")
    print(f"Wrote layer '{OUT_LAYER}' ({n} features, {CRS_OUT}) to {OUT_GPKG}")

    unmatched = joined[joined["match_status"] == "unmatched"].copy()
    unmatched["reason"] = unmatched["decoded_street"].isna().map(
        {True: "undecoded_road_code", False: "no_match_in_property_info"}
    )
    unmatched[["BLK_NO", "ST_COD", "POSTAL_COD", "decoded_street", "norm_street", "reason"]].to_csv(
        REVIEW_CSV, index=False
    )
    print(f"Wrote {len(unmatched)} unmatched rows to {REVIEW_CSV}")


if __name__ == "__main__":
    main()
