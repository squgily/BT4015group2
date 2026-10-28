"""
BT4015 - build the walking-time matrices with a local OSRM server (foot profile).

Origins:      output/hdb_blocks.gpkg, layer hdb_points (residential block centroids, EPSG:3414)
Destinations: data/Centres_2026.geojson              -> centres (geocoded 2026 ECDA listing)
              data/ChildCareServices_2021.geojson   -> centres2021 (legacy, comparison only)
              data/MRTStationExits_2026.geojson     -> mrt_exits
              data/BusStops_2026.geojson            -> bus_stops

For each destination set, the full origin x destination table is fetched in 100 x 100
chunks from OSRM's /table endpoint, labelled by origin OBJECTID and destination id (never
by row position), checked for unreachable cells, and written as parquet to large_data/
(git-ignored).  A per-origin summary (nearest minutes, counts within 10 / 15 min) is
written to output/hdb_walk_access.csv so it can be committed.

Setup (one-off, see README):
  osrm-extract -p "$(brew --prefix osrm-backend)/share/osrm/profiles/foot.lua" large_data/singapore.osm.pbf
  osrm-partition large_data/singapore.osrm
  osrm-customize large_data/singapore.osrm
  osrm-routed --algorithm mld --max-table-size 10000 -p 5001 large_data/singapore.osrm &

Run:  python scripts/build_walk_matrix.py [--sets centres,mrt_exits,bus_stops] [--port 5001]
"""
import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import requests
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
GPKG = ROOT / "output" / "hdb_blocks.gpkg"
LARGE = ROOT / "large_data"
OUT = ROOT / "output"

DEST_SETS = {
    "centres": (ROOT / "data" / "Centres_2026.geojson", "centre_code"),   # geocoded Oct-2026 ECDA listing
    "centres2021": (ROOT / "data" / "ChildCareServices_2021.geojson", "OBJECTID"),  # legacy, for comparison
    "mrt_exits": (ROOT / "data" / "MRTStationExits_2026.geojson", "OBJECTID"),
    "bus_stops": (ROOT / "data" / "BusStops_2026.geojson", "OBJECTID_1"),
}
CHUNK = 100
THRESHOLDS_MIN = (10, 15)


def lonlat(gdf):
    g = gdf.to_crs(4326).geometry
    g = g.centroid if (g.geom_type != "Point").any() else g
    return np.c_[g.x.to_numpy(), g.y.to_numpy()]


def osrm_table(base, src_xy, dst_xy, annotation, retries=3):
    coords = ";".join(f"{x:.6f},{y:.6f}" for x, y in np.vstack([src_xy, dst_xy]))
    n = len(src_xy)
    params = {
        "sources": ";".join(map(str, range(n))),
        "destinations": ";".join(map(str, range(n, n + len(dst_xy)))),
        "annotations": annotation,
    }
    for attempt in range(retries):
        try:
            r = requests.get(f"{base}/table/v1/foot/{coords}", params=params, timeout=120)
            if r.status_code == 200:
                data = r.json()[annotation + "s"]
                return np.array([[np.nan if v is None else v for v in row] for row in data], dtype=float)
            msg = r.text[:200]
        except requests.RequestException as e:
            msg = str(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"OSRM table request failed after {retries} tries: {msg}")


def build(base, name, origins, o_xy, o_ids):
    path, id_col = DEST_SETS[name]
    dest = pyogrio.read_dataframe(path)
    d_xy, d_ids = lonlat(dest), dest[id_col].to_numpy()
    T = np.full((len(o_xy), len(d_xy)), np.nan)
    D = np.full_like(T, np.nan)
    o_chunks = range(0, len(o_xy), CHUNK)
    d_chunks = range(0, len(d_xy), CHUNK)
    with tqdm(total=len(o_chunks) * len(d_chunks), desc=name, unit="call") as bar:
        for i in o_chunks:
            for j in d_chunks:
                so, sd = o_xy[i:i + CHUNK], d_xy[j:j + CHUNK]
                T[i:i + CHUNK, j:j + CHUNK] = osrm_table(base, so, sd, "duration") / 60.0
                D[i:i + CHUNK, j:j + CHUNK] = osrm_table(base, so, sd, "distance")
                bar.update(1)
    n_nan = int(np.isnan(T).sum())
    print(f"{name}: {T.shape[0]:,} x {T.shape[1]:,}; unreachable cells: {n_nan:,} "
          f"({n_nan / T.size:.4%}); median nearest = {np.nanmedian(np.nanmin(T, axis=1)):.1f} min")
    LARGE.mkdir(exist_ok=True)
    for arr, tag in ((T, "time_min"), (D, "dist_m")):
        df = pd.DataFrame(arr, index=pd.Index(o_ids, name="OBJECTID"), columns=d_ids.astype(str))
        df.to_parquet(LARGE / f"walk_{name}_{tag}.parquet")
    summary = pd.DataFrame({"OBJECTID": o_ids,
                            f"{name}_nearest_min": np.nanmin(T, axis=1),
                            f"{name}_nearest_id": d_ids[np.nanargmin(np.where(np.isnan(T), np.inf, T), axis=1)],
                            f"{name}_nearest_m": D[np.arange(len(T)), np.nanargmin(np.where(np.isnan(T), np.inf, T), axis=1)]})
    for t in THRESHOLDS_MIN:
        summary[f"{name}_n_within_{t}min"] = (T <= t).sum(axis=1)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="centres,mrt_exits")
    ap.add_argument("--port", type=int, default=5001)
    args = ap.parse_args()
    base = f"http://localhost:{args.port}"
    try:
        requests.get(f"{base}/nearest/v1/foot/103.85,1.29", timeout=5).raise_for_status()
    except Exception as e:
        sys.exit(f"OSRM not reachable on port {args.port}: {e}")

    origins = pyogrio.read_dataframe(GPKG, layer="hdb_points")
    o_xy, o_ids = lonlat(origins), origins["OBJECTID"].to_numpy()
    print(f"{len(origins):,} origins")

    summary = origins[["OBJECTID", "cluster_id", "SUBZONE_C", "SUBZONE_N", "PLN_AREA_N",
                       "total_dwelling_units"]].copy()
    for name in args.sets.split(","):
        summary = summary.merge(build(base, name, origins, o_xy, o_ids), on="OBJECTID", how="left")
    OUT.mkdir(exist_ok=True)
    summary.to_csv(OUT / "hdb_walk_access.csv", index=False)
    print(f"Wrote {OUT / 'hdb_walk_access.csv'} ({len(summary):,} rows)")


if __name__ == "__main__":
    main()
