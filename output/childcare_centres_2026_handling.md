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
| **Centres in the layer, all with a location** | **1,795** |
| With a Nursery fee | 1,587 |
| Without a fee | 208 |

Every centre that was geocoded or has no fee is listed in
[`childcare_centres_2026_review.csv`](childcare_centres_2026_review.csv) (419 rows).

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

## Rerunning

```
python scripts/build_childcare_centres_2026.py
```

The script reads only `data/` and writes only the three `output/` files above. It does
not change `ChildCareServices_2021.geojson`. The fee analysis scripts
(`spatial_autocorrelation_nursery_fee.py`, `household_income_nursery_fee_regression.py`)
still read the 2021 GeoJSON, so point them at `childcare_centres_2026.gpkg` to use this
layer.
