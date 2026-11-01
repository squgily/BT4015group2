# Childcare centres 2026: how locations and fees were built

`scripts/build_childcare_centres_2026.py` builds `childcare_centres_2026.gpkg` (layer
`centres`, EPSG:3414) from the 2026 ECDA centre list, so the analysis covers currently
listed centres. It replaces the 2021 GeoJSON as the base layer. That file had **562 of
1,925 centres** with no fee, because fees had to be matched to 2021 names. Here every
centre is joined to its fee by `centre_code`, and nothing is imputed.

| Outcome | Centres |
|---|---:|
| 2026 rows in `CentreAttributes_2026.csv` | 1,875 |
| Dropped: `centre_code` is `na` (mostly no name either, cannot join fees) | 80 |
| Added back: an `na` row verified as an operating centre (section 3.2) | 1 |
| **Centres in the layer, all with a location** | **1,796** |
| With a Nursery fee | 1,587 |
| Without a fee | 209 |

Every centre that was geocoded or has no fee is listed in
[`childcare_centres_2026_review.csv`](childcare_centres_2026_review.csv) (420 rows).

## Using this layer

This is the shared centre dataset for the project: one row per centre operating in
October 2026. Read it with `gpd.read_file("output/childcare_centres_2026.gpkg", layer="centres")`.

| Column | Meaning |
|---|---|
| `centre_code` | ECDA centre code; the key for joining other ECDA tables (vacancy, services). Empty for the 1 verified addition |
| `tp_code` | ECDA `tp_code`, mostly `na`; identifies the verified addition |
| `record_source` | `ecda_listed` (1,795) or `verified_addition` (1) |
| `centre_name`, `organisation_code`, `organisation_description`, `service_model`, `centre_address`, `postal_code`, `last_updated` | As listed by ECDA |
| `lon`, `lat`, `location_source`, `objectid_2021`, `name_similarity_2021` | Location and how it was found (section 1) |
| `FULL_DAY_SC_NURSERY_FEE`, `fee_status` | Nursery fee, or why it is missing (section 2) |
| `SUBZONE_C`, `SUBZONE_N`, `PLN_AREA_N`, `REGION_N` | 2019 Master Plan subzone the point falls in; all 1,796 fall in one |

Filter for what your analysis needs rather than dropping rows from the file:

- **Supply and accessibility:** all rows. `service_model` CC, DS, EYC and EYC-DS all
  provide childcare; KN (183) are kindergartens only, so decide whether they count.
- **Fees:** `fee_status == "listed"`.
- **Joining vacancy or other ECDA attributes:** join on `centre_code`. The verified
  addition has no code, so it gets no attributes.

Centres that are planned, duplicated or unverified are not in the layer. They are in
[`excluded_centres_verification_2026.csv`](excluded_centres_verification_2026.csv) with
a status and source for each (section 3.2).

**Layer `planned` (13 centres).** These are centres ECDA lists as upcoming, kept in the
same file for analyses of future supply (for example Tengah once Blk 135 and Blk 216D
open). Read it with `layer="planned"`. It has the same name, address and subzone
columns as `centres`, plus `expected_opening` (Q4 2026 to Q4 2027), the ECDA entry and
source. Most have no name in the ECDA list (`na`); the `evidence` column gives the name
from ECDA's upcoming page. A 14th planned centre, PCF Sparkletots @ Sembawang Central at
3A Canberra View (Q1 2027), has no location yet and is only in the CSV. Do not add
`planned` to current supply.

**The H-a and H-c scripts read a different layer.** `build_walk_matrix.py`,
`build_subzone_stats.py` and `lisa_hc.py` read `data/Centres_2026.geojson` (from
`geocode_centres_2026.py`). That file keeps only CC and KN, so it leaves out the 145 DS,
EYC and EYC-DS centres. It also includes PCF Sparkletots @ Tampines Boulevard Blk 634A,
which ECDA lists as opening in Q1 2027. Switching those scripts to this layer is up to
their owner.

## 1. Locations (`location_source`)

| `location_source` | Centres | How |
|---|---:|---|
| `2021_postal_name` | 1,223 | Same postal code as a 2021 centre, similar name (score ≥ 0.6) |
| `2021_postal_only` | 267 | Same postal code as a 2021 centre, different name |
| `onemap_postal` | 305 | No 2021 centre at that postal code; geocoded with OneMap search |

