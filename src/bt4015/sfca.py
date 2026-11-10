"""Two-step floating catchment (2SFCA) helpers shared by 3_07 (pressure index) and 3_08 (planned
centres).  Minh's code from ``scripts/pressure_index.py`` and the ``load_dest`` helper of
``scripts/build_walk_matrix.py``; logic unchanged.

Pressure index (decisions log 2026-11-02):
  step 1  for each centre j:  pool_j = sum of children 0-6 in HDB blocks within d0 minutes,
          R_j = 1 / pool_j   (every centre is one unit; capacity is not used)
  step 2  for each block i:   A_i = sum of R_j over centres within d0  (centres per child)
          pressure_i = 1 / A_i = children per reachable centre
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio


def two_sfca(T: pd.DataFrame, demand: pd.Series, d0: float):
    """Binary-catchment 2SFCA.

    ``T``: blocks x centres walking minutes (NaN = unreachable); ``demand``: children per block,
    indexed like ``T``; ``d0``: catchment in minutes.  Returns three Series: A (centres per child,
    per block), R (supply ratio per centre) and pool (children within d0, per centre).
    A block with no centre within d0 gets A = 0; a centre with no block in reach gets R = 0.
    """
    M = T.to_numpy(float) <= d0                       # NaN compares False
    P = demand.reindex(T.index).fillna(0).to_numpy(float)
    pool = M.T @ P
    R = np.divide(1.0, pool, out=np.zeros_like(pool), where=pool > 0)
    A = M @ R
    return (pd.Series(A, index=T.index), pd.Series(R, index=T.columns), pd.Series(pool, index=T.columns))


def wmean(v, w):
    """Weighted mean of v with weights w, ignoring NaN values and zero weights (NaN if none)."""
    v, w = np.asarray(v, float), np.asarray(w, float)
    ok = ~np.isnan(v) & (w > 0)
    return np.average(v[ok], weights=w[ok]) if ok.any() else np.nan


def load_centres(gpkg: Path, layer: str = "centres", matrix_columns=None):
    """Read a centre layer from the canonical GeoPackage and build its matrix id.

    For layer ``centres`` the id is ``centre_code`` where present, else ``tp_code`` (one verified
    addition has no centre code); for layer ``planned`` the id is ``tp_code``.  Asserts the ids
    are unique and, if ``matrix_columns`` is given, that they are exactly the walk-matrix
    columns.  Returns (GeoDataFrame, ids as a str array in layer order).
    """
    dest = pyogrio.read_dataframe(gpkg, layer=layer)
    if layer == "centres":
        dest["centre_id"] = dest["centre_code"].where(
            dest["centre_code"].notna() & (dest["centre_code"] != ""), dest["tp_code"]
        )
        id_col = "centre_id"
    else:
        id_col = "tp_code"
    ids = dest[id_col].astype(str).to_numpy()
    assert len(set(ids)) == len(ids), f"{layer}: destination ids are not unique"
    if matrix_columns is not None:
        assert set(matrix_columns) == set(ids), f"walk matrix columns do not match layer {layer}"
    return dest, ids
