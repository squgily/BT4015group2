"""
Status of all 80 ECDA rows dropped from the centre layer (centre_code 'na'), from the
evidence gathered by hand on 2026-11-01. The 40 possibly missing centres (qa_status
'possible_missing' in output/excluded_centres_2026.csv) were each checked; the 35
duplicates and 5 unlocated records keep their QA status unless ECDA lists them as upcoming.

status:
  planned               on ECDA's upcoming-centres list, so not operating at 30 Sep 2026
  duplicate             same block/unit, same named HDB project, or a stated extension of a
                        centre already in the 2026 layer
  operational_absent    operating per the operator's own centre page, not in the 2026 layer
  unverified            no source found; `likely` gives the best guess, not used as evidence
EVIDENCE is keyed by the OneMap postal code of each record (unique among the 40),
OVERRIDES by tp_code. in_layer marks the rows the build script adds back.

Output: output/excluded_centres_verification_2026.csv (80 rows)
        layer "planned" in output/childcare_centres_2026.gpkg (planned centres with a
        location; the build script only rewrites layer "centres", so this layer survives)
Run:    python scripts/excluded_centres_verification.py
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "output" / "excluded_centres_2026.csv"
OUT = ROOT / "output" / "excluded_centres_verification_2026.csv"
GPKG = ROOT / "output" / "childcare_centres_2026.gpkg"
SUBZONES = ROOT / "data" / "MasterPlanSubZones_2019.geojson"
VERIFIED_ON = "2026-11-01"

ECDA = "https://ecda.gov.sg/parents/preschool-search/upcoming-preschools"
PCF_UP = "https://pcfsparkletots.org.sg/upcoming-preschools/"
LAYER = "data/CentreAttributes_2026.csv (retained centre address)"

# postal: (status, likely, evidence, source)
EVIDENCE = {
    "760936": ("planned", "", "ECDA upcoming: My First Skool, Blk 936 Yishun Central, est. Q4 2026", ECDA),
    "829910": ("planned", "", "ECDA upcoming: E-Bridge Pre-school, 82 Punggol Way #03-27 to #03-37, est. Q4 2026", ECDA),
    "690135": ("planned", "", "ECDA upcoming: PCF Sparkletots @ Tengah Blk 135 (CC), est. Q4 2026; PCF upcoming list same", ECDA),
    "531214": ("planned", "", "ECDA upcoming: MY World Preschool, Blk 214A Tampines Road #02-132, est. Q4 2026", ECDA),
    "532182": ("planned", "", "ECDA upcoming: PCF Sparkletots @ Geylang Serai Blk 182B (CC), est. Q4 2026 (PCF says Q1 2027)", ECDA),
    "521899": ("planned", "", "ECDA upcoming: extension to PCF Sparkletots @ Tampines West Blk 890A (CC), Blk 899A, est. Q4 2026", ECDA),
    "320152": ("planned", "", "ECDA upcoming: My First Skool, Blk 152 Towner Road #01-01, est. Q1 2027", ECDA),
    "694216": ("planned", "", "ECDA upcoming: My First Skool, Blk 216D / 217A Tengah Garden Avenue, est. Q1 2027", ECDA),
    "521634": ("planned", "", "ECDA upcoming: PCF Sparkletots @ Tampines Boulevard Blk 634A (CC), est. Q1 2027", ECDA),
    "524859": ("planned", "", "ECDA upcoming: extension to E-Bridge Pre-school at Tampines GreenSpring, Blk 859D, est. Q1 2027", ECDA),
    "211055": ("planned", "", "ECDA upcoming: Kent Height, Blk 55A Owen Road, est. Q1 2027", ECDA),
    "730909": ("duplicate", "", "Same block and unit (909 North Woodlands Way #01-01, UrbanVille) as PCF Sparkletots @ Marsiling Blk 909 (CC)", LAYER),
    "732894": ("duplicate", "", "Same block and unit (894D Woodlands Dr 50 #01-19) as PCF Sparkletots @ Woodgrove Blk 894D (CC)", LAYER),
    "791415": ("duplicate", "", "Same block (416A Fernvale Link) and service (DS) as PCF Sparkletots @ Buangkok-Fernvale South Blk 416A (DS)", LAYER),
    "691302": ("duplicate", "", "Same HDB project (Parc Residences @ Tengah) as ST0417 PCF Sparkletots @ Brickland Blk 300 (CC)", LAYER),
    "690307": ("duplicate", "", "Same HDB project (Parc Clover @ Tengah) as ST0405 PCF Sparkletots @ Brickland Blk 308B (CC)", LAYER),
    "382020": ("duplicate", "", "Same HDB project (Kallang Breeze) as PCF Sparkletots @ Kreta Ayer-Kim Seng Blk 21 (CC)", LAYER),
    "732189": ("duplicate", "", "Same HDB project (Marsiling Grove) as My First Skool, 187 Marsiling Road #03-11", LAYER),
    "762467": ("duplicate", "", "Same HDB project (Casa Spring @ Yishun) as NT0605 My First Skool, 464 Yishun Ave 6", LAYER),
    "522489": ("duplicate", "", "Record states it is an extension of the My First Skool main centre at Blk 487C Tampines St 45, which is in the layer", "data/CentreAttributes_2026.csv (record's own address)"),
    "603285": ("operational_absent", "",
               "Operator page: 'PCF Sparkletots Preschool @ Yuhua Blk 285C (KN)', Blk 285C Toh Guan Rd #01-92, Mon-Fri 8am-5pm, no closure notice; "
               "same unit as this record; also in the 2021 layer; not in the 2026 ECDA list under any centre code",
               "https://pcfsparkletots.org.sg/our-preschools/pcf-sparkletots-bukit-batok-east-blk-285c"),
    "821223": ("unverified", "duplicate", "Matilda Edge (Blks 220-224 Sumang Lane) is served by PCF Sparkletots @ Punggol West Blk 222 (CC), Blk 222 Sumang Lane MSCP, 160 m away; not on ECDA upcoming list", "https://pcf.org.sg/sparkletots/our-preschools/pcf-sparkletots-punggol-west-blk-222"),
    "571156": ("unverified", "duplicate", "Bishan Towers (156A); My First Skool at 156C Bishan St 11, 16 m away", LAYER),
    "752101": ("unverified", "duplicate", "EastCreek @ Canberra (101B); Skool4Kidz at 101 Canberra St, 46 m away", LAYER),
    "532470": ("unverified", "duplicate", "Hougang Parkview (470B); PCF Sparkletots Blk 470C Upper Serangoon Cres, 55 m away", LAYER),
    "651443": ("unverified", "duplicate", "West Ridges (443A); E-Bridge at 443 Bukit Batok West Ave 8 MSCP, 68 m away", LAYER),
    "750333": ("unverified", "duplicate", "My First Skool at 331 Sembawang Close, 66 m away", LAYER),
    "731372": ("unverified", "duplicate", "Woodgrove Ascent (372A); My First Skool at 375 Woodlands Ave 1, 163 m away", LAYER),
    "751117": ("unverified", "duplicate", "Eastlink II (117A); My First Skool at 120 Canberra Cres MSCP, 126 m away", LAYER),
    "531996": ("unverified", "duplicate", "Buangkok Tropica (996A); My First Skool at 997 Buangkok Cres MSCP, 147 m away", LAYER),
    "659841": ("unverified", "historical", "My First Skool was at this postal code in 2021; My First Skool's site lists no centre there now (nearest Blk 260, in the layer)", "https://www.myfirstskool.com/our-centres/blk-260-bukit-batok/"),
    "390054": ("unverified", "", "No preschool found at 54 Cassia Crescent; My First Skool NT0571 at 56 Cassia Crescent is in the layer", LAYER),
    "392088": ("unverified", "", "No preschool found at Dakota One", ""),
    "761338": ("unverified", "", "HDB precinct brochure shows a preschool in Yishun Boardwalk; no operator or opening found", "https://www.mynicehome.gov.sg/wp-content/uploads/2025/03/RS-LivinginYishun-YishunBoardwalk.pdf"),
    "361216": ("unverified", "", "HDB precinct brochure shows a preschool in Bartley GreenRise; not on ECDA upcoming list (30 Sep 2026)", "https://www.mynicehome.gov.sg/wp-content/uploads/RS-LivinginBidadari-BartleyGreenRise.pdf"),
    "734691": ("unverified", "", "No preschool found in Admiralty Flora", ""),
    "684485": ("unverified", "", "No preschool found at 485D Choa Chu Kang Ave 5", ""),
    "520665": ("unverified", "", "No preschool found in Tampines GreenCrest", ""),
    "522646": ("unverified", "", "No preschool found in Tampines GreenFoliage", ""),
    "730586": ("unverified", "", "No preschool found at 586 Woodlands Dr 16; PCF Sparkletots @ Admiralty Blk 585 is 117 m away", LAYER),
}


# Duplicate or unlocated records that ECDA lists as upcoming (checked against the same page).
OVERRIDES = {
    "TP1371": ("planned", "", "ECDA upcoming: PCF Sparkletots Preschool, Blk 483 Tampines St 43 #01-202, est. Q4 2027 (a new service in the building of the retained PCF KN centre)", ECDA),
    "TP1372": ("planned", "", "ECDA upcoming: PCF Sparkletots Preschool, Blk 868A Tampines Ave 8 #01-534, est. Q4 2027 (a new service in the building of the retained PCF KN centre)", ECDA),
    "TP1198": ("planned", "", "ECDA upcoming: PCF Sparkletots @ Sembawang Central (CC), 3A Canberra View, est. Q1 2027; PCF upcoming list same", ECDA),
}
IN_LAYER = {"TP1356"}  # must match VERIFIED_ADDITIONS in build_childcare_centres_2026.py


def main():
    ex = pd.read_csv(SRC, dtype=str)
    ex["onemap_postal"] = ex["onemap_address"].str.extract(r"(\d{6})$")[0]
    pm = ex["qa_status"] == "possible_missing"
    assert ex.loc[pm, "onemap_postal"].is_unique and set(ex.loc[pm, "onemap_postal"]) == set(EVIDENCE)

    def row_status(r):
        if r["tp_code"] in OVERRIDES:
            return OVERRIDES[r["tp_code"]]
        if r["qa_status"] == "possible_missing":
            return EVIDENCE[r["onemap_postal"]]
        if r["qa_status"] == "duplicate":
            same = r["retained_centres_same_postal"]
            if pd.isna(same):
                same = f"the retained centre at postal code {r['onemap_postal']}"
            return ("duplicate", "", f"Same building and operator as {same}", LAYER)
        return ("unverified", "", "No OneMap result for the address and not on the ECDA upcoming list", "")

    ev = pd.DataFrame(ex.apply(row_status, axis=1).tolist(), index=ex.index,
                      columns=["status", "likely", "evidence", "source"])
    out = pd.concat([ex, ev], axis=1).assign(verified_on=VERIFIED_ON)
    out["in_layer"] = out["tp_code"].isin(IN_LAYER)
    out = out[["tp_code", "centre_name", "service_model", "centre_address", "onemap_address",
               "lat", "lon", "SUBZONE_N", "PLN_AREA_N", "last_updated", "qa_status", "status",
               "likely", "in_layer", "evidence", "source", "verified_on"]]
    out.sort_values(["status", "PLN_AREA_N"]).to_csv(OUT, index=False)
    print(pd.crosstab(out["qa_status"], out["status"], margins=True).to_string())
    print(f"in_layer: {out['in_layer'].sum()}")
    write_planned_layer(out)


def write_planned_layer(out):
    p = out[(out["status"] == "planned") & out["lat"].notna()].copy()
    p["expected_opening"] = p["evidence"].str.extract(r"est\. (Q\d \d{4})")[0]
    p["record_source"] = "planned"
    p = gpd.GeoDataFrame(p, geometry=gpd.points_from_xy(p["lon"].astype(float), p["lat"].astype(float)),
                         crs=4326).to_crs(3414)
    sz = gpd.read_file(SUBZONES).to_crs(3414)[["SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "REGION_N", "geometry"]]
    p = gpd.sjoin(p.drop(columns=["SUBZONE_N", "PLN_AREA_N"]), sz, predicate="within")
    p = p[["tp_code", "record_source", "centre_name", "service_model", "centre_address",
           "onemap_address", "lon", "lat", "SUBZONE_C", "SUBZONE_N", "PLN_AREA_N", "REGION_N",
           "expected_opening", "evidence", "source", "verified_on", "geometry"]]
    p.to_file(GPKG, layer="planned", driver="GPKG")
    print(f"planned layer: {len(p)} centres "
          f"({(out['status'] == 'planned').sum() - len(p)} planned without a location left out)")


if __name__ == "__main__":
    main()
