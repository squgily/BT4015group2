"""
H-c: do subzones with many young children AND low accessibility form significant spatial clusters?

Bivariate Moran's I / local bivariate LISA (esda) on output/subzone_stats (gpkg layer),
HDB subzones with >= 100 children 0-6, Queen contiguity (islands attached to nearest neighbour),
9,999 permutations. Demand = children 0-6 (0-4 + per-subzone share of 5-9; see build_subzone_stats.py).
Demand x = child density; access y = child-weighted walk time to nearest
centre (H-c quadrant = HH) and log centres per 1,000 children 0-6 (H-c quadrant = HL).
This is the record of the rejected proposal-form H-c; the reframed analysis is pressure_index.py.

Output: output/subzone_lisa_hc.csv (quadrant label + pseudo p per subzone, both specifications).
Requires: pip install libpysal esda
"""
import warnings
from pathlib import Path

import sys
import numpy as np
import pandas as pd
import pyogrio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spatial_weights import queen_with_islands_patched
from esda.moran import Moran, Moran_BV, Moran_Local_BV

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
GPKG = ROOT / "output" / "hdb_blocks.gpkg"
OUT = ROOT / "output" / "subzone_lisa_hc.csv"
MIN_CHILDREN, PERMS, SEED = 100, 9999, 4015
LAB = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}


def main():
    np.random.seed(SEED)
    s = pyogrio.read_dataframe(GPKG, layer="subzone_stats")
    h = s[s["has_hdb"] & (s["children_0_6"] >= MIN_CHILDREN)].reset_index(drop=True)
    w = queen_with_islands_patched(h)
    print(f"{len(h)} HDB subzones with >= {MIN_CHILDREN} children; Queen contiguity")

    x = h["child_density_0_6_km2"].to_numpy(float)
    specs = {"walk": ("walk_nearest_min_cw", h["walk_nearest_min_cw"].to_numpy(float), "HH"),
             "sup": ("log centres per 1,000 children", np.log1p(h["centres_per_1000_children_0_6"].to_numpy(float)), "HL")}
    for key, (name, y, bad) in specs.items():
        g = Moran_BV(x, y, w, permutations=PERMS)
        loc = Moran_Local_BV(x, y, w, permutations=PERMS)
        sig = loc.p_sim < 0.05
        h[f"bv_{key}_q"] = [LAB[q] if sg else "ns" for q, sg in zip(loc.q, sig)]
        h[f"bv_{key}_p"] = loc.p_sim
        counts = pd.Series([LAB[q] for q in loc.q[sig]]).value_counts().to_dict()
        print(f"child density vs {name}: bivariate I = {g.I:+.3f}, p = {g.p_sim:.4f}; "
              f"H-c quadrant {bad}: {counts.get(bad, 0)} subzones; all significant: {counts}")
        print(h.loc[h[f"bv_{key}_q"] == bad, ["SUBZONE_N", "PLN_AREA_N", "children_0_6",
                    "walk_nearest_min_cw", "centres_per_1000_children_0_6", f"bv_{key}_p"]].round(2).to_string(index=False))
    for n, v in (("child density", x), ("walk time", specs["walk"][1]), ("log supply", specs["sup"][1])):
        m = Moran(v, w, permutations=PERMS)
        print(f"univariate Moran's I, {n}: {m.I:+.3f} (p = {m.p_sim:.4f})")
    print("Pearson r, child density vs log centres per 1,000 children:",
          round(np.corrcoef(x, specs["sup"][1])[0, 1], 3))
    h.drop(columns="geometry").to_csv(OUT, index=False)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
