"""
Sensitivity of the pressure-index LISA (scripts/pressure_index.py) to the minimum-children cut-off.
Re-runs global and local Moran's I on log pressure_base for HDB subzones with >= 0 / 50 / 100 / 200
children 0-6 and reports the high-high set each time. Also lists the Queen-contiguity islands.

Run:  python scripts/lisa_threshold_sensitivity.py   (after pressure_index.py)
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
from libpysal.weights import Queen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spatial_weights import queen_with_islands_patched  # noqa: E402
from esda.moran import Moran, Moran_Local  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
GPKG = ROOT / "output" / "hdb_blocks.gpkg"
OUT = ROOT / "output" / "lisa_threshold_sensitivity.csv"
PERMS, SEED = 9999, 4015
LAB = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}


def main():
    sp = pyogrio.read_dataframe(GPKG, layer="subzone_pressure")
    h_all = sp[sp["has_hdb"] & sp["pressure_base"].notna()]
    rows = []
    for th in (0, 50, 100, 200):
        g = h_all[h_all["children_0_6"] >= th].reset_index(drop=True)
        raw = Queen(list(g.geometry), silence_warnings=True)
        islands = ", ".join(g.loc[raw.islands, "SUBZONE_N"].str.title())
        w = queen_with_islands_patched(g)
        y = np.log(g["pressure_base"].to_numpy(float))
        np.random.seed(SEED)
        mi = Moran(y, w, permutations=PERMS)
        loc = Moran_Local(y, w, permutations=PERMS, seed=SEED)
        q = [LAB[a] if p < 0.05 else "ns" for a, p in zip(loc.q, loc.p_sim)]
        hh = sorted(g["SUBZONE_N"][[x == "HH" for x in q]].str.title())
        counts = pd.Series(q).value_counts().to_dict()
        rows.append({"min_children_0_6": th, "n_subzones": len(g), "islands_patched": islands,
                     "morans_I": round(mi.I, 3), "p_sim": mi.p_sim, "n_HH": len(hh), "n_LL": counts.get("LL", 0),
                     "n_HL": counts.get("HL", 0), "n_LH": counts.get("LH", 0), "HH_subzones": "; ".join(hh)})
        print(f">= {th:3d} children: n={len(g):3d} | islands: {islands or 'none'} | I={mi.I:+.3f} p={mi.p_sim:.4f} "
              f"| HH={len(hh)}: {', '.join(hh)}")
    pd.DataFrame(rows).to_csv(OUT, index=False)
    core = set.intersection(*[set(r["HH_subzones"].split("; ")) for r in rows if r["min_children_0_6"] >= 50])
    print(f"\nHH at every threshold from 50 to 200 ({len(core)}): {', '.join(sorted(core))}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
