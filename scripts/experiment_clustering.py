"""
Experiment: which distance-based clustering should group HDB blocks into neighbourhoods?

Runs several methods per subzone on residential block centroids (EPSG:3414) and reports,
per configuration: number of clusters, size distribution, cluster diameter, and the
"centroid error" (distance from each block to its cluster centroid, weighted by dwelling
units) -- the error you accept when computing walk times from the cluster centroid.

Output: output/clustering_experiment.csv (one row per config) + printed summary.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
from scipy.spatial.distance import pdist
from sklearn.cluster import DBSCAN, AgglomerativeClustering
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

GPKG = ROOT / "output" / "hdb_blocks.gpkg"
OUT_CSV = ROOT / "output" / "clustering_experiment.csv"

blocks = pyogrio.read_dataframe(GPKG, layer="hdb_blocks")
blocks = blocks[blocks["is_residential"] & blocks["total_dwelling_units"].gt(0)].copy()
blocks["geometry"] = blocks.geometry.centroid
sz = pyogrio.read_dataframe(GPKG, layer="subzones")[["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "geometry"]]
pts = gpd.sjoin(blocks, sz, how="left", predicate="within")
missing = pts["SUBZONE_C"].isna().sum()
if missing:  # centroids on a boundary: snap to nearest subzone
    nn = gpd.sjoin_nearest(pts[pts["SUBZONE_C"].isna()].drop(columns=["index_right","SUBZONE_C","SUBZONE_N","PLN_AREA_N"]), sz, how="left")
    pts.loc[nn.index, ["SUBZONE_C","SUBZONE_N","PLN_AREA_N"]] = nn[["SUBZONE_C","SUBZONE_N","PLN_AREA_N"]].values
print(f"{len(pts)} residential blocks with units; {missing} needed nearest-subzone snap; "
      f"{pts['SUBZONE_C'].nunique()} subzones with HDB")

X_all = np.c_[pts.geometry.x, pts.geometry.y]
w_all = pts["total_dwelling_units"].to_numpy(float)

CONFIGS = []
for eps in (150, 200, 250, 300):
    CONFIGS.append((f"dbscan_{eps}m", "DBSCAN (single-link chaining)", eps,
                    lambda X, e=eps: DBSCAN(eps=e, min_samples=1).fit_predict(X)))
for th in (250, 300, 400, 500):
    CONFIGS.append((f"complete_{th}m", "Agglomerative complete (max diameter)", th,
                    lambda X, t=th: AgglomerativeClustering(n_clusters=None, distance_threshold=t, linkage="complete").fit_predict(X)))
for th in (200, 300, 400):
    CONFIGS.append((f"average_{th}m", "Agglomerative average", th,
                    lambda X, t=th: AgglomerativeClustering(n_clusters=None, distance_threshold=t, linkage="average").fit_predict(X)))


def run(label, fn):
    cid = np.empty(len(pts), dtype=object)
    for code, idx in pts.groupby("SUBZONE_C").indices.items():
        X = X_all[idx]
        lab = fn(X) if len(idx) > 1 else np.zeros(1, int)
        cid[idx] = [f"{code}_{l}" for l in lab]
    return cid


rows, labels = [], {}
for label, family, param, fn in CONFIGS:
    cid = run(label, fn)
    labels[label] = cid
    df = pd.DataFrame({"cid": cid, "x": X_all[:, 0], "y": X_all[:, 1], "w": w_all})
    g = df.groupby("cid")
    sizes = g.size()
    units = g["w"].sum()
    # cluster centroid (unit-weighted) and per-block error
    cx = g.apply(lambda d: np.average(d.x, weights=d.w), include_groups=False)
    cy = g.apply(lambda d: np.average(d.y, weights=d.w), include_groups=False)
    err = np.hypot(df.x - df.cid.map(cx), df.y - df.cid.map(cy))
    diam = g.apply(lambda d: pdist(d[["x", "y"]].to_numpy()).max() if len(d) > 1 else 0.0, include_groups=False)
    rows.append({
        "config": label, "family": family, "param_m": param,
        "n_clusters": len(sizes),
        "singletons": int((sizes == 1).sum()),
        "median_blocks": float(sizes.median()), "max_blocks": int(sizes.max()),
        "median_units": float(units.median()), "max_units": int(units.max()),
        "median_diam_m": float(diam.median()), "p95_diam_m": float(diam.quantile(.95)), "max_diam_m": float(diam.max()),
        "mean_err_m": float(np.average(err, weights=w_all)),
        "p95_err_m": float(np.percentile(err, 95)),
        "share_err_gt300m": float(np.average(err > 300, weights=w_all)),
    })
res = pd.DataFrame(rows)
res.to_csv(OUT_CSV, index=False)
pd.set_option("display.width", 250)
print(res.round(0).to_string(index=False))
