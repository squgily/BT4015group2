# HDB join review: how the 156 unmatched blocks were handled

`scripts/join_hdb_nationwide.py` joins the HDB Existing Building polygons (2026-06-21) to
HDB Property Information (2026-10-08) on block number + street name. The first pass left
**156 of 13,436 blocks** without attributes. Every one of them is listed, with its
decision, in [`hdb_join_review.csv`](hdb_join_review.csv) (resolved blocks carry their
`match_status` in `hdb_blocks.gpkg`).

| Outcome | Blocks | `match_status` |
|---|---:|---|
| Matched by a fallback pass | 36 | `postal_sector`, `alt_spelling` |
| Included after manual review, units imputed | 3 | `imputed` |
| Excluded | 117 | `unmatched` |
| **Total** | **156** | |

## 1. Matched by a fallback pass (36)

**Road codes newer than the 2019 LTA lookup (19).** `ST_COD` `HOS21Q` and `HOS22Q` are
missing from `LTARoadNameCode_2019.xlsx`, so no street name could be decoded. These blocks
are matched by block number among property rows in the same contract town, where the town
is inferred from the postal sector (first two digits) of already-matched blocks; a match
is accepted only when exactly one unused row qualifies.
`HOS21Q` → Hougang St 12 (9 blocks), `HOS22Q` → Hougang St 13 (10 blocks), all completed
2025–2026.

**Street-name spelling variants (17).** The abbreviation table shortens words that HDB keeps
in full in some names, or misses abbreviations HDB uses only sometimes. The fallback tries
the unabbreviated LTA name and an extra abbreviation set (`MARKET → MKT`, `INDUSTRIAL → IND`):
Buangkok Green (10), Taman Ho Swee (5), New Market Rd → New Mkt Rd (1),
Woodlands Industrial Park E3 → Woodlands Ind Pk E3 (1).

25 of the 36 are residential; they now hold about 467 children in
`hdb_blocks_children_final.gpkg`.

## 2. Manual review of single blocks (4)

Four unmatched blocks are full-size buildings (900–2,400 m², polygons updated 2024–25) on
streets that do exist in Property Information, but their block number does not. Each was
checked by postal code on OneMap and Google Maps, against HDB resale records
(data.gov.sg, 2017 onwards) and news reports.

| Block | Postal | Evidence | Decision |
|---|---|---|---|
| 87 Jalan Satu | 390087 | OneMap: Mountbatten Community Club | Exclude |
| 63 Commonwealth Dr | 140063 | Residential block on Google Maps | Include |
| 82 MacPherson Lane | 360082 | 3-room flats (1968 lease), last resale Oct 2017; selected for SERS in 2018 ([Straits Times](https://www.straitstimes.com/singapore/three-blocks-in-macpherson-lane-get-nod-for-sers)), since repurposed for PPHS temporary housing | Include, flag |
| 40 Tanglin Halt Rd | 143040 | Residential block on Google Maps; SERS block with PPHS redevelopment plans | Include, flag |

The decisions are coded in `MANUAL_REVIEW` in `join_hdb_nationwide.py`. Flagged blocks
carry `review_flag = verify_occupancy` in both `hdb_blocks.gpkg` and
`hdb_blocks_children_final.gpkg`; occupancy was not independently verified.

**Imputed attributes.** With no Property Information row, the 3 included blocks take their
attributes from the nearest residential blocks on the same street: dwelling units = own
footprint × the neighbours' median units per m²; flat-type mix, floors, completion year and
use flags from the same neighbours.

| Block | Neighbours used | Est. units | Children 0–9 |
|---|---|---:|---:|
| 63 Commonwealth Dr | 60, 62, 64 (1963, 116–118 units each) | 116 | 13.7 |
| 82 MacPherson Lane | 81, 83 (1968, 130 and 93 units) | 113 | 11.3 |
| 40 Tanglin Halt Rd | 38, 41, 42 (1962, 116–118 units each) | 118 | 13.9 |

The neighbours for 63 and 40 are near-identical blocks; the estimate for 82 is rougher.

## 3. Rows that remain excluded (117)

- **116 Pasir Ris structures**: Pasir Ris Heights (55), Terrace (40), Avenue (15),
  Road (6). None of these streets appears in Property Information 2026, the footprints are
  small (median 96 m² against roughly 600–1,500 m² for a flat block) and most polygons were
  last updated in 2013. They are not treated as flat blocks. Verified that they are landed properties through google search.
- **87 Jalan Satu**: Mountbatten Community Club (see §2).

Excluded blocks have null attributes and `is_residential = False`, so they carry no demand.

## 4. Effect on child population

Subzone child totals come from SingStat and are always fully assigned to the residential
blocks in that subzone, so no child is lost through an excluded block; an exclusion can
only shift children to other blocks in the same subzone. After this review all 259,910
HDB children aged 0–9 are assigned across 10,769 blocks, with no nulls. The 3 imputed
blocks hold about 39 of them.

## Regenerate

```
python scripts/join_hdb_nationwide.py
python scripts/assign_child_population_fillnull.py
```
