"""
Geocode the Oct-2026 ECDA centre listing (data/CentreAttributes_2026.csv) by postal code
with the OneMap search API, producing one point per active childcare / kindergarten centre.

Why: the 2021 ChildCareServices GeoJSON is stale (292 active centres have no 2021 point;
541 of the 2021 points no longer appear in 2026). Every 2026 row has a 6-digit postal code,
which in Singapore identifies one building, so OneMap search gives building-level points.

Output: data/Centres_2026.geojson (EPSG:4326) with centre_code, name, operator,
        service_model, address, postal_code, geocode_status, and the OneMap address matched.
        Optional: set ONEMAP_TOKEN env var to authenticate (works without, slower/rate-limited).
Run:    python scripts/geocode_centres_2026.py
"""
import os
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "CentreAttributes_2026.csv"
OLD_POINTS = ROOT / "data" / "ChildCareServices_2021.geojson"  # reused for shared postal codes
OUT = ROOT / "data" / "Centres_2026.geojson"
KEEP_MODELS = {"CC", "KN"}
URL = "https://www.onemap.gov.sg/api/common/elastic/search"
HEADERS = {"User-Agent": "curl/8.4.0"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
if os.environ.get("ONEMAP_TOKEN"):
    SESSION.headers["Authorization"] = os.environ["ONEMAP_TOKEN"]


def geocode(postal, retries=6):
    for attempt in range(retries):
        try:
            r = SESSION.get(URL, params={"searchVal": postal, "returnGeom": "Y",
                                         "getAddrDetails": "Y", "pageNum": 1}, timeout=(5, 10))
            if r.status_code == 200:
                res = [x for x in r.json().get("results", []) if x.get("POSTAL") == postal]
                if res:
                    x = res[0]
                    return float(x["LATITUDE"]), float(x["LONGITUDE"]), x["ADDRESS"], "ok"
                return None, None, None, "no_result"
            if r.status_code == 429:  # unauthenticated OneMap allows ~1 call / 2 s
                time.sleep(4 + 3 * attempt); continue
            return None, None, None, f"http_{r.status_code}"
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return None, None, None, "error"


def main():
    c = pd.read_csv(SRC)
    c = c[c["service_model"].isin(KEEP_MODELS)].drop_duplicates("centre_code").copy()
    c["postal_code"] = c["postal_code"].astype(str).str.zfill(6)
    cols = ["centre_code", "centre_name", "organisation_description", "service_model",
            "scheme_type", "centre_address", "postal_code", "weekday_full_day",
            "government_subsidy", "spark_certified", "last_updated"]
    c = c[cols].rename(columns={"organisation_description": "operator"})
    uniq = c["postal_code"].unique()
    # 1) reuse coordinates from the 2021 points for postal codes already seen there
    old = gpd.read_file(OLD_POINTS).to_crs(4326)
    old["pc"] = old["ADDRESSPOSTALCODE"].astype(str).str.zfill(6)
    old = old.drop_duplicates("pc").set_index("pc")
    cache = {p: (old.at[p, "geometry"].y, old.at[p, "geometry"].x, "reused 2021 point", "ok_2021")
             for p in uniq if p in old.index}
    todo = [p for p in uniq if p not in cache]
    print(f"{len(c)} active CC/KN centres, {len(uniq)} unique postal codes: "
          f"{len(cache)} reused from 2021 points, {len(todo)} to geocode via OneMap", flush=True)
    # 2) OneMap for the rest (throttled: no token -> ~1 request / 2 s)
    t0 = time.time()
    for i, p in enumerate(todo, 1):
        cache[p] = geocode(p)
        time.sleep(2.2)
        if i % 25 == 0:
            ok = sum(v[3].startswith("ok") for v in cache.values())
            print(f"  {i}/{len(todo)} done, {ok} ok, {time.time() - t0:.0f}s", flush=True)
    c["lat"] = c["postal_code"].map(lambda p: cache[p][0])
    c["lon"] = c["postal_code"].map(lambda p: cache[p][1])
    c["onemap_address"] = c["postal_code"].map(lambda p: cache[p][2])
    c["geocode_status"] = c["postal_code"].map(lambda p: cache[p][3])
    print(c["geocode_status"].value_counts().to_string())
    g = gpd.GeoDataFrame(c, geometry=gpd.points_from_xy(c["lon"], c["lat"]), crs="EPSG:4326")
    g.to_file(OUT, driver="GeoJSON")
    print(f"Wrote {OUT}: {len(g)} centres, {int(g.geocode_status.str.startswith('ok').sum())} with coordinates")
    bad = g[~g["geocode_status"].str.startswith("ok")]
    if len(bad):
        bad.drop(columns="geometry").to_csv(ROOT / "output" / "centres_2026_ungeocoded.csv", index=False)
        print(f"{len(bad)} centres without coordinates listed in output/centres_2026_ungeocoded.csv")


if __name__ == "__main__":
    main()
