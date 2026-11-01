"""Shared spatial-weights helper: Queen contiguity (Lecture 8) with islands attached to their
nearest neighbour so every unit has at least one neighbour. Row-standardised."""
import numpy as np
from libpysal.weights import KNN, Queen, W


def queen_with_islands_patched(gdf):
    w = Queen(list(gdf.geometry), silence_warnings=True)
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