**Matched to 2021 (1,490).** Each 2026 centre is matched to the 2021 GeoJSON by postal
code. If several 2021 centres share the code, the most similar name is taken
(`name_similarity_2021`, using the same name normalisation as `join_childcare_fees.py`).
The 2021 coordinates are reused on the assumption that the centre has not moved. A
Singapore postal code identifies a single building, so the coordinates hold even when
the name differs. A sample of the 267 `2021_postal_only` matches showed that these are
mostly a different centre in the same building, for example a new operator in former
premises, or a preschool in a church that hosted a kindergarten in 2021. They are not
missed name matches. `objectid_2021` gives the 2021 centre each match came from.

**Geocoded (305).** These are centres opened or moved since 2021. All 305 were found by
postal code on OneMap (`https://www.onemap.gov.sg/api/common/elastic/search`), so the
street-address fallback was not needed. Responses are cached in
[`onemap_geocode_cache.csv`](onemap_geocode_cache.csv), so a rerun does not query OneMap
again.

## 2. Fees (`FULL_DAY_SC_NURSERY_FEE`, `fee_status`)

The fee is the Nursery (4 yrs old), Full Day, Singapore Citizen fee from
`ListingofCentreServices.csv`, joined by `centre_code`. A centre with several different
fees for that combination gets no fee. These are the same rules as
`join_childcare_fees.py`.

| `fee_status` | CC | KN | DS / EYC / EYC-DS | Total |
|---|---:|---:|---:|---:|
| `listed` | 1,442 | 0 | 145 | 1,587 |
| `no_nursery_full_day_sc_listing` | 10 | 183 | 0 | 193 |
| `conflicting_fees` | 15 | 0 | 0 | 15 |

**Kindergartens (183).** KN centres do not offer full-day Nursery, so a missing fee is
correct for them. Leave them out of fee analyses rather than impute a fee. Without them,
**25 of 1,612 centres (1.6%)** have no fee. That is too few to justify spatial or
model-based imputation, so they are left missing.

**No Nursery Full Day SC listing (10 CC).** These are mostly infant-care-only centres:

| `centre_code` | Centre |
|---|---|
| PT9416 | Heartyland Infant Care Pte Ltd |
| PT9123 | Nurture Infant Pte Ltd |
| PT9874 | York Infant River Valley |
| PT9956 | Superland Pre-School (Immersion) Pte. Ltd. |
| PT9846 | Bright Sparks Infant Care Pte. Ltd |
| PT8853 | Greentree Children Community Pte Ltd |
| PT9801 | Camelot Learning Centre Pte Ltd |
| PT9800 | Alora Infant Care (Leng Kee) Pte Ltd |
| PT9277 | Camelot International Infant Care Pte Ltd |
| PT9484 | Baby Elk Infant Care Pte Ltd |

**Conflicting fees (15), still to be checked by hand.** These centres have more than one
Nursery Full Day SC fee listed. Some gaps are small (e.g. a GST-inclusive and an
exclusive figure). Others, such as 650 vs 2,000, suggest a row that is not really full
day. Check `remarks` in the fee listing and the centre's own website.

| `centre_code` | Centre | Fees listed |
|---|---|---|
| PT9078 | ChildFirst @ Tampines | 2016.51, 2108.26 |
| PT8822 | ChildFirst @ Hillview | 2016.51, 2108.26 |
| PT9167 | Wharton Eastcoast | 1730, 1830 |
| PT9802 | Little Paddington Preschool and Infant Care Kent Ridge | 1830, 2000 |
| PT9366 | The Schoolhouse West Coast | 2180, 2235 |
| PT8933 | The Schoolhouse Sembawang (Sembawang Country Club) | 1980, 2180 |
| PT8374 | The Schoolhouse Mount Emily | 2030, 2250 |
| PT8040 | The Schoolhouse Gentle Road | 1850, 2150, 2250 |
| PT9926 | The Schoolhouse Kovan 2 | 2100, 2230 |
| PT9151 | The Schoolhouse Kovan | 2100, 2230 |
| PT9128 | Little Footprints Preschool Asia | 650, 2000 |
| RC1745 | Little Dolphins Playskool | 650, 800 |
| PT9820 | Kinderland Preschool | 650, 680 |
| PT9821 | Kinderland Preschool | 650, 680 |
| PT9437 | Creative Thinkers Preschool | 1500, 1550 |

