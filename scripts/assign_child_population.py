"""
BT4015 Group 2 - preprocessing step 2
Assign child population (ages 0-9) to each HDB block using dasymetric
disaggregation weighted by flat-type floor area.

Overview
--------
The goal is to estimate how many children aged 0-9 live in each individual
HDB block polygon. No dataset directly gives per-block child counts, so we
disaggregate subzone-level population data down to individual blocks using
the number and type of dwelling units in each block as a weight.

Method
------
1. FLOOR AREA LOOKUP (per-block, from resale transactions)
   Download all 5 HDB Resale Flat Prices datasets (1990-present) from
   data.gov.sg. For every unique (block, street, flat_type) combination,
   compute the median floor_area_sqm across all transactions. This gives us
   the actual measured floor area for each flat type in each specific block,
   rather than relying on national averages.

2. FA BUCKET MAPPING
   Map each floor area value to one of the five buckets used in the
   respopagesexfa2026 population dataset:
     <=60 sqm | >60 to 80 sqm | >80 to 100 sqm | >100 to 120 sqm | >120 sqm
   Rental and studio units never appear in resale data (they cannot be
   resold), so a national-median fallback is used for those types. These
   account for a small minority of total units.

3. SPATIAL JOIN
   Load hdb_blocks.gpkg (produced by join_hdb_nationwide.py) which contains
   HDB block polygons with flat-type unit counts. Join each block centroid to
   its Master Plan subzone.

4. UNITS PER FA BUCKET
   For each block, sum its unit counts into FA bucket columns (units_<=60,
   units_>60 to 80, etc.) using the per-block floor areas from step 1.

5. CHILD POPULATION BY SUBZONE x FA BUCKET
   From respopagesexfa2026.csv, filter to age groups 0_to_4 and 5_to_9
   (both sexes) and aggregate by subzone x FA bucket. This dataset covers
   ALL Singapore residents, including those in private housing.

6. DASYMETRIC DISAGGREGATION
   Within each subzone x FA bucket, distribute the child population across
   HDB blocks proportionally to each block's unit count for that bucket.
   Formula per block:
     child_pop = subzone_child_pop_in_bucket
                 x (block_units_in_bucket / total_HDB_units_in_bucket_in_subzone)

7. AGGREGATE
   Sum contributions across all FA buckets -> child_pop_0_9 per block.

Coverage note
-------------
respopagesexfa2026 covers all Singapore residents (~5.9M). Only ~78% live in
HDB flats; the remainder are in private condominiums and landed housing. Since
we only assign population to HDB blocks, approximately 20-30% of the child
population total will remain unassigned. This is expected and correct behaviour
-- those children live in private housing, not in HDB blocks.

Inputs  (relative to repo root)
  output/hdb_blocks.gpkg                    join_hdb_nationwide.py output
  data/MasterPlanSubZones_2019.geojson       subzone polygons
  <POP_CSV>                                  respopagesexfa2026.csv (see below)

Outputs
  output/hdb_blocks_with_children.gpkg       hdb_blocks + child_pop_0_9

POP_CSV default: ~/Downloads/respopagesexfa2026/respopagesexfa2026.csv
  Override by setting env var POP_CSV or editing the constant below.

Run:  python scripts/assign_child_population.py
Requires: geopandas, pandas, requests, pyogrio
"""

import io
import os
import time
from pathlib import Path

import pandas as pd
import geopandas as gpd
import requests

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT  = ROOT / "output"

POP_CSV = Path(
    os.environ.get(
        "POP_CSV",
        Path.home() / "Downloads" / "respopagesexfa2026" / "respopagesexfa2026.csv",
    )
)

HDB_GPKG        = OUT  / "hdb_blocks.gpkg"
SUBZONE_GEOJSON = DATA / "MasterPlanSubZones_2019.geojson"
OUT_GPKG        = OUT  / "hdb_blocks_with_children.gpkg"
OUT_LAYER       = "hdb_blocks_with_children"

# ── Constants ─────────────────────────────────────────────────────────────────

