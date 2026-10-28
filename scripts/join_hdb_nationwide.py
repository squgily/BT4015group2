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

# Abbreviations HDB uses in only some street names, tried as a fallback so they don't
# break the names that keep the full word.
EXTRA_ABBR = {"MARKET": "MKT", "INDUSTRIAL": "IND"}

# Manual decisions for unmatched blocks checked by hand (OneMap, Google Maps, news).
# "include" blocks are absent from Property Information 2026 but judged residential;
# their attributes are imputed from the nearest same-street residential blocks.
MANUAL_REVIEW = {
    "87_JLN SATU": ("exclude", None, "Mountbatten Community Club, not residential"),
    "63_C'WEALTH DR": ("include", None, "Residential HDB block"),
    "82_MACPHERSON LANE": ("include", "verify_occupancy",
                           "SERS block (2018) repurposed for PPHS temporary housing"),
    "40_TANGLIN HALT RD": ("include", "verify_occupancy",
                           "SERS block with PPHS redevelopment plans"),
}
IMPUTE_NEIGHBOURS = 3

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


def resolve_keys(hdb, prop):
    """Return (join_key, match_status) per block, with two fallback passes.

    1. alt_spelling: the unabbreviated LTA name (HDB keeps e.g. "TAMAN HO SWEE",
       "BUANGKOK GREEN") or EXTRA_ABBR on top of ABBR ("NEW MKT RD").
    2. postal_sector: for road codes newer than the 2019 LTA table, match the block
       number among property rows in the same contract town, the town being inferred
       from the postal sector (first two digits) of blocks matched in pass 0/1.
       Accepted only when exactly one unused property row qualifies.
    """
    prop_keys = set(prop["join_key"])
    keys = hdb["join_key"].copy()
    status = pd.Series("unmatched", index=hdb.index)

    raw_key = hdb["blk_norm"] + "_" + hdb["decoded_street"].str.strip().str.upper()
    hit = keys.isin(prop_keys)
    status[hit] = (raw_key[hit] == keys[hit]).map({True: "exact", False: "normalized"})

    used = set(keys[hit])
    for i in hdb.index[~hit & hdb["decoded_street"].notna()]:
        street = hdb.at[i, "norm_street"]
        for candidate in (
            raw_key[i],
            hdb.at[i, "blk_norm"] + "_" + " ".join(EXTRA_ABBR.get(w, w) for w in street.split()),
        ):
            if candidate in prop_keys and candidate not in used:
                keys[i], status[i] = candidate, "alt_spelling"
                used.add(candidate)
                break

    town_by_key = prop.set_index("join_key")["bldg_contract_town"]
    matched = status != "unmatched"
    sector_towns = (
        pd.DataFrame({
            "sector": hdb.loc[matched, "POSTAL_COD"].str[:2],
            "town": keys[matched].map(town_by_key),
        })
        .groupby("sector")["town"].agg(set)
    )
    unused = prop[~prop["join_key"].isin(used)]
    for i in hdb.index[(status == "unmatched") & hdb["decoded_street"].isna()]:
        towns = sector_towns.get(str(hdb.at[i, "POSTAL_COD"])[:2], set())
        candidates = unused[
            (unused["blk_norm"] == hdb.at[i, "blk_norm"]) & unused["bldg_contract_town"].isin(towns)
        ]
        if len(candidates) == 1:
            keys[i], status[i] = candidates["join_key"].iloc[0], "postal_sector"
            unused = unused.drop(candidates.index)

    return keys, status


UNIT_COLS = [c for c in PROPERTY_COLS if c.endswith(("_sold", "_rental"))]


