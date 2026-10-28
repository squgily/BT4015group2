"""Build a 2026 childcare centre layer with locations and Nursery fees.

Base dataset is the 2026 ECDA centre list (CentreAttributes_2026.csv), so the
analysis covers currently listed centres rather than the 2021 GeoJSON.

1. Drop placeholder rows whose centre_code is "na" (they cannot be joined to
   fees and most have no name either).
2. Match each 2026 centre to the 2021 GeoJSON by postal code. When several
   2021 centres share that postal code, the most similar name is used. Matched
   centres reuse the 2021 coordinates, assuming they have not relocated (a
   shared postal code means the same building, so a renamed centre at the same
   address keeps a valid location).
3. Geocode only the unmatched centres (new, relocated, or invalid postal code)
   with the OneMap search API. Results are cached so reruns do not re-query.
4. Join the Nursery (4 yrs old) Full Day/SC fee by centre_code, using the same
   rules as join_childcare_fees.py. Centres with no listed fee, or several
   conflicting fees, are left missing and labelled in fee_status.

Outputs:
  output/childcare_centres_2026.gpkg       layer "centres", EPSG:3414
  output/childcare_centres_2026_review.csv centres that were geocoded or are
                                           still missing a location or fee
  output/onemap_geocode_cache.csv          OneMap responses keyed by query

Set ONEMAP_TOKEN in the environment if the search API asks for a token.

Requires: geopandas, pandas, requests
"""

from __future__ import annotations

import csv
import difflib
import os
import time
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from join_childcare_fees import BENCHMARK_LEVEL, core_name, load_fee_records

ATTRIBUTES_CSV = Path("data/CentreAttributes_2026.csv")
FEES_CSV = Path("data/ListingofCentreServices.csv")
CENTRES_2021 = Path("data/ChildCareServices_2021.geojson")
OUT_GPKG = Path("output/childcare_centres_2026.gpkg")
OUT_LAYER = "centres"
OUT_REVIEW = Path("output/childcare_centres_2026_review.csv")
GEOCODE_CACHE = Path("output/onemap_geocode_cache.csv")

CRS_OUT = "EPSG:3414"  # SVY21 / Singapore TM, metres
ONEMAP_SEARCH = "https://www.onemap.gov.sg/api/common/elastic/search"
NAME_MATCH_MIN = 0.6  # below this a same-postal match is labelled postal_only
REQUEST_PAUSE_S = 0.5  # OneMap allows about 250 calls a minute
MAX_RETRIES = 5
CACHE_SAVE_EVERY = 25


def valid_postal(value: str) -> bool:
    value = (value or "").strip()
    return len(value) == 6 and value.isdigit() and value != "000000"


def name_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, core_name(a), core_name(b)).ratio()


