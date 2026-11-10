"""Walking-time helpers for the local OSRM server (Minh's ``scripts/build_walk_matrix.py``, moved
here 2026-11-10 so notebooks 1_07 and the bus-stop check can import them; logic unchanged).

The server is OSRM with the foot profile on a Singapore clip of the Geofabrik extract, started
with ``osrm-routed --algorithm mld --max-table-size 10000 -p 5001 large_data/singapore.osrm``
(see the README). Matrices are fetched from its ``/table`` endpoint in ``CHUNK`` x ``CHUNK``
blocks, labelled by origin OBJECTID and destination id, never by row position.
"""
import time

import numpy as np
import pyogrio
import requests

from bt4015.paths import DATA, OUT

CHUNK = 100               # origins and destinations per /table call (server max-table-size is 10,000 cells)
THRESHOLDS_MIN = (10, 15)  # walk-time cut-offs for the "centres within N minutes" counts

# name -> (path, id column, layer). "centres" is the canonical layer (Jessie, 1,796 centres, Oct 2026);
# one verified addition has no centre_code, so its matrix id is centre_code with tp_code as fallback.
DEST_SETS = {
    "centres": (OUT / "childcare_centres_2026.gpkg", "centre_id", "centres"),
    "planned": (OUT / "childcare_centres_2026.gpkg", "tp_code", "planned"),  # 13 upcoming ECDA centres
    "centres2021": (DATA / "ChildCareServices_2021.geojson", "OBJECTID", None),  # legacy, comparison only
    "mrt_exits": (DATA / "MRTStationExits_2026.geojson", "OBJECTID", None),
    "bus_stops": (DATA / "BusStops_2026.geojson", "OBJECTID_1", None),  # not used: see docs/decisions.md
}


def osrm_reachable(base, timeout=5):
    """True when an OSRM server answers a /nearest probe at ``base`` (e.g. http://localhost:5001)."""
    try:
        requests.get(f"{base}/nearest/v1/foot/103.85,1.29", timeout=timeout).raise_for_status()
        return True
    except Exception:
        return False


def load_dest(name):
    """Destination GeoDataFrame and its id array for a ``DEST_SETS`` entry.

    For "centres" the id is ``centre_code`` where present, otherwise ``tp_code``. Asserts that
    the ids are unique, because they become the matrix column labels.
    """
    path, id_col, layer = DEST_SETS[name]
    dest = pyogrio.read_dataframe(path, layer=layer) if layer else pyogrio.read_dataframe(path)
    if id_col == "centre_id":
        dest["centre_id"] = dest["centre_code"].where(dest["centre_code"].notna() & (dest["centre_code"] != ""),
                                                      dest["tp_code"])
    ids = dest[id_col].astype(str).to_numpy()
    assert len(set(ids)) == len(ids), f"{name}: destination ids are not unique"
    return dest, ids


def lonlat(gdf):
    """(n, 2) array of lon/lat in WGS 84; polygons are reduced to their centroid."""
    g = gdf.to_crs(4326).geometry
    g = g.centroid if (g.geom_type != "Point").any() else g
    return np.c_[g.x.to_numpy(), g.y.to_numpy()]


def osrm_table(base, src_xy, dst_xy, annotation, retries=3):
    """One /table call: ``annotation`` is "duration" (seconds) or "distance" (metres).

    Returns a (len(src_xy), len(dst_xy)) float array with NaN for unreachable pairs. Retries
    with a growing pause, then raises so a partial matrix is never written silently.
    """
    coords = ";".join(f"{x:.6f},{y:.6f}" for x, y in np.vstack([src_xy, dst_xy]))
    n = len(src_xy)
    params = {
        "sources": ";".join(map(str, range(n))),
        "destinations": ";".join(map(str, range(n, n + len(dst_xy)))),
        "annotations": annotation,
    }
    for attempt in range(retries):
        try:
            r = requests.get(f"{base}/table/v1/foot/{coords}", params=params, timeout=120)
            if r.status_code == 200:
                data = r.json()[annotation + "s"]
                return np.array([[np.nan if v is None else v for v in row] for row in data], dtype=float)
            msg = r.text[:200]
        except requests.RequestException as e:
            msg = str(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"OSRM table request failed after {retries} tries: {msg}")