## 3. The 80 dropped records (`centre_code` is `na`)

`scripts/locate_excluded_centres_2026.py` locates them and writes
[`excluded_centres_2026.csv`](excluded_centres_2026.csv). Most of them look like ECDA
licensing records for planned centres, not separate operating centres: 70 have no name,
and many give an HDB contract code (`N4 C18`, `PAC5`) instead of a building.

| Group | Records | Located | Duplicate of a retained centre | Possible missing centre |
|---|---:|---:|---:|---:|
| Postal code `000000` | 24 | 21 (block + street, or project name) | 4 | 17 |
| Postal code used by a retained centre | 31 | 31 (that centre's point) | 31 | 0 |
| Postal code not in the layer | 25 | 23 (OneMap postal) | 0 | 23 |
| **Total** | **80** | **75** | **35** | **40** |

**Duplicates (35).** Each one shares a building with a retained centre from the same
operator (PCF Sparkletots, My First Skool, Skool4Kidz). For 33 it is the same centre,
already in the layer. The other 2 (Blk 483 Tampines St 43 and Blk 868A Tampines Ave 8)
are new childcare services ECDA lists as opening in Q4 2027 in buildings that already
have a PCF kindergarten, so they are planned, not operating (section 3.2).

**Not located (5).** `3A Canberra View`, `445A Northshore Drive` and `991 Upper Jurong
Road` return nothing from OneMap. `MK16 Lot No. 02852K & 02843M` and `PAC5` have no
address. 3A Canberra View is PCF Sparkletots @ Sembawang Central, which ECDA lists as
opening in Q1 2027. The other four are unverified.

**Possible missing centres (40).** These are spread across 15 planning areas, at 1 to 6%
of each area's retained centres. The exception is **Tengah, with 4 against 14 retained
(22%)**. 38 fall in subzones covered by the H-c analysis. 2 fall in the H-c pressure
cluster (supply quadrant HL): one in Garden (4 retained centres) and one in Matilda (14).
That is 5% of the excluded records, against 3% of retained centres, so leaving them out
does not create the clusters. The Garden record turned out to be planned, not open
(section 3.2). None fall in the walk-time HH subzones. Four OneMap matches are to the
next block (for example 182A geocoded as 182B Hougang Street 13), which is the same estate
and close enough for subzone assignment.

Section 3.2 checks whether each of the 40 is open. Only one is.

### 3.1 Are the missing records spatially concentrated?

`scripts/excluded_centres_missingness.py` writes rates by planning area and subzone to
[`excluded_centres_missingness_by_area.csv`](excluded_centres_missingness_by_area.csv).
The comparison population is all 1,835 centre locations: 1,795 retained and 40 possibly
missing. The overall missing rate is **2.18%**.

**Null hypothesis (random labelling).** The 40 are a random draw from the 1,835 observed
centre locations. This null keeps the real geography of centres, so it asks only whether
missingness is uneven among places that have centres. It does not ask whether centres
themselves cluster. 9,999 label permutations, seed 4015, one-sided p.

| Statistic | What it measures | Observed | Null mean | Null 95th (5th for NN) | p |
|---|---|---:|---:|---:|---:|
| G, planning area | Unequal missing rates across 42 planning areas | 59.7 | 36.2 | 49.4 | **0.002** |
| G, planning area, Tengah removed | Same, without Tengah | 48.0 | 34.8 | – | **0.041** |
| G, subzone | Unequal missing rates across subzones | 122.0 | 127.9 | 143.3 | 0.73 |
| Cuzick-Edwards T₁ | Missing records whose nearest centre is also missing | 1 | 2.2 | 5 | 0.87 |
| Cuzick-Edwards T₅ | Same, among the 5 nearest centres | 10 | 5.9 | 11 | 0.12 |
| Mean nearest-neighbour distance among the 40 | Closeness of missing records to each other | 1,018 m | 1,460 m | 1,216 m | **0.001** |

**Tengah.** 4 of 18 centres are missing (22.2%), against 0.39 expected at the overall rate,
a rate ratio of **10.2**. Exact hypergeometric P(X ≥ 4) = 0.0005, which is **0.020 after
Bonferroni correction** over the 42 planning areas. No other planning area is above 6%.
The next highest are Kallang (3 of 50), Woodlands (6 of 102) and Sembawang (3 of 62).

**Clark-Evans, against complete spatial randomness (CSR).** The study area is the 2019
subzone boundary (785 km²), with 999 simulations of 40 uniform points inside it.
R = 0.46 against a CSR mean of 1.18, p = 0.001. This is given for reference only. The
retained centres have R = 0.55 on the same boundary, so the missing records cluster against
CSR about as much as all centres do, because centres sit where people live. The CSR test
does not show that missingness is biased; the random-labelling tests above are the ones
to use.

**Interpretation.**

- **Concentration by planning area is significant, and it is mostly Tengah.** Missing
  records fall unevenly across planning areas (p = 0.002), and Tengah alone is significant
  after correction. Without Tengah the result is borderline (p = 0.041): a mild tilt
  towards the north and east (Woodlands, Sembawang, Tampines, Hougang), where BTO blocks
  have been completed recently.
- **There is no clustering at subzone or neighbour scale.** Subzone rates are no more
  uneven than chance (p = 0.73), and missing records are not each other's nearest
  neighbours (T₁ p = 0.87, T₅ p = 0.12). The high subzone rates in the CSV (Park 2 of 7,
  Tampines North 3 of 13) each rest on one to three records. They are descriptive and
  not significant. With 40 records spread over the 238 subzones that have centres, the subzone test has
  little power.
- **The shorter nearest-neighbour distance shows regional, not local, clustering.** The
  40 are closer to each other than 40 random centres would be (p = 0.001). The local
  Cuzick-Edwards tests are not significant, so this reflects records sharing a handful of
  towns about 1 km apart, not forming tight local clusters. That fits the planning-area
  result.
- **What this means for the analysis.** The excluded records are not randomly placed.
  They follow the newest BTO towns, Tengah above all. Verification (section 3.2) shows why:
  they are mostly records for centres being built in new estates. None of Tengah's 4 is an
  operating centre missing from the layer: 2 are planned (Blk 135 for Q4 2026, Blk 216D
  in Garden for Q1 2027) and 2 duplicate PCF centres already in the layer. So the
  concentration does not mean supply is understated today. It does mean Tengah's supply
  is about to grow, which is worth one sentence in the limitations of H-a and H-c.

### 3.2 Which of the dropped records are operating?

Each of the 40 possibly missing centres was checked on **2026-11-01**. The sources were:
- ECDA's upcoming-centres page (<https://ecda.gov.sg/parents/preschool-search/upcoming-preschools>,
  "Information accurate as at 30 September 2026").
