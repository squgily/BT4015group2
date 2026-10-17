"""
BT4015 preprocessing: load the URA Master Plan 2019 Subzone Boundary (No Sea) into the
working GeoPackage as layer "subzones" in EPSG:3414, with area in km2.

Source: data/MasterPlanSubZones_2019.geojson (data.gov.sg d_8594ae9ff96d0c708bc2af633048edfb).
"""
import pyogrio
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

SRC = ROOT / "data" / "MasterPlanSubZones_2019.geojson"
OUT_GPKG = ROOT / "output" / "hdb_blocks.gpkg"
OUT_LAYER = "subzones"
CRS_OUT = "EPSG:3414"

KEEP = ["SUBZONE_NO", "SUBZONE_N", "SUBZONE_C", "CA_IND", "PLN_AREA_N", "PLN_AREA_C",
        "REGION_N", "REGION_C", "geometry"]


def main():
    sz = pyogrio.read_dataframe(SRC)[KEEP].to_crs(CRS_OUT)
    sz["area_km2"] = sz.geometry.area / 1e6
    assert sz["SUBZONE_C"].is_unique, "SUBZONE_C must be unique"
    sz.to_file(OUT_GPKG, layer=OUT_LAYER, driver="GPKG")
    print(f"Wrote layer '{OUT_LAYER}': {len(sz)} subzones, "
          f"{sz['PLN_AREA_N'].nunique()} planning areas, {sz['REGION_N'].nunique()} regions, "
          f"total {sz['area_km2'].sum():.1f} km2 -> {OUT_GPKG}")


if __name__ == "__main__":
    main()
