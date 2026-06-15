# 2026 Watchlist Methodology

This script generates an early-stage 2026 watchlist from Certificate-stage
parcel-year records already loaded into the unified lifecycle table.

It is intentionally conservative. Because assessor building data has not yet
been joined, the watchlist does not know bedrooms, bathrooms, condition,
occupancy, financing constraints, or parcel geometry. It uses source-document
property-type text and assessed-value signals only.

Run:

```powershell
python -m src.analysis.build_2026_watchlist
```

Outputs:

- `outputs/public/analysis_2026_homebuyer_watchlist.csv`
- `outputs/public/analysis_repeat_buyer_summary_with_names.csv`
- `outputs/public/analysis_repeat_buyer_summary_public_safe.csv`
- `outputs/public/snohomish_2026_watchlist_and_public_safe_outputs.xlsx`
- `docs/2026_watchlist_and_public_safe_buyers.md`