- PCF's upcoming list (<https://pcfsparkletots.org.sg/upcoming-preschools/>).
- Operators' own centre pages.
- The addresses of retained centres in `CentreAttributes_2026.csv`.

The 35 duplicates and 5 unlocated records were also checked against the ECDA list.
`scripts/excluded_centres_verification.py` writes all 80 with their status, evidence and
source URL to [`excluded_centres_verification_2026.csv`](excluded_centres_verification_2026.csv).

| `status` | From the 40 | From the other 40 | Total | Meaning |
|---|---:|---:|---:|---|
| `planned` | 11 | 3 | 14 | On ECDA's upcoming list, opening Q4 2026 to Q4 2027 |
| `duplicate` | 9 | 33 | 42 | Same block and unit, same named HDB project, or a stated extension of a centre in the layer |
| `operational_absent` | 1 | 0 | 1 | Operating per the operator, not in the ECDA list; **added to the layer** |
| `unverified` | 19 | 4 | 23 | No source found either way |

**Added to the layer (1).** PCF Sparkletots Preschool @ Yuhua Blk 285C (KN), 285C Toh
Guan Rd #01-92 (`tp_code` TP1356). PCF's centre page
(<https://pcfsparkletots.org.sg/our-preschools/pcf-sparkletots-bukit-batok-east-blk-285c>)
lists it at that unit, open Monday to Friday 8am to 5pm, with no closure notice. It was
also in the 2021 layer. The ECDA row has no name or centre code, so the name comes from
PCF's page. Other fields are kept as ECDA lists them, including `service_model` DS,
although PCF lists the centre as a kindergarten. It has no fee (`fee_status`
`no_centre_code`). Its point is the 2021 point at the same postal code. It is in subzone
Toh Guan (JESZ03), Jurong East.

**Priority areas.**
- Garden: My First Skool at 216D Tengah Garden Ave is planned for Q1 2027.
- Matilda: unverified. Matilda Edge is served by PCF Sparkletots @ Punggol West Blk 222,
  160 m away and already in the layer, so it is most likely a duplicate.
- Tengah: Blk 135 is planned for Q4 2026. Parc Residences and Parc Clover duplicate PCF
  Brickland Blk 300 and Blk 308B.

**Unverified (23).** These stay out of the layer. 9 sit 16 to 163 m from a retained
centre in the same estate and are most likely duplicates (`likely` = `duplicate`). One is
at a postal code where My First Skool operated in 2021 but no longer lists a centre
(`likely` = `historical`). 13 have nothing found either way, for example Dakota One,
Admiralty Flora, Tampines GreenCrest and the four unlocated BTO sites. The `likely`
column is a guess and not evidence. If one of them is confirmed open, add its `tp_code`
to `VERIFIED_ADDITIONS` in the build script and to `IN_LAYER` in the verification
script, then rerun.

### 3.3 Sensitivity to the unverified records

`scripts/unverified_centres_sensitivity.py` adds the unverified records to the layer
under two scenarios. 19 of the 23 have a location; the other 4 cannot be placed.

| Scenario | Added | Centres |
|---|---:|---:|
| Layer as built | 0 | 1,796 |
| `plausible`: unverified, not judged likely duplicates | 10 | 1,806 |
| `upper_bound`: all located unverified | 19 | 1,815 |

Both scenarios are layers in
[`childcare_centres_2026_sensitivity.gpkg`](childcare_centres_2026_sensitivity.gpkg), with
the added rows marked `record_source` `unverified_sensitivity`. Use them only as a
robustness check, not as the main data. Per-subzone counts and centres per 1,000 children
aged 0 to 9 are in
[`unverified_centres_sensitivity_by_subzone.csv`](unverified_centres_sensitivity_by_subzone.csv).
Child counts come from `subzone_stats.csv`; nothing in the analysis was rerun.

- **The effect is small and spread out.** Under the upper bound, 16 subzones gain 1 or 2
  centres. The largest relative changes are in Bukit Batok East (+1, from 4), Sembawang East
  (+2, from 9) and Tampines North (+2, from 10).
- **Only one H-c cluster subzone is affected: Matilda.** It gains 1 centre (14 to 15), so
  supply rises from 2.55 to 2.74 per 1,000 children (+7%). Matilda's supply LISA is
  p = 0.043, so a 7% change could move it across 0.05. The added record is a likely
  duplicate of PCF Punggol West Blk 222, so it is in `upper_bound` only. Garden, Hong Kah,
  Punggol Town Centre, Tiong Bahru and Clementi North gain nothing in either scenario.

The counts here use this layer, which includes DS and EYC centres. They differ from
`centres_n` in `subzone_stats.csv`, which uses the CC and KN-only layer; for example,
Garden has 5 here and 4 there.

## Rerunning

```
python scripts/build_childcare_centres_2026.py         # the layer
python scripts/locate_excluded_centres_2026.py         # QA: locate the 80 na rows
python scripts/excluded_centres_verification.py        # QA: status of the 80, and layer "planned"
python scripts/excluded_centres_missingness.py         # QA: section 3.1
python scripts/unverified_centres_sensitivity.py       # QA: section 3.3
```

The build script reads only `data/` and writes only the three `output/` files above.
`VERIFIED_ADDITIONS` in the build script holds the one `na` row it adds back. The QA
scripts use only the `ecda_listed` rows, so their results do not change when a row is
added back. The build does not change `ChildCareServices_2021.geojson`. The fee analysis scripts
(`spatial_autocorrelation_nursery_fee.py`, `household_income_nursery_fee_regression.py`)
still read the 2021 GeoJSON, so point them at `childcare_centres_2026.gpkg` to use this
layer.