def impute_manual_includes(joined):
    """Fill attributes of MANUAL_REVIEW "include" blocks from same-street neighbours.

    Dwelling units = own footprint x median units per m2 of the IMPUTE_NEIGHBOURS
    nearest matched residential blocks on the same street; the flat-type mix, floors,
    year and flags are taken from those neighbours. Sets match_status to "imputed".
    """
    keys = [k for k, (decision, _, _) in MANUAL_REVIEW.items() if decision == "include"]
    targets = joined.index[joined["join_key"].isin(keys) & joined["match_status"].eq("unmatched")]
    for i in targets:
        pool = joined[joined["norm_street"].eq(joined.at[i, "norm_street"])
                      & joined["residential"].eq("Y")]
        nearest = pool.loc[
            pool.geometry.centroid.distance(joined.geometry[i].centroid).nsmallest(IMPUTE_NEIGHBOURS).index
        ]
        units = round(joined.at[i, "footprint_m2"]
                      * (nearest["total_dwelling_units"] / nearest["footprint_m2"]).median())
        mix = nearest[UNIT_COLS].sum() / nearest[UNIT_COLS].sum().sum()
        joined.loc[i, UNIT_COLS] = (mix * units).round().to_numpy()
        joined.at[i, "total_dwelling_units"] = joined.loc[i, UNIT_COLS].sum()
        joined.at[i, "max_floor_lvl"] = nearest["max_floor_lvl"].median()
        joined.at[i, "year_completed"] = nearest["year_completed"].median()
        for col in ["bldg_contract_town", "residential", "commercial", "market_hawker",
                    "miscellaneous", "multistorey_carpark", "precinct_pavilion"]:
            joined.at[i, col] = nearest[col].mode().iloc[0]
        joined.at[i, "match_status"] = "imputed"
        print(f"  imputed {joined.at[i, 'join_key']}: {int(joined.at[i, 'total_dwelling_units'])} units "
              f"from {', '.join(nearest['BLK_NO'])}")
    return joined


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

    hdb["join_key"], hdb["match_status"] = resolve_keys(hdb, prop)

    joined = hdb.merge(prop[["join_key"] + PROPERTY_COLS], on="join_key", how="left")

    joined = joined.to_crs(CRS_OUT)
    joined["footprint_m2"] = joined.geometry.area
    joined = impute_manual_includes(joined)
    joined["gfa_m2"] = joined["footprint_m2"] * joined["max_floor_lvl"]
    joined["is_residential"] = joined["residential"].eq("Y")
    joined["review_flag"] = joined["join_key"].map(
        {k: flag for k, (_, flag, _) in MANUAL_REVIEW.items() if flag}
    )

    n = len(joined)
    n_matched = int((joined["match_status"] != "unmatched").sum())
    print(f"Nationwide HDB join: {n_matched}/{n} matched ({n_matched / n:.1%})")
    print(joined["match_status"].value_counts().to_string())
    print(f"Residential blocks: {int(joined['is_residential'].sum())}, "
          f"dwelling units: {int(joined['total_dwelling_units'].sum())}")

    joined.to_file(OUT_GPKG, layer=OUT_LAYER, driver="GPKG")
    print(f"Wrote layer '{OUT_LAYER}' ({n} features, {CRS_OUT}) to {OUT_GPKG}")

    unmatched = joined[joined["match_status"].isin(["unmatched", "imputed"])].copy()
    unmatched["reason"] = unmatched["decoded_street"].isna().map(
        {True: "undecoded_road_code", False: "no_match_in_property_info"}
    )
    # Unmatched blocks are excluded from demand (is_residential is False for them).
    unmatched["resolution"] = unmatched["match_status"].map(
        {"imputed": "included_imputed", "unmatched": "excluded_not_in_property_info"}
    )
    unmatched["review_note"] = unmatched["join_key"].map(
        {k: note for k, (_, _, note) in MANUAL_REVIEW.items()}
    )
    unmatched[["BLK_NO", "ST_COD", "POSTAL_COD", "decoded_street", "norm_street",
               "footprint_m2", "total_dwelling_units", "reason", "resolution",
               "review_flag", "review_note"]].to_csv(
        REVIEW_CSV, index=False
    )
    print(f"Wrote {len(unmatched)} unmatched/imputed rows to {REVIEW_CSV}")


if __name__ == "__main__":
    main()
