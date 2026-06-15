# README Graphs and Professional Insights Snippet

Paste this into the README after the Key findings section, or adapt into the final report.

## What this analysis suggests

This project is not just a document extraction exercise. The linked lifecycle table makes it possible to analyze the tax foreclosure process as a funnel, rather than as isolated PDFs.

### 1. Minimum bid behaves more like a legal threshold than a market signal

The auction competitiveness outputs show that winning bids often exceed the minimum bid by several multiples. For buyers, this means the minimum bid is a poor affordability proxy. For analysts, it suggests that minimum bid should be modeled as an opening constraint rather than an estimate of expected sale price.

![Median winning bid multiple by year](docs/assets/median_bid_multiple_by_year.png)

![Minimum bid versus winning sale price](docs/assets/minimum_bid_vs_sale_price.png)

### 2. The main buyer problem is triage, not just finding parcels

The lifecycle data shows that many parcels appear before the sale stage but do not ultimately become confirmed sales. A practical buyer does not only need a list of parcels; they need a way to prioritize which parcels are still active, which ones are likely residential, and which ones have enough property information to justify deeper due diligence.

![Foreclosure lifecycle funnel by year](docs/assets/lifecycle_funnel_by_year.png)

### 3. The market appears to include specialized participants

Repeat-buyer outputs show that a subset of purchasers appear across multiple auction years. This matters because first-time or occasional buyers are not only evaluating properties; they may also be competing against participants who understand the auction process, title risks, redemption dynamics, and local parcel quirks.

![Repeat-buyer concentration](docs/assets/repeat_buyer_concentration.png)

### 4. 2026 opportunities need assessor enrichment before true ranking

The 2026 watchlist is useful for screening, but not yet sufficient for purchase decisions. The next professional-grade improvement is to join assessor and GIS fields: beds, baths, building square feet, year built, property class, parcel geometry, hazard overlays, zoning, access, and utilities/septic indicators.

![2026 watchlist by fit category](docs/assets/2026_watchlist_by_category.png)

## Practical professional takeaways

- A low minimum bid should trigger due diligence, not excitement.
- The most valuable workflow is stage-based triage: certificate → publication → final order → sale.
- OCR imperfections are manageable if they are exposed with review flags instead of hidden.
- Public-safe repeat-buyer outputs let the project discuss market structure without relying on named individuals in the narrative.
- Assessor/GIS enrichment is the highest-value next data layer because it turns a foreclosure dataset into a property-screening dataset.