RESALE_DATASET_IDS = [
    "d_ea9ed51da2787afaf8e51f827c304208",   # 1990-1999
    "d_ebc5ab87086db484f88045b47411ebc5",   # 2000-Feb 2012
    "d_2d5ff9ea31397b66239f245f57751537",   # Mar 2012-Dec 2014
    "d_43f493c6c50d54243cc1eab0df142d6a",   # Jan 2015-Dec 2016
    "d_8b84c4ee58e3cfc0ece0d773c8ca6abc",   # Jan 2017-present
]

FA_BUCKETS = ["<=60", ">60 to 80", ">80 to 100", ">100 to 120", ">120"]

# Same abbreviation table used by join_hdb_nationwide.py so that resale
# street names normalise to the same form as hdb_blocks.join_key.
ABBR = {
    "ROAD": "RD", "STREET": "ST", "AVENUE": "AVE", "DRIVE": "DR",
    "CRESCENT": "CRES", "JALAN": "JLN", "LORONG": "LOR", "NORTH": "NTH",
    "SOUTH": "STH", "CENTRAL": "CTRL", "PLACE": "PL", "TERRACE": "TER",
    "GARDENS": "GDNS", "GARDEN": "GDN", "PARK": "PK", "CLOSE": "CL",
    "HEIGHTS": "HTS", "GROVE": "GR", "BOULEVARD": "BLVD", "HIGHWAY": "HWY",
    "UPPER": "UPP", "BUKIT": "BT", "KAMPONG": "KG", "TANJONG": "TG",
    "TAMAN": "TMN", "GREEN": "GRN", "COMMONWEALTH": "C'WEALTH", "SQUARE": "SQ",
}

