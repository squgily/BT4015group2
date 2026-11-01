"""
Locate the 80 rows of the 2026 ECDA centre list that build_childcare_centres_2026.py drops
(centre_code 'na'), and check whether leaving them out biases the subzone analysis (H-c).

Groups (mutually exclusive):
  invalid_postal  postal code 000000; located from the block + street, or the project name
  postal_in_layer postal code already used by a retained centre; reuse that centre's point
  postal_absent   valid postal code with no retained centre; geocoded by postal code
OneMap responses are cached in output/onemap_geocode_cache.csv (shared with the main build).

Output: output/excluded_centres_2026.csv (one row per excluded record, with location,
        subzone, the retained centres at the same postal code and the H-c LISA labels)
Run:    python scripts/locate_excluded_centres_2026.py
"""
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "CentreAttributes_2026.csv"
LAYER = ROOT / "output" / "childcare_centres_2026.gpkg"
SUBZONES = ROOT / "data" / "MasterPlanSubZones_2019.geojson"
LISA = ROOT / "output" / "subzone_lisa_hc.csv"
CACHE = ROOT / "output" / "onemap_geocode_cache.csv"
OUT = ROOT / "output" / "excluded_centres_2026.csv"
URL = "https://www.onemap.gov.sg/api/common/elastic/search"

# Search text for the postal-000000 rows, read off centre_address by hand. Block + street
# where one is given, otherwise the HDB project name. None = nothing searchable.
INVALID_QUERIES = {
    "152,Towner Road": "152 TOWNER ROAD",
    "Dakota One": "DAKOTA ONE",
    "Yishun Boardwalk": "YISHUN BOARDWALK",
    "750,Jurong West Street 73": "750 JURONG WEST STREET 73",
    "N1 C25 Marsiling Grove": "MARSILING GROVE",
    "467B,Yishun Ave 6": "467B YISHUN AVENUE 6",
    "WOODLANDS N3 C16 Woodgrove Ascent": "WOODGROVE ASCENT",
    "MK16 Lot No": None,
    "PLC6 - Parc Woods": "PARC WOODS",
    "PAC5": None,
    "470B,SERANGOON CRESCENT": "470B SERANGOON CRESCENT",
    "N1 C6 Eastlink 2": "EASTLINK II",
    "76A,Circuit Road": "76A CIRCUIT ROAD",
    "Blk 665,Tampines St 64": "665 TAMPINES STREET 64",
    "646B,Tampines St 62": "646B TAMPINES STREET 62",
    "489C,Tampines Street 45": "489C TAMPINES STREET 45",
    "691D,Woodlands Drive 73": "691D WOODLANDS DRIVE 73",
    "223A,Sumang Lane": "223A SUMANG LANE",
    "445A,Northshore Drive": "445A NORTHSHORE DRIVE",
    "C59,Kent Heights": "KENT HEIGHTS",
    "Bishan Towers": "BISHAN TOWERS",
    "326,Ubi Avenue 1": "326 UBI AVENUE 1",
    "Bidadari C13": "BARTLEY GREENRISE",
    "443A,Bukit Batok West Avenue 8": "443A BUKIT BATOK WEST AVENUE 8",
}


def onemap(query, cache, want_postal=None):
    if query in cache:
        return cache[query]
    for attempt in range(6):
        r = requests.get(URL, params={"searchVal": query, "returnGeom": "Y",
                                      "getAddrDetails": "Y", "pageNum": 1},
                         headers={"User-Agent": "curl/8.4.0"}, timeout=(5, 10))
        if r.status_code == 429:
            time.sleep(4 + 3 * attempt)
            continue
        res = r.json().get("results", [])
        if want_postal:
            res = [x for x in res if x.get("POSTAL") == want_postal]
        hit = (float(res[0]["LATITUDE"]), float(res[0]["LONGITUDE"]), res[0]["POSTAL"],
               res[0]["ADDRESS"]) if res else (None, None, None, None)
        cache[query] = hit
        time.sleep(2.2)
        return hit
    raise RuntimeError(f"OneMap kept rate-limiting on {query!r}")


def main():
    raw = pd.read_csv(SRC, dtype=str)
    ex = raw[raw["centre_code"].str.lower() == "na"].copy()
    kept = gpd.read_file(LAYER, layer="centres")
    kept = kept[kept["record_source"] == "ecda_listed"]  # verified additions are among the 80
    kept_by_postal = kept.groupby("postal_code")
    ex["group"] = [
        "invalid_postal" if p == "000000"
        else "postal_in_layer" if p in kept_by_postal.groups else "postal_absent"
        for p in ex["postal_code"]]

    c = pd.read_csv(CACHE, dtype=str)
    cache = {q: (float(la), float(lo), p, a)
             for q, la, lo, p, a in c[["query", "lat", "lon", "postal", "address"]].values}

    rows = []
    for _, r in ex.iterrows():
        out = {"query": None, "lat": None, "lon": None, "onemap_address": None,
               "retained_centres_same_postal": None}
        if r["group"] == "postal_in_layer":
            same = kept_by_postal.get_group(r["postal_code"])
            pt = same.to_crs(4326).geometry.iloc[0]
            out.update(lat=pt.y, lon=pt.x, location_source="retained_centre_point",
                       retained_centres_same_postal="; ".join(
                           same["centre_code"] + " " + same["centre_name"]))
        else:
            if r["group"] == "postal_absent":
                q, want = r["postal_code"], r["postal_code"]
            else:
                key = next((k for k in INVALID_QUERIES if r["centre_address"].startswith(k)), None)
                q, want = INVALID_QUERIES.get(key), None
            if q:
                la, lo, p, a = onemap(q, cache, want)
                out.update(query=q, lat=la, lon=lo, onemap_address=a)
            out["location_source"] = "onemap" if out["lat"] is not None else "not_located"
        rows.append({**r[["tp_code", "centre_name", "service_model", "organisation_description",
                          "centre_address", "postal_code", "last_updated", "group"]], **out})

    pd.DataFrame([(q, *v) for q, v in cache.items() if v[0] is not None],
                 columns=["query", "lat", "lon", "postal", "address"]).to_csv(CACHE, index=False)

    df = pd.DataFrame(rows)
    # A OneMap hit on a postal code the layer already has is the same building as a
    # retained centre (all such cases are the same operator), so it counts as a duplicate.
    df["onemap_postal"] = df["onemap_address"].str.extract(r"(\d{6})$")[0]
    df["qa_status"] = "possible_missing"
    df.loc[df["onemap_postal"].isin(kept_by_postal.groups), "qa_status"] = "duplicate"
    df.loc[df["group"] == "postal_in_layer", "qa_status"] = "duplicate"
    df.loc[df["location_source"] == "not_located", "qa_status"] = "not_located"
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)
    sz = gpd.read_file(SUBZONES).to_crs(4326)[["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "geometry"]]
    pts = gpd.sjoin(pts, sz, how="left", predicate="within").drop(columns="index_right")
    lisa = pd.read_csv(LISA)[["SUBZONE_C", "children_0_9", "centres_n",
                              "centres_per_1000_children", "bv_walk_q", "bv_sup_q", "bv_sup_p"]]
    pts = pts.merge(lisa, on="SUBZONE_C", how="left")
    pts.drop(columns="geometry").to_csv(OUT, index=False)
    print(pts["group"].value_counts().to_string())
    print(pts["location_source"].value_counts().to_string())
    print(pts["qa_status"].value_counts().to_string())
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
