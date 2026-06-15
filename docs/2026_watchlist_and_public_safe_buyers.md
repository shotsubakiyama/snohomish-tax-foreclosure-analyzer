# 2026 Opportunity Watchlist and Public-Safe Buyer Outputs

## 2026 watchlist framing

The 2026 table is an early-stage watchlist built from Certificate of Delinquency
records currently loaded into the lifecycle table. It is not a recommendation
list.

The scoring lens is a flexible first-time homebuyer:

- ideal target: 2–3 bedrooms and 2 bathrooms;
- house preferred;
- condos/townhomes still interesting;
- rural or less conventional properties are not automatically excluded.

Current limitation: beds, bathrooms, building area, condition, occupancy, HOA
status, utilities, septic, and parcel geometry are not yet loaded. Those should
come from future assessor/GIS enrichment.

Very low assessed values are not automatically attractive. They may indicate
partial interests, odd parcels, source-value issues, mobile-home/site issues,
land-only components, or other risks that require parcel-level verification.

## Repeat-buyer names

The project currently keeps buyer names because they appear in public Return of
Sale records and are useful for reproducibility. However, the output also
includes a public-safe repeat-buyer table with stable hashed buyer IDs and
generic display names. This makes it easy to remove names from the public report
later while preserving concentration and repeat-participant analysis.

## Future data that would materially improve the watchlist

- Assessor parcel/building attributes: beds, baths, building sqft, year built,
  property class, land/improvement values, situs address, and prior sale.
- GIS geometry: parcel shape, road frontage, access, incorporated area, UGA,
  zoning, and future land use.
- Hazard/environment overlays: floodplain, wetland, stream buffer, steep slope,
  shoreline jurisdiction, and landslide risk.
- Utility/septic indicators where available.
- Permit/code records: recent permits, code enforcement, demolition, unsafe
  structures, and septic/health notes.
- Manual image review from assessor photos, aerial imagery, and street view.

These should be future-version enhancements, not blockers for the current
lifecycle analysis.
