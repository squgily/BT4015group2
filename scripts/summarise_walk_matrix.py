"""
Rebuild output/hdb_walk_access.csv from the parquet matrices in large_data/ without
re-querying OSRM. Picks up whichever destination sets exist (walk_<set>_time_min.parquet
and walk_<set>_dist_m.parquet).

Run:  python scripts/summarise_walk_matrix.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio

ROOT = Path(__file__).resolve().parent.parent
GPKG = ROOT / "output" / "hdb_blocks.gpkg"
LARGE = ROOT / "large_data"
OUT = ROOT / "output" / "hdb_walk_access.csv"
THRESHOLDS_MIN = (10, 15)


def summarise(name):
    T = pd.read_parquet(LARGE / f"walk_{name}_time_min.parquet")
    D = pd.read_parquet(LARGE / f"walk_{name}_dist_m.parquet")
    t = T.to_numpy(float)
    safe = np.where(np.isnan(t), np.inf, t)
    j = safe.argmin(axis=1)
    s = pd.DataFrame({"OBJECTID": T.index.to_numpy(),
                      f"{name}_nearest_min": safe[np.arange(len(t)), j],
                      f"{name}_nearest_id": T.columns.to_numpy()[j],
                      f"{name}_nearest_m": D.to_numpy(float)[np.arange(len(t)), j]})
    for th in THRESHOLDS_MIN:
        s[f"{name}_n_within_{th}min"] = (t <= th).sum(axis=1)
    unreach = np.isinf(s[f"{name}_nearest_min"]).sum()
    print(f"{name}: {T.shape[0]:,} x {T.shape[1]:,}; nan cells {int(np.isnan(t).sum()):,}; "
          f"origins with no reachable destination {unreach}; "
          f"median nearest {np.nanmedian(t.min(axis=1, initial=np.inf, where=~np.isnan(t))):.1f} min")
    return s


def main():
    origins = pyogrio.read_dataframe(GPKG, layer="hdb_points", read_geometry=False)
    summary = origins[["OBJECTID", "cluster_id", "SUBZONE_C", "SUBZONE_N", "PLN_AREA_N",
                       "total_dwelling_units"]].copy()
    sets = sorted({p.name.split("_time_min")[0].replace("walk_", "")
                   for p in LARGE.glob("walk_*_time_min.parquet")
                   if (LARGE / p.name.replace("_time_min", "_dist_m")).exists()})
    if not sets:
        raise SystemExit("no complete parquet matrices found in large_data/")
    for name in sets:
        summary = summary.merge(summarise(name), on="OBJECTID", how="left")
    summary.to_csv(OUT, index=False)
    print(f"Wrote {OUT} ({len(summary):,} rows, sets: {', '.join(sets)})")


if __name__ == "__main__":
    main()
