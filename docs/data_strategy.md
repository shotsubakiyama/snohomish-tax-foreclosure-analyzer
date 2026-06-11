# Data Strategy

## Product objective

Turn fragmented Snohomish County tax-foreclosure records into a parcel-level
historical and due-diligence dataset that is understandable to nontechnical
buyers while retaining enough source detail for professional analysis.

## Collection principle

Collect somewhat more than the current report needs when a field is:

1. available from the same source at low marginal cost;
2. useful for joins, validation, or future scoring;
3. difficult to reconstruct after the source changes; or
4. likely to explain why an apparently attractive parcel is risky.

Do not discard raw source values merely because a normalized version exists.
Preserve both whenever feasible.

## Planned source families

- Certificate of Delinquency
- Affidavit of Publication
- Final Order of Sale
- Return of Sale
- Excess Funds List
- Assessor parcel and improvement data
- Parcel geometry and addressing
- Zoning and future land use
- FEMA flood hazard
- Wetlands, streams, shoreline, and geologic hazards
- Permit and septic records
- Prior recorded sales
- Utility service-area data
- Historical aerial-review observations

## Data layers

### Source layer
Immutable downloaded documents and source-manifest metadata.

### Normalized layer
Separate relational tables for parcels, auction events, sale outcomes,
assessor snapshots, hazards, permits, buyers, and sources.

### Product layer
Public CSV, Excel, static HTML report, maps, and plain-English risk summaries.

## Important modeling rules

- Parcel number is the primary cross-source join key, but not a universal
  record key. Use parcel-year and auction-sale identifiers as well.
- Preserve source dates because assessed values and classifications change.
- Keep source text for legal descriptions, use descriptions, and special notes.
- Treat vacant land, improved residential property, condos, and unusual
  interests as different analytical populations.
- Keep opportunity and complexity/risk as separate measures rather than
  collapsing them into one opaque score.
- Retain buyer names as printed for historical market analysis, while avoiding
  contact enrichment or solicitation-oriented fields.