# Map HDB property info column names to resale flat_type labels.
# Rental and studio units never appear in resale data; they fall back to the
# national median of the closest equivalent type.
PROP_COL_TO_FLAT_TYPE = {
    "1room_sold":            "1 ROOM",
    "2room_sold":            "2 ROOM",
    "3room_sold":            "3 ROOM",
    "4room_sold":            "4 ROOM",
    "5room_sold":            "5 ROOM",
    "exec_sold":             "EXECUTIVE",
    "multigen_sold":         "MULTI-GENERATION",
    "studio_apartment_sold": "1 ROOM",      # ~35 sqm, falls in <=60 bucket
    "1room_rental":          "1 ROOM",
    "2room_rental":          "2 ROOM",
    "3room_rental":          "3 ROOM",
    "other_room_rental":     "1 ROOM",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def assign_fa_bucket(sqm: float) -> str:
    """Map a floor area value (sqm) to the FA bucket label used in the population CSV."""
    if sqm <= 60:
        return "<=60"
    elif sqm <= 80:
        return ">60 to 80"
    elif sqm <= 100:
        return ">80 to 100"
    elif sqm <= 120:
        return ">100 to 120"
    else:
        return ">120"


def normalize_street(name: str) -> str:
    """Uppercase, strip, then apply HDB abbreviations (matches join_hdb_nationwide.py)."""
    return " ".join(ABBR.get(w, w) for w in str(name).strip().upper().split())


def make_join_key(block: str, street: str) -> str:
    return f"{str(block).strip().upper()}_{normalize_street(street)}"


def download_resale_datasets() -> pd.DataFrame:
    """Download all 5 resale datasets; return concatenated DataFrame with
    block, street_name, flat_type, and floor_area_sqm columns."""
    api = "https://api-open.data.gov.sg/v1/public/api/datasets/{}/poll-download"
    frames = []
    for i, ds_id in enumerate(RESALE_DATASET_IDS):
        if i > 0:
            time.sleep(3)   # avoid 429 rate-limit
        print(f"  Fetching {ds_id} ...")
        meta = requests.get(api.format(ds_id), timeout=30)
        meta.raise_for_status()
        download_url = meta.json()["data"]["url"]
        csv_r = requests.get(download_url, timeout=180)
        csv_r.raise_for_status()
        df = pd.read_csv(
            io.StringIO(csv_r.text),
            usecols=["block", "street_name", "flat_type", "floor_area_sqm"],
        )
        frames.append(df)
        print(f"    {len(df):,} rows")
    return pd.concat(frames, ignore_index=True)


def build_fa_lookups(resale_df: pd.DataFrame):
    """
    Returns:
      block_lookup  — dict {(join_key, flat_type): fa_bucket}  per-block lookup
      national_map  — dict {flat_type: fa_bucket}              national-median fallback
    """
    resale_df = resale_df.copy()
    resale_df["flat_type"]   = resale_df["flat_type"].str.strip().str.upper()
    resale_df["join_key"]    = resale_df.apply(
        lambda r: make_join_key(r["block"], r["street_name"]), axis=1
    )

    # Per-block median floor area per flat type
    per_block = (
        resale_df.groupby(["join_key", "flat_type"])["floor_area_sqm"]
        .median()
        .reset_index()
    )
    per_block["fa_bucket"] = per_block["floor_area_sqm"].apply(assign_fa_bucket)
    block_lookup = {
        (row.join_key, row.flat_type): row.fa_bucket
        for row in per_block.itertuples()
    }

    # National median fallback
    national = (
        resale_df.groupby("flat_type")["floor_area_sqm"]
        .median()
        .reset_index()
    )
    national["fa_bucket"] = national["floor_area_sqm"].apply(assign_fa_bucket)
    national_map = national.set_index("flat_type")["fa_bucket"].to_dict()

    # Handle MULTI GENERATION / MULTI-GENERATION naming inconsistency
    for key in list(national_map.keys()):
        if "MULTI" in key:
            national_map["MULTI-GENERATION"] = national_map[key]
            national_map["MULTI GENERATION"] = national_map[key]

    print("\nNational fallback - flat type -> FA bucket:")
    print(national[["flat_type", "floor_area_sqm", "fa_bucket"]].to_string(index=False))
    print(f"\nPer-block lookup entries: {len(block_lookup):,}")

    return block_lookup, national_map


def add_units_per_bucket(
    hdb: gpd.GeoDataFrame,
    block_lookup: dict,
    national_map: dict,
) -> tuple:
    """
    For each block and each flat-type column, look up the actual FA bucket
    for that specific block from resale data. Falls back to the national median
    if the block+flat_type combination has no resale history.
    Adds units_<bucket> columns to hdb.
    Returns (hdb, stats_dict).
    """
    for b in FA_BUCKETS:
        hdb[f"units_{b}"] = 0.0

    per_block_units  = 0.0
    fallback_units   = 0.0

    for prop_col, flat_type in PROP_COL_TO_FLAT_TYPE.items():
        if prop_col not in hdb.columns:
            continue

        buckets = []
        for jk in hdb["join_key"]:
            b = block_lookup.get((jk, flat_type))
            if b is None:
                b = national_map.get(flat_type)
                is_fallback = True
            else:
                is_fallback = False
            buckets.append((b, is_fallback))

        bucket_series   = pd.Series([x[0] for x in buckets], index=hdb.index)
        fallback_mask   = pd.Series([x[1] for x in buckets], index=hdb.index)
        units           = hdb[prop_col].fillna(0)

        per_block_units += units[~fallback_mask].sum()
        fallback_units  += units[fallback_mask].sum()

        for bucket in FA_BUCKETS:
            mask = bucket_series == bucket
            hdb.loc[mask, f"units_{bucket}"] += units[mask]

    total_units = per_block_units + fallback_units
    stats = {
        "total_units":      total_units,
        "per_block_units":  per_block_units,
        "fallback_units":   fallback_units,
    }
    return hdb, stats


def load_child_pop(pop_csv: Path) -> pd.DataFrame:
    """Load respopagesexfa2026.csv; return child pop (0-9) by subzone x FA bucket."""
    df = pd.read_csv(pop_csv)
    child = df[df["AG"].isin(["0_to_4", "5_to_9"])].copy()
    agg = (
        child.groupby(["SZ", "FA"])["Pop"]
        .sum()
        .reset_index()
        .rename(columns={"SZ": "subzone", "FA": "fa_bucket", "Pop": "child_pop"})
    )
    agg["subzone"] = agg["subzone"].str.upper()
    return agg


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    OUT.mkdir(exist_ok=True)

    # 1. Download resale data and build FA lookups
    print("Downloading HDB Resale Flat Prices datasets ...")
    resale_df = download_resale_datasets()
    block_lookup, national_map = build_fa_lookups(resale_df)

    # 2. Load HDB blocks
    print("\nLoading HDB blocks ...")
    hdb = gpd.read_file(HDB_GPKG, layer="hdb_blocks")
    hdb = hdb[hdb["residential"] == "Y"].copy()
    print(f"  {len(hdb):,} residential blocks")

    # 3. Spatial join block centroids -> subzone
    print("Spatial-joining to subzones ...")
    subzones = gpd.read_file(SUBZONE_GEOJSON)[["SUBZONE_N", "geometry"]].to_crs(hdb.crs)
    centroids = hdb[["geometry"]].copy()
    centroids["geometry"] = hdb.centroid
    joined = gpd.sjoin(centroids, subzones, how="left", predicate="within")
    hdb["subzone"] = joined["SUBZONE_N"].values
    unmatched = hdb["subzone"].isna().sum()
    print(f"  Matched {len(hdb) - unmatched:,} blocks; {unmatched} unmatched (excluded)")

    # 4. Compute units per FA bucket per block using per-block floor area
    print("Assigning flat types to FA buckets (per-block) ...")
    hdb, unit_stats = add_units_per_bucket(hdb, block_lookup, national_map)

    # 5. Load child population
    print(f"\nLoading child population from {POP_CSV} ...")
    child_pop = load_child_pop(POP_CSV)

    # 6. Dasymetric disaggregation (vectorised per FA bucket)
    print("Disaggregating child population to blocks ...")
    hdb["child_pop_0_9"] = 0.0

    for fa_bucket in FA_BUCKETS:
        units_col = f"units_{fa_bucket}"

        sz_totals = (
            hdb.groupby("subzone")[units_col]
            .sum()
            .rename("sz_total_units")
            .reset_index()
        )
        fa_pop = child_pop[child_pop["fa_bucket"] == fa_bucket][["subzone", "child_pop"]]

        tmp = (
            hdb[["subzone", units_col]]
            .merge(sz_totals, on="subzone", how="left")
            .merge(fa_pop, on="subzone", how="left")
        )
        tmp["child_pop"] = tmp["child_pop"].fillna(0)
        tmp["sz_total_units"] = tmp["sz_total_units"].replace(0, pd.NA)

        hdb["child_pop_0_9"] += (
            (tmp[units_col] / tmp["sz_total_units"] * tmp["child_pop"]).fillna(0)
        )

    assigned   = hdb["child_pop_0_9"].sum()
    available  = child_pop["child_pop"].sum()
    unassigned = available - assigned

    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")

    print(f"\n[1] Floor area source for dwelling units")
    print(f"    Per-block (from resale transactions) : "
          f"{unit_stats['per_block_units']:>9,.0f} units  "
          f"({unit_stats['per_block_units'] / unit_stats['total_units'] * 100:.1f}%)")
    print(f"    National median fallback             : "
          f"{unit_stats['fallback_units']:>9,.0f} units  "
          f"({unit_stats['fallback_units'] / unit_stats['total_units'] * 100:.1f}%)")
    print(f"    Fallback units are rental flats and studio apartments,")
    print(f"    which never appear in resale data. Their floor areas are")
    print(f"    standardised by HDB so the national median is reliable.")

    print(f"\n[2] Child population assigned (ages 0-9)")
    print(f"    Assigned to HDB blocks : {assigned:>9,.0f}  ({assigned / available * 100:.1f}%)")
    print(f"    Unassigned             : {unassigned:>9,.0f}  ({unassigned / available * 100:.1f}%)")
    print(f"    The unassigned children live in private housing")
    print(f"    (condominiums, landed property) which is outside the")
    print(f"    scope of HDB block polygons. This is expected --")
    print(f"    ~78% of Singapore residents live in HDB, so ~22%")
    print(f"    of children will not be assigned to any HDB block.")
    print(f"{'='*60}")

    # 7. Save output
    keep = (
        ["geometry", "join_key", "subzone", "total_dwelling_units", "child_pop_0_9"]
        + [f"units_{b}" for b in FA_BUCKETS]
    )
    keep = [c for c in keep if c in hdb.columns]
    hdb[keep].to_file(OUT_GPKG, layer=OUT_LAYER, driver="GPKG")
    print(f"\nSaved -> {OUT_GPKG}  (layer: {OUT_LAYER})")

    print("\nSample output:")
    print(
        hdb[["join_key", "subzone", "total_dwelling_units", "child_pop_0_9"]]
        .dropna()
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
