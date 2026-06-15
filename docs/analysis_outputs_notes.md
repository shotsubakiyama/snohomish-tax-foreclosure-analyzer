# Analysis Output Notes

These analysis outputs are derived from `outputs/public/unified_parcel_lifecycle.csv`.

## Generated tables

- `analysis_annual_funnel.csv`: certificate/publication/final-order/sale counts by year.
- `analysis_auction_competitiveness_by_year.csv`: sale prices, bid multiples, and winning-bid premiums.
- `analysis_property_type_summary.csv`: lifecycle counts by simplified property category.
- `analysis_repeat_buyer_summary.csv`: buyer concentration and repeat-buyer activity.
- `analysis_top_bid_multiples.csv`: highest sale-price-to-minimum-bid examples.
- `analysis_review_flags.csv`: parcel-years that still have OCR caveats.

## Caveats

The funnel is strongest from Publication → Final Order → Sale for years with usable publication data. The 2020 Affidavit remains pending OCR/layout review. Certificate-stage coverage is partial, so certificate-to-publication rates should not yet be presented as complete historical rates.

Blank rate fields generally mean the denominator was zero or unavailable for that year.

## Suggested report framing

Use the funnel and competitiveness tables as the first public-facing analysis. Treat certificate-stage counts, OCR review flags, repaired APNs, and assessor/GIS overlays as future-version notes rather than blockers.