def load_centres_2026() -> pd.DataFrame:
    centres = pd.read_csv(ATTRIBUTES_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    centres["postal_code"] = centres["postal_code"].str.strip().str.zfill(6)
    placeholder = centres["centre_code"].str.strip().str.lower() == "na"
    print(f"2026 rows: {len(centres)}, dropping {placeholder.sum()} with centre_code 'na'")
    centres = centres[~placeholder].drop_duplicates("centre_code").reset_index(drop=True)
    return centres[
        ["centre_code", "centre_name", "organisation_code", "organisation_description",
         "service_model", "centre_address", "postal_code", "last_updated"]
    ]


def match_to_2021(centres: pd.DataFrame) -> pd.DataFrame:
    """Add lon/lat, the matched 2021 OBJECTID and location_source by postal code."""
    old = gpd.read_file(CENTRES_2021).to_crs("EPSG:4326")
    old["postal"] = old["ADDRESSPOSTALCODE"].fillna("").astype(str).str.strip().str.zfill(6)
    by_postal: dict[str, list[int]] = defaultdict(list)
    for index, postal in old["postal"].items():
        if valid_postal(postal):
            by_postal[postal].append(index)

    lon, lat, object_ids, sources, scores = [], [], [], [], []
    for row in centres.itertuples():
        candidates = by_postal.get(row.postal_code, []) if valid_postal(row.postal_code) else []
        if not candidates:
            lon.append(None); lat.append(None); object_ids.append(None)
            sources.append(None); scores.append(None)
            continue
        best = max(candidates, key=lambda i: name_similarity(row.centre_name, old.at[i, "NAME"]))
        score = name_similarity(row.centre_name, old.at[best, "NAME"])
        point = old.geometry[best]
        lon.append(point.x); lat.append(point.y)
        object_ids.append(int(old.at[best, "OBJECTID"]))
        sources.append("2021_postal_name" if score >= NAME_MATCH_MIN else "2021_postal_only")
        scores.append(round(score, 3))

    centres = centres.copy()
    centres["lon"], centres["lat"] = lon, lat
    centres["objectid_2021"] = pd.array(object_ids, dtype="Int64")
    centres["location_source"] = sources
    centres["name_similarity_2021"] = scores
    return centres


def load_cache() -> dict[str, dict[str, str]]:
    if not GEOCODE_CACHE.exists():
        return {}
    with GEOCODE_CACHE.open(encoding="utf-8", newline="") as handle:
        return {row["query"]: row for row in csv.DictReader(handle)}


def save_cache(cache: dict[str, dict[str, str]]) -> None:
    GEOCODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with GEOCODE_CACHE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query", "lat", "lon", "postal", "address"])
        writer.writeheader()
        writer.writerows(cache.values())


def onemap_search(query: str, session: requests.Session) -> dict[str, str]:
    params = {"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}
    headers = {"Authorization": os.environ["ONEMAP_TOKEN"]} if os.environ.get("ONEMAP_TOKEN") else {}
    for attempt in range(MAX_RETRIES):
        response = session.get(ONEMAP_SEARCH, params=params, headers=headers, timeout=30)
        if response.status_code != 429:
            break
        wait = float(response.headers.get("Retry-After") or 15 * (attempt + 1))
        print(f"  rate limited on {query!r}, waiting {wait:.0f}s")
        time.sleep(wait)
    response.raise_for_status()
    results = response.json().get("results", [])
    # For a postal-code query only accept a result in that postal code.
    if query.isdigit():
        results = [r for r in results if r.get("POSTAL") == query]
    if not results:
        return {"query": query, "lat": "", "lon": "", "postal": "", "address": ""}
    top = results[0]
    return {"query": query, "lat": top["LATITUDE"], "lon": top["LONGITUDE"],
            "postal": top.get("POSTAL", ""), "address": top.get("ADDRESS", "")}


def address_query(address: str) -> str:
    """'86,JALAN PERGAM,EAST VIEW GARDEN,488362' -> '86 JALAN PERGAM'."""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    parts = [p for p in parts if not (len(p) == 6 and p.isdigit())]
    return " ".join(parts[:2])


def geocode_unmatched(centres: pd.DataFrame) -> pd.DataFrame:
    cache = load_cache()
    session = requests.Session()
    centres = centres.copy()
    todo = centres.index[centres["lon"].isna()]
    print(f"Geocoding {len(todo)} unmatched centres with OneMap ({len(cache)} cached queries)")
    new_queries = 0
    try:
        for index in todo:
            row = centres.loc[index]
            queries = [row.postal_code] if valid_postal(row.postal_code) else []
            queries.append(address_query(row.centre_address))
            for query in filter(None, queries):
                if query not in cache:
                    cache[query] = onemap_search(query, session)
                    new_queries += 1
                    if new_queries % CACHE_SAVE_EVERY == 0:
                        save_cache(cache)
                        print(f"  {new_queries} queries done")
                    time.sleep(REQUEST_PAUSE_S)
                hit = cache[query]
                if hit["lat"]:
                    centres.at[index, "lat"] = float(hit["lat"])
                    centres.at[index, "lon"] = float(hit["lon"])
                    centres.at[index, "location_source"] = (
                        "onemap_postal" if query == row.postal_code else "onemap_address"
                    )
                    break
    finally:
        # Keep finished lookups even if the run crashes, so a rerun resumes.
        save_cache(cache)
    return centres


def join_fees(centres: pd.DataFrame) -> pd.DataFrame:
    """Add the Nursery Full Day/SC fee by centre_code, leaving gaps as missing."""
    records = {r.centre_code: r.fee for r in load_fee_records(FEES_CSV, ATTRIBUTES_CSV)}
    fees = pd.read_csv(FEES_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    benchmark = fees[
        (fees["type_of_service"].str.strip().str.casefold() == "full day")
        & (fees["type_of_citizenship"].str.strip().str.casefold() == "sc")
        & (fees["levels_offered"].str.strip() == BENCHMARK_LEVEL)
    ]
    has_benchmark_row = set(benchmark["centre_code"])

    centres = centres.copy()
    centres["FULL_DAY_SC_NURSERY_FEE"] = centres["centre_code"].map(records)
    centres["fee_status"] = "listed"
    centres.loc[~centres["centre_code"].isin(has_benchmark_row), "fee_status"] = "no_nursery_full_day_sc_listing"
    centres.loc[
        centres["centre_code"].isin(has_benchmark_row) & centres["FULL_DAY_SC_NURSERY_FEE"].isna(),
        "fee_status",
    ] = "conflicting_fees"
    return centres


def main() -> None:
    centres = load_centres_2026()
    centres = match_to_2021(centres)
    print("Matched to 2021 GeoJSON:")
    print(centres["location_source"].value_counts(dropna=False).to_string())

    centres = geocode_unmatched(centres)
    centres = join_fees(centres)

    located = centres["lon"].notna()
    gdf = gpd.GeoDataFrame(
        centres[located],
        geometry=gpd.points_from_xy(centres.loc[located, "lon"], centres.loc[located, "lat"]),
        crs="EPSG:4326",
    ).to_crs(CRS_OUT)
    OUT_GPKG.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT_GPKG, layer=OUT_LAYER, driver="GPKG")

    review = centres[
        ~centres["location_source"].fillna("").str.startswith("2021")
        | centres["FULL_DAY_SC_NURSERY_FEE"].isna()
    ]
    review.to_csv(OUT_REVIEW, index=False)

    print(f"\nCentres: {len(centres)}, located: {located.sum()}, no location: {(~located).sum()}")
    print(centres["location_source"].value_counts(dropna=False).to_string())
    print(centres["fee_status"].value_counts().to_string())
    print(f"Wrote {OUT_GPKG} ({len(gdf)} centres) and {OUT_REVIEW} ({len(review)} rows)")


if __name__ == "__main__":
    main()
