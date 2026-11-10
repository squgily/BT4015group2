"""Shared spatial-weights helper: Queen contiguity (Lecture 8) with islands attached to their
nearest neighbour so every unit has at least one neighbour. Row-standardised.

``rook_with_islands_patched`` (added 2026-11-10 for the 3_07 weights comparison) does the same with
Rook contiguity (shared edges only, no corner-touching neighbours)."""
import numpy as np
from libpysal.weights import KNN, Queen, Rook, W


def _patch_islands(w, gdf):
    """Attach every island to its nearest centroid neighbour (symmetrically) and row-standardise."""
    if w.islands:
        wk = KNN(np.c_[gdf.geometry.centroid.x, gdf.geometry.centroid.y], k=1)
        nb = {k: list(v) for k, v in w.neighbors.items()}
        for i in w.islands:
            j = wk.neighbors[i][0]
            nb[i] = [j]
            nb[j] = nb[j] + [i]
        w = W(nb, silence_warnings=True)
    w.transform = "r"
    return w


def queen_with_islands_patched(gdf):
    w = Queen(list(gdf.geometry), silence_warnings=True)
    return _patch_islands(w, gdf)


def rook_with_islands_patched(gdf):
    w = Rook(list(gdf.geometry), silence_warnings=True)
    return _patch_islands(w, gdf)
