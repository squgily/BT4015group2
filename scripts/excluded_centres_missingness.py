"""
Spatial missingness of the 40 possibly missing centres (qa_status 'possible_missing' in
output/excluded_centres_2026.csv) against the 1,795 retained centres.

Null hypothesis (random labelling): the 40 missing records are a random draw from all
1,835 observed centre locations. 9,999 label permutations, seed 4015. Statistics:
  G_pa, G_sz    likelihood-ratio G = 2 sum o ln(o/e) of missing counts by planning area /
                subzone (expected = area share of all centres x 40). Concentration by area.
  T_k           Cuzick-Edwards: pairs (missing i, one of i's k nearest centres) where the
                neighbour is also missing, k = 1, 5. Point-level clustering.
  mean_nn       mean nearest-neighbour distance among the 40 (small = clustered).
Tengah: exact hypergeometric P(X >= observed) for the planning-area count.
Clark-Evans R for the 40 against CSR inside the 2019 subzone boundary (999 simulations),
reported for reference only: centres are not uniform over Singapore, so CSR overstates
clustering. The retained centres' R is printed for comparison.

Output: output/excluded_centres_missingness_by_area.csv; statistics printed.
Run:    python scripts/excluded_centres_missingness.py
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import hypergeom

ROOT = Path(__file__).resolve().parent.parent
LAYER = ROOT / "output" / "childcare_centres_2026.gpkg"
EXCLUDED = ROOT / "output" / "excluded_centres_2026.csv"
SUBZONES = ROOT / "data" / "MasterPlanSubZones_2019.geojson"
OUT = ROOT / "output" / "excluded_centres_missingness_by_area.csv"
PERMS, CSR_SIMS, SEED, KS = 9999, 999, 4015, (1, 5)


def g_stat(counts, expected):
    o = counts[counts > 0]
    return 2 * np.sum(o * np.log(o / expected[counts > 0]))


def mean_nn(xy):
    d, _ = cKDTree(xy).query(xy, k=2)
    return d[:, 1].mean()


def clark_evans(xy, area):
    return mean_nn(xy) / (0.5 / np.sqrt(len(xy) / area))


def main():
    rng = np.random.default_rng(SEED)
    sz = gpd.read_file(SUBZONES).to_crs(3414)[["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "geometry"]]
    kept = gpd.read_file(LAYER, layer="centres")
    kept = kept.loc[kept["record_source"] == "ecda_listed", ["geometry"]]
    ex = pd.read_csv(EXCLUDED, dtype=str)
    ex = ex[ex["qa_status"] == "possible_missing"]
    miss = gpd.GeoDataFrame(geometry=gpd.points_from_xy(ex["lon"].astype(float),
                                                        ex["lat"].astype(float)), crs=4326).to_crs(3414)
    pts = pd.concat([kept.assign(missing=0), miss.assign(missing=1)], ignore_index=True)
    pts = gpd.sjoin(gpd.GeoDataFrame(pts, crs=3414), sz, how="left", predicate="within")
    assert pts["SUBZONE_C"].notna().all() and len(pts) == len(kept) + len(miss)
    lab = pts["missing"].to_numpy()
    n, m = len(lab), lab.sum()
    xy = np.c_[pts.geometry.x, pts.geometry.y]
    print(f"{n} centre locations, {m} missing ({100 * m / n:.2f}%), {len(kept)} retained")

    # Rates by area
    rows = []
    for level, col in [("planning_area", "PLN_AREA_N"), ("subzone", "SUBZONE_N")]:
        t = pts.groupby(col)["missing"].agg(total="size", missing="sum").reset_index()
        t["retained"] = t["total"] - t["missing"]
        t["missing_rate_pct"] = 100 * t["missing"] / t["total"]
        t["expected_missing"] = t["total"] * m / n
        rows.append(t.rename(columns={col: "area"}).assign(level=level))
    rates = pd.concat(rows)[["level", "area", "retained", "missing", "total",
                            "missing_rate_pct", "expected_missing"]]
    rates.sort_values(["level", "missing_rate_pct"], ascending=[True, False]).to_csv(OUT, index=False)

    # Precomputed structures for the permutations
    codes = {c: pd.factorize(pts[c])[0] for c in ["PLN_AREA_N", "SUBZONE_N"]}
    exp = {c: np.bincount(codes[c]) * m / n for c in codes}
    _, knn = cKDTree(xy).query(xy, k=max(KS) + 1)
    knn = knn[:, 1:]

    def stats(l):
        idx = np.flatnonzero(l)
        out = {f"G_{'pa' if c == 'PLN_AREA_N' else 'sz'}":
               g_stat(np.bincount(codes[c][idx], minlength=len(exp[c])), exp[c]) for c in codes}
        for k in KS:
            out[f"T_{k}"] = l[knn[idx, :k]].sum()
        out["mean_nn"] = mean_nn(xy[idx])
        return out

    obs = stats(lab)
    sims = pd.DataFrame([stats(rng.permutation(lab)) for _ in range(PERMS)])
    print(f"\nRandom labelling, {PERMS} permutations (pseudo p, one-sided towards clustering)")
    for s, v in obs.items():
        more = (sims[s] <= v) if s == "mean_nn" else (sims[s] >= v)
        p = (more.sum() + 1) / (PERMS + 1)
        print(f"  {s:8s} observed {v:10.2f}   null mean {sims[s].mean():10.2f}   "
              f"null 95th/5th {sims[s].quantile(0.05 if s == 'mean_nn' else 0.95):10.2f}   p = {p:.4f}")

    # Tengah
    t = rates[(rates["level"] == "planning_area") & (rates["area"] == "TENGAH")].iloc[0]
    p_t = hypergeom.sf(t["missing"] - 1, n, m, t["total"])
    print(f"\nTengah: {t['missing']} of {t['total']} missing ({t['missing_rate_pct']:.1f}%) vs "
          f"{100 * m / n:.2f}% overall; expected {t['expected_missing']:.2f}; "
          f"rate ratio {t['missing_rate_pct'] / (100 * m / n):.1f}; hypergeometric P(X>={t['missing']}) = {p_t:.4f}; "
          f"Bonferroni over {rates['level'].eq('planning_area').sum()} planning areas = "
          f"{min(1, p_t * rates['level'].eq('planning_area').sum()):.3f}")
    keep = (pts["PLN_AREA_N"] != "TENGAH").to_numpy()
    c, l = pd.factorize(pts.loc[keep, "PLN_AREA_N"])[0], lab[keep]
    e = np.bincount(c) * l.sum() / len(l)
    g0 = g_stat(np.bincount(c[l == 1], minlength=len(e)), e)
    gs = np.array([g_stat(np.bincount(c[pl == 1], minlength=len(e)), e)
                   for pl in (rng.permutation(l) for _ in range(PERMS))])
    print(f"G_pa without Tengah: observed {g0:.2f}, null mean {gs.mean():.2f}, "
          f"p = {((gs >= g0).sum() + 1) / (PERMS + 1):.4f}")

    # Clark-Evans against CSR in the land boundary (reference only)
    land = sz.geometry.union_all()
    minx, miny, maxx, maxy = land.bounds
    area = land.area

    def csr(k):
        out = np.empty((0, 2))
        while len(out) < k:
            c = rng.uniform([minx, miny], [maxx, maxy], size=(4 * k, 2))
            out = np.vstack([out, c[gpd.points_from_xy(c[:, 0], c[:, 1]).within(land)]])
        return out[:k]

    r_obs = clark_evans(xy[lab == 1], area)
    r_sim = np.array([clark_evans(csr(m), area) for _ in range(CSR_SIMS)])
    p_csr = ((r_sim <= r_obs).sum() + 1) / (CSR_SIMS + 1)
    print(f"\nClark-Evans vs CSR in subzone boundary ({area / 1e6:.0f} km2): R(missing) = {r_obs:.3f}, "
          f"CSR mean {r_sim.mean():.3f}, p = {p_csr:.4f}; "
          f"R(retained) = {clark_evans(xy[lab == 0], area):.3f}")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
