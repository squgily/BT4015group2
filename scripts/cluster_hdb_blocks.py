"""
BT4015 preprocessing steps 2-4: residential block centroids -> subzone tag -> neighbourhood
clusters (complete-linkage agglomerative, 300 m max diameter, run within each subzone).
See docs/clustering_decision.md for why.

Writes three layers to output/hdb_blocks.gpkg (run scripts/load_subzones.py first) (all EPSG:3414):
  hdb_points         one point per residential block: subzone, cluster_id, color_idx
  hdb_clusters       one point per cluster (dwelling-unit-weighted centroid): n_blocks,
                     dwelling_units, gfa_m2, diameter_m, color_idx
  hdb_cluster_hulls  convex hull polygon per cluster (small buffer so 1-2 block clusters show)

color_idx (0-7) is a greedy graph colouring so neighbouring clusters never share a colour:
in QGIS use Categorized symbology on color_idx with 8 classes.
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
from scipy.spatial import cKDTree
from scipy.spatial.distance import pdist
from sklearn.cluster import AgglomerativeClustering
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

GPKG = ROOT / "output" / "hdb_blocks.gpkg"
DIAMETER_M = 300          # decided 2026-10-16; 400 is the fallback
HULL_BUFFER_M = 15        # visual only, so singletons / pairs render as a shape
POINT_COLS = ["OBJECTID", "BLK_NO", "decoded_street", "POSTAL_COD", "year_completed",
              "max_floor_lvl", "total_dwelling_units", "footprint_m2", "gfa_m2",
              "1room_sold", "2room_sold", "3room_sold", "4room_sold", "5room_sold",
              "exec_sold", "1room_rental", "2room_rental", "3room_rental"]


def colour_clusters(centroids_xy, k_neighbours=8, n_colours=8):
    tree = cKDTree(centroids_xy)
    nb = tree.query(centroids_xy, k=min(k_neighbours + 1, len(centroids_xy)))[1]
    col = np.full(len(centroids_xy), -1)
    for i in range(len(centroids_xy)):
        used = {col[j] for j in nb[i][1:] if col[j] >= 0}
        col[i] = next((c for c in range(n_colours) if c not in used), i % n_colours)
    return col


def main():
    blocks = pyogrio.read_dataframe(GPKG, layer="hdb_blocks")
    blocks = blocks[blocks["is_residential"] & blocks["total_dwelling_units"].gt(0)].copy()
    pts = blocks[POINT_COLS + ["geometry"]].copy()
    pts["geometry"] = blocks.geometry.centroid

    sz = pyogrio.read_dataframe(GPKG, layer="subzones")[["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "geometry"]]
    pts = gpd.sjoin(pts, sz, how="left", predicate="within").drop(columns="index_right")
    miss = pts["SUBZONE_C"].isna()
    if miss.any():
        near = gpd.sjoin_nearest(pts.loc[miss, ["geometry"]], sz, how="left")
        pts.loc[miss, ["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N"]] = near[["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N"]].values
    print(f"Step 2-3: {len(pts)} residential block centroids tagged to {pts['SUBZONE_C'].nunique()} subzones "
          f"({int(miss.sum())} snapped to nearest subzone)")

    xy = np.c_[pts.geometry.x, pts.geometry.y]
    cid = np.empty(len(pts), dtype=object)
    for code, idx in pts.groupby("SUBZONE_C").indices.items():
        if len(idx) == 1:
            lab = np.zeros(1, int)
        else:
            lab = AgglomerativeClustering(n_clusters=None, distance_threshold=DIAMETER_M,
                                          linkage="complete").fit_predict(xy[idx])
        cid[idx] = [f"{code}_{l:03d}" for l in lab]
    pts["cluster_id"] = cid

    w = pts["total_dwelling_units"].to_numpy(float)
    df = pd.DataFrame({"cluster_id": cid, "x": xy[:, 0], "y": xy[:, 1], "w": w,
                       "gfa": pts["gfa_m2"].to_numpy(), "SUBZONE_C": pts["SUBZONE_C"].values,
                       "SUBZONE_N": pts["SUBZONE_N"].values, "PLN_AREA_N": pts["PLN_AREA_N"].values})
    g = df.groupby("cluster_id")
    cl = pd.DataFrame({
        "SUBZONE_C": g["SUBZONE_C"].first(), "SUBZONE_N": g["SUBZONE_N"].first(),
        "PLN_AREA_N": g["PLN_AREA_N"].first(),
        "n_blocks": g.size(), "dwelling_units": g["w"].sum().astype(int), "gfa_m2": g["gfa"].sum(),
        "cx": g.apply(lambda d: np.average(d["x"], weights=d["w"]), include_groups=False),
        "cy": g.apply(lambda d: np.average(d["y"], weights=d["w"]), include_groups=False),
        "diameter_m": g.apply(lambda d: pdist(d[["x", "y"]].to_numpy()).max() if len(d) > 1 else 0.0,
                              include_groups=False),
    }).reset_index()
    assert cl["diameter_m"].max() <= DIAMETER_M + 1e-6
    cl["color_idx"] = colour_clusters(cl[["cx", "cy"]].to_numpy())
    pts["color_idx"] = pts["cluster_id"].map(cl.set_index("cluster_id")["color_idx"])

    clusters = gpd.GeoDataFrame(cl.drop(columns=["cx", "cy"]),
                                geometry=gpd.points_from_xy(cl["cx"], cl["cy"]), crs=pts.crs)
    hulls = pts.dissolve(by="cluster_id")[["geometry"]].convex_hull.buffer(HULL_BUFFER_M)
    hulls = gpd.GeoDataFrame(cl.set_index("cluster_id").drop(columns=["cx", "cy"]),
                             geometry=hulls, crs=pts.crs).reset_index()

    pts.to_file(GPKG, layer="hdb_points", driver="GPKG")
    clusters.to_file(GPKG, layer="hdb_clusters", driver="GPKG")
    hulls.to_file(GPKG, layer="hdb_cluster_hulls", driver="GPKG")
    s = cl["n_blocks"]
    print(f"Step 4: {len(cl)} clusters (max diameter {DIAMETER_M} m); blocks per cluster "
          f"median {s.median():.0f}, max {s.max()}, singletons {(s == 1).sum()}; "
          f"median {cl['dwelling_units'].median():.0f} flats per cluster")
    print("Wrote layers hdb_points, hdb_clusters, hdb_cluster_hulls")


if __name__ == "__main__":
    main()
