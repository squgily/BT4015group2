"""
BT4015 - what will ECDA's planned centres do? ("will the new centre help, and whom will it attract?")

For each of the 13 centres ECDA lists as upcoming (output/childcare_centres_2026.gpkg, layer "planned",
verified by Jessie), using the same 2SFCA machinery as scripts/pressure_index.py (10-min walk, one unit
per centre, HDB children 0-6 as demand):
  attract  pool_children_0_6   children 0-6 in HDB blocks within 10 min of the planned centre, and its
                               percentile among the pools of the 1,796 existing centres
  improve  pressure of its own subzone before and after adding only that centre (% change), the number
           of blocks and children whose supply ratio rises, and the subzone that gains most
  gap      weak-link subzones (top 15 by pressure, or LISA HH) with no planned centre within 10 min of
           any of their blocks -> what the current pipeline leaves untouched

Inputs   large_data/walk_centres_time_min.parquet, large_data/walk_planned_time_min.parquet
         output/hdb_access_children.csv, output/subzone_pressure.csv, output/weak_links_top15.csv
Outputs  output/planned_centre_impact.csv (one row per planned centre), output/planned_centre_gap.csv
Caveats  capacity unknown (one unit per centre, as everywhere else); demand pool is HDB children only;
         the planned list is ECDA's as of Oct 2026.

Run:  python scripts/planned_centre_impact.py   (after pressure_index.py)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_walk_matrix import load_dest  # noqa: E402
from pressure_index import D0, two_sfca, wmean  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LARGE, OUT = ROOT / "large_data", ROOT / "output"


def subzone_pressure(A, blk):
    """children-weighted supply ratio per subzone -> children per reachable centre."""
    g = pd.DataFrame({"A": A.reindex(blk.index), "w": blk["child_0_6"], "sz": blk["SUBZONE_C"]})
    m = g.groupby("sz").apply(lambda d: wmean(d["A"], d["w"]))
    return 1 / m.where(m > 0)


def main():
    T = pd.read_parquet(LARGE / "walk_centres_time_min.parquet")
    TP = pd.read_parquet(LARGE / "walk_planned_time_min.parquet").reindex(T.index)
    planned, pids = load_dest("planned")
    planned = planned.set_index(pd.Index(pids, name="tp_code"))
    blk = pd.read_csv(OUT / "hdb_access_children.csv").set_index("OBJECTID").reindex(T.index)
    demand = blk["child_0_6"]
    names = pyogrio.read_dataframe(OUT / "hdb_blocks.gpkg", layer="subzones", read_geometry=False,
                                   columns=["SUBZONE_C", "SUBZONE_N"]).set_index("SUBZONE_C")["SUBZONE_N"]

    A0, R0, pool0 = two_sfca(T, demand, D0)
    P0 = subzone_pressure(A0, blk)
    existing_pools = pool0[pool0 > 0]
    print(f"existing centres: pool within {D0} min median {existing_pools.median():,.0f} children 0-6, "
          f"p90 {existing_pools.quantile(.9):,.0f}, max {existing_pools.max():,.0f}")

    rows = []
    for k in pids:
        Tk = pd.concat([T, TP[[k]]], axis=1)
        A1, R1, pool1 = two_sfca(Tk, demand, D0)
        P1 = subzone_pressure(A1, blk)
        own = planned.loc[k, "SUBZONE_C"]
        gain = (A1 - A0)
        benefit = gain > 1e-12
        dP = (P1 / P0 - 1) * 100
        best = dP.idxmin() if dP.notna().any() else None
        rows.append({
            "tp_code": k, "service_model": planned.loc[k, "service_model"],
            "centre_name": planned.loc[k, "centre_name"] if str(planned.loc[k, "centre_name"]).lower() not in ("na", "nan", "")
            else f"(unnamed ECDA entry, see evidence: {str(planned.loc[k, 'evidence'])[:50]})",
            "SUBZONE_N": planned.loc[k, "SUBZONE_N"], "PLN_AREA_N": planned.loc[k, "PLN_AREA_N"],
            "expected_opening": planned.loc[k, "expected_opening"],
            "pool_children_0_6": float(pool1[k]),
            "pool_percentile_vs_existing": float((existing_pools < pool1[k]).mean() * 100),
            "own_subzone_pressure_before": float(P0.get(own, np.nan)), "own_subzone_pressure_after": float(P1.get(own, np.nan)),
            "own_subzone_pct_change": float(dP.get(own, np.nan)),
            "blocks_benefiting": int(benefit.sum()), "children_benefiting": float(demand[benefit].sum()),
            "subzones_affected": int((dP < -0.5).sum()),
            "most_improved_subzone": names.get(best, best) if best is not None else None,
            "most_improved_pct_change": float(dP.min()) if best is not None else np.nan,
        })
    imp = pd.DataFrame(rows).sort_values("own_subzone_pct_change")
    imp.to_csv(OUT / "planned_centre_impact.csv", index=False)
    print("\nPlanned centres, sorted by relief in their own subzone:")
    print(imp[["centre_name", "SUBZONE_N", "expected_opening", "pool_children_0_6", "pool_percentile_vs_existing",
               "own_subzone_pressure_before", "own_subzone_pct_change", "children_benefiting", "most_improved_subzone",
               "most_improved_pct_change"]].round(1).to_string(index=False))

    # ---- gap: weak links with no planned centre in reach
    top = pd.read_csv(OUT / "weak_links_top15.csv")
    sp = pd.read_csv(OUT / "subzone_pressure.csv")
    weak = set(top["SUBZONE_C"]) | set(sp.loc[sp["lisa_q"].eq("HH"), "SUBZONE_C"])
    reach = (TP <= D0).any(axis=1)                      # block has a planned centre within D0
    per_sz = pd.DataFrame({"sz": blk["SUBZONE_C"], "w": demand, "reach": reach.reindex(blk.index).fillna(False)})
    cover = per_sz.groupby("sz").apply(lambda d: d.loc[d["reach"], "w"].sum() / d["w"].sum() if d["w"].sum() else np.nan)
    gap = sp[sp["SUBZONE_C"].isin(weak)][["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "children_0_6", "pressure_base",
                                          "lisa_q", "planned_centres_n"]].copy()
    gap["share_children_near_planned"] = gap["SUBZONE_C"].map(cover).fillna(0)
    gap = gap.sort_values("pressure_base", ascending=False)
    gap.to_csv(OUT / "planned_centre_gap.csv", index=False)
    untouched = gap[gap["share_children_near_planned"] < 0.05]
    print(f"\nWeak links (top 15 or HH): {len(gap)}; with no planned centre within {D0} min of (almost) any child: "
          f"{len(untouched)} -> " + ", ".join(untouched["SUBZONE_N"]))


if __name__ == "__main__":
    main()
