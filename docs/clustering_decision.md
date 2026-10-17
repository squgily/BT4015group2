# How we group HDB blocks into neighbourhoods

## Why cluster at all

Our origins are HDB residential blocks (10,741 blocks nationwide after dropping carparks,
markets and other non-residential blocks). Computing accessibility per block is possible, but
the young-child population is only published per subzone, so demand has to be allocated
downward anyway. Grouping blocks into walkable neighbourhoods gives a unit that is (a) small
enough that one walk time represents every block in it, (b) large enough to carry a
meaningful child count, and (c) easy to map and explain. Clusters are built **within each
subzone**, so every cluster belongs to exactly one subzone and the population allocation stays
clean.

## Options considered

**Option A — "blocks within 200–300 m of each other form a cluster" (DBSCAN / single linkage).**
This is the rule in the proposal. Two blocks join if they are within the threshold, and
clusters grow by chaining: A joins B, B joins C, so A and C end up together even if they are
far apart.

**Option B — "no two blocks in a cluster are more than 300 m apart" (complete-linkage
agglomerative clustering with a 300 m distance threshold).** Blocks are merged bottom-up, but a
merge is only allowed if the resulting cluster's diameter stays under 300 m. A 400 m variant was
also tested.

## Evidence

Both options were run on all 10,741 blocks, separately inside each of the 159 subzones that
contain HDB. The decisive metric is the **centroid error**: how far a block sits from its
cluster's (unit-weighted) centroid. That is the error we accept when the walk time is computed
once per cluster instead of once per block.

| | Option A (DBSCAN 250 m) | Option B (complete 300 m) | Option B' (complete 400 m) |
|---|---|---|---|
| Clusters nationwide | 193 | 1,400 | 981 |
| Largest cluster | 413 blocks | 31 blocks | 40 blocks |
| Median cluster | 36 blocks / 4,500 flats | 7 blocks / 790 flats | 11 blocks / 1,140 flats |
| 95th-pct cluster diameter | 1.7 km | 289 m | 384 m |
| Mean centroid error | 367 m (~5 min walk) | 79 m (~1 min) | 101 m (~1.5 min) |
| 95th-pct centroid error | 790 m (~10 min) | 142 m | 180 m |

Example, Tampines East subzone (437 blocks): Option A gives 2 clusters, one of them 413 blocks
spanning the whole estate. Option B gives 58 clusters of up to 16 blocks, each roughly one
HDB precinct. See `figures/clustering_comparison.png`.

## Decision: Option B, complete linkage, 300 m, per subzone

- **Option A fails its own purpose.** HDB estates are dense: almost every block has a
  neighbour within 250 m, so chaining merges whole towns. A 10-minute centroid error is larger
  than the walking differences we are trying to measure.
- **Option B gives a guaranteed walking scale.** Every block is within about 2 minutes' walk of
  its cluster centroid, so one walk time per cluster is a fair stand-in for all its blocks.
- **The clusters look like real neighbourhoods.** Median cluster is 7 blocks, about 790 flats,
  which matches an HDB precinct. That is the level at which residents actually experience
  "the nearest childcare".
- **Size is still manageable.** 1,400 clusters nationwide is a trivial routing job and a readable
  map. If it proves too fine for presentation, the 400 m variant (981 clusters) is the fallback
  and changes nothing else in the pipeline.

## Implementation

Residential block centroids in EPSG:3414 (metres), grouped by `SUBZONE_C`, then
`sklearn.cluster.AgglomerativeClustering(n_clusters=None, distance_threshold=300,
linkage="complete")`. Cluster id = `{SUBZONE_C}_{k}`. Cluster centroid is weighted by dwelling
units so it sits where the people are. Script: `scripts/experiment_clustering.py` (comparison),
with the production step to follow in the preprocessing pipeline.

## Caveats to state in the report

- 300 m is a straight-line cap; walking paths inside a precinct can be longer, but at this scale
  the difference is under a minute.
- Clusters do not cross subzone boundaries by design. A few estates that straddle a boundary are
  split in two; this is intentional so that population allocation stays consistent.
