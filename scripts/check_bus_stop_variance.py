"""
Why bus stops are NOT a covariate: walking time from HDB blocks to the nearest bus stop
has almost no spread, so it cannot explain variation in fees or supply.

Part 1 (no OSRM needed): straight-line distance from every residential block to its
nearest bus stop.
Part 2 (OSRM on port 5001): network walking time for a random sample of blocks
(default 500, seed 4015) to all 5,205 bus stops, and the same for MRT exits for contrast.

Run:  python scripts/check_bus_stop_variance.py [--sample 500] [--port 5001] [--no-osrm]
Decision recorded in docs/decisions.md (prof confirmed 2026-10-30).
"""
import argparse
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import requests

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from build_walk_matrix import CHUNK, DEST_SETS, GPKG, lonlat, osrm_table  # noqa: E402


def q(x):
    x = pd.Series(x).dropna()
    return {"p10": x.quantile(.1), "median": x.median(), "p90": x.quantile(.9),
            "p99": x.quantile(.99), "max": x.max(), "CV": x.std() / x.mean(),
            ">5": (x > 5).mean() * 100, ">10": (x > 10).mean() * 100}


def nearest_min(base, o_xy, d_xy):
    best = np.full(len(o_xy), np.inf)
    for i in range(0, len(o_xy), CHUNK):
        for j in range(0, len(d_xy), CHUNK):
            t = osrm_table(base, o_xy[i:i + CHUNK], d_xy[j:j + CHUNK], "duration") / 60.0
            best[i:i + CHUNK] = np.fmin(best[i:i + CHUNK], np.nanmin(np.where(np.isnan(t), np.inf, t), axis=1))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=500)
    ap.add_argument("--seed", type=int, default=4015)
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--no-osrm", action="store_true")
    a = ap.parse_args()

    blocks = pyogrio.read_dataframe(GPKG, layer="hdb_points").to_crs(3414)
    stops = pyogrio.read_dataframe(DEST_SETS["bus_stops"][0]).to_crs(3414)
    mrt = pyogrio.read_dataframe(DEST_SETS["mrt_exits"][0]).to_crs(3414)

    sl = gpd.sjoin_nearest(blocks[["OBJECTID", "geometry"]], stops[["geometry"]], distance_col="d")
    sl = sl.drop_duplicates("OBJECTID")
    r = q(sl.d)
    print(f"Straight-line to nearest bus stop, all {len(sl):,} blocks (m): "
          f"p10 {r['p10']:.0f} | median {r['median']:.0f} | p90 {r['p90']:.0f} | p99 {r['p99']:.0f} | "
          f"max {r['max']:.0f} | CV {r['CV']:.2f}")
    if a.no_osrm:
        return

    base = f"http://localhost:{a.port}"
    try:
        requests.get(f"{base}/nearest/v1/foot/103.85,1.29", timeout=5).raise_for_status()
    except Exception as e:
        sys.exit(f"OSRM not reachable on port {a.port}: {e}  (use --no-osrm for part 1 only)")

    smp = blocks.sample(a.sample, random_state=a.seed)
    o_xy = lonlat(smp)
    rows = []
    for name, dest in (("bus stop", stops), ("MRT exit", mrt)):
        r = q(nearest_min(base, o_xy, lonlat(dest)))
        rows.append({"nearest": name, **r})
    df = pd.DataFrame(rows).set_index("nearest")
    print(f"\nWalking time (min) to nearest ..., {a.sample}-block random sample (seed {a.seed}):")
    print(df.round(1).to_string())


if __name__ == "__main__":
    main()
