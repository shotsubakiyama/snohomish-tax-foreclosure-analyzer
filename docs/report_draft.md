# Snohomish County Tax Foreclosure Auction Analysis

## Working title

**What Actually Happens in Snohomish County Tax Foreclosure Auctions?**

A parcel-level look at foreclosure-stage records, auction outcomes, bid competition, and early 2026 opportunities.

---

## 1. Project overview

This project builds a reproducible dataset of Snohomish County tax foreclosure auction records from public county documents. The goal is to make the tax foreclosure process easier to analyze by connecting separate public records into a parcel-year lifecycle.

The core lifecycle is:

```text
Certificate of Delinquency
→ Affidavit of Publication
→ Final Order of Sale
→ Return of Sale
→ Excess Funds, where available
```

The project is designed for public-interest research, education, reproducibility, and practical due diligence. It is not intended to be used as a marketing, solicitation, lead-generation, or contact list.

## 2. Key takeaways so far

### Minimum bid is not a realistic purchase-price estimate

Across confirmed auction sales, winning bids often exceeded minimum bids by several multiples. Recent years show especially high competition. This means a low minimum bid should be treated as the legal starting point for auction, not as a likely acquisition price.

### Many parcels do not make it all the way to sale

The lifecycle table shows that parcels may appear at earlier stages and then disappear before sale due to payment, redemption, administrative removal, or other status changes. For practical buyers, this matters because researching every early-stage parcel can waste time unless the parcel remains active.

### Repeat buyers appear across multiple years

The Return of Sale records show a mix of one-time buyers and repeat participants. This suggests Snohomish tax foreclosure auctions attract both occasional buyers and more specialized or professional participants.

Buyer names are included in the current working dataset because they appear in public Return of Sale records and are useful for reproducibility. However, the project also generates public-safe repeat-buyer outputs with generic buyer labels and stable hashed IDs, so the final public report can remove names if desired.

### 2026 is best treated as an opportunity watchlist, not a recommendation list

The 2026 table is based on Certificate-stage records. It can identify parcels that may warrant follow-up, but it does not yet include enough property-level information to rank purchase opportunities confidently.

For a flexible first-time-homebuyer lens, the current 2026 watchlist prioritizes likely residential homes and condos/townhomes, while flagging vacant land, commercial/non-residential properties, and very-low-value parcels as higher caution.

## 3. Data sources loaded

The project currently includes public Snohomish County foreclosure-related PDFs across multiple years:

| Source layer | Current coverage | Status |
|---|---:|---|
| Return of Sale / auction sales | 2019–2025 | Strong |
| Final Order of Sale | 2019–2025 | Usable with OCR caveats |
| Affidavit of Publication | 2021–2025; 2020 pending | Usable with caveats |
| Certificate of Delinquency | Partial; strongest for machine-readable 2024 and 2026 records | Partial / future work |
| Excess funds | Exact matches currently loaded for 2024–2025 | Partial / future work |
| Assessor / parcel characteristics | Not yet integrated | Future version |
| GIS / hazard / zoning overlays | Not yet integrated | Future version |

The project intentionally preserves coverage gaps rather than hiding them. The generated coverage audit files are intended to make these limitations visible in the final report.

## 4. Current dataset outputs

The main generated outputs are:

| Output | Purpose |
|---|---|
| `unified_parcel_lifecycle.csv` | Main parcel-year lifecycle table |
| `foreclosure_stage_events.csv` | Long-form source/stage events |
| `unified_lifecycle_summary.csv` | Annual lifecycle counts |
| `snohomish_analysis_outputs.xlsx` | Analysis workbook |
| `analysis_annual_funnel.csv` | Annual certificate/publication/final-order/sale funnel |
| `analysis_auction_competitiveness_by_year.csv` | Minimum bid vs sale price metrics |
| `analysis_repeat_buyer_summary.csv` | Repeat-buyer activity |
| `analysis_repeat_buyer_summary_public_safe.csv` | Repeat-buyer summary with names removed |
| `analysis_2026_homebuyer_watchlist.csv` | Early 2026 screening table |
| `source_coverage_audit.csv` | Source coverage and caveat summary |

## 5. Lifecycle funnel interpretation

The lifecycle funnel should be interpreted carefully because source coverage differs by year.

Publication-stage funnel analysis is strongest for years where the Affidavit of Publication data is available and usable, especially 2021–2025. Earlier years are included for final-order and sale outcomes, but publication-stage source coverage is incomplete.

Rates may exceed 100% in some years where OCR missed publication records, where a source layer is incomplete, or where a later-stage document contains parcels not captured by the earlier-stage parser. These cases should be treated as source-coverage caveats rather than literal real-world rates.

A recommended final-report framing:

> The funnel is useful for understanding attrition across stages, but it should not yet be treated as a complete legal event history for every parcel in every year. The most reliable conclusions come from confirmed sale records and from years where publication and final-order coverage are both strong.

## 6. Auction competitiveness

The auction competitiveness table compares minimum bids with winning sale prices.

Important metrics:

| Metric | Meaning |
|---|---|
| `minimum_bid` | Starting bid / legal minimum |
| `selling_price` | Winning auction price |
| `bid_multiple` | Selling price divided by minimum bid |
| `winning_bid_premium` | Selling price minus minimum bid |

The public report should emphasize that minimum bids are often misleading for buyers. A parcel with a low minimum bid can still sell for many times that amount.

Suggested wording:

> Minimum bid is not market price. In many Snohomish County tax foreclosure auctions, winning bids substantially exceeded the listed minimum bid. Anyone using minimum bid as a proxy for affordability would likely underestimate actual auction competition.

## 7. Repeat-buyer analysis

The repeat-buyer table helps show whether the auction market is dominated by one-time buyers or recurring participants.

Current outputs are designed so names can be removed later:

| File | Use |
|---|---|
| `analysis_repeat_buyer_summary_with_names.csv` | Internal/reproducible version with buyer names |
| `analysis_repeat_buyer_summary_public_safe.csv` | Public-safe version with generic display names and hashed buyer IDs |

Recommended public framing:

> A small number of repeat purchasers appear across multiple auction years, suggesting that Snohomish tax foreclosure auctions attract both one-off buyers and specialized participants. The public-safe version of this analysis can show concentration patterns without publishing buyer names in the narrative report.

## 8. 2026 opportunity watchlist

The 2026 watchlist is an early screening tool built from Certificate-stage records. It is not a recommendation list.

The scoring lens is a flexible first-time homebuyer:

```text
Ideal: 2–3 bedrooms / 2 bathrooms
Preferred: house
Also interesting: condos and townhomes
Flexible: rural or less conventional locations
Higher caution: vacant land, commercial/non-residential properties, unusually low assessed value
```

Current limitations:

- beds and bathrooms are not yet loaded;
- building size and year built are not yet loaded;
- condition is unknown;
- occupancy is unknown;
- HOA status is unknown for condos;
- financing constraints are unknown;
- parcel geometry, access, utilities, septic, and hazards are not yet integrated.

Suggested wording:

> The 2026 watchlist should be treated as a prioritization aid for due diligence. It identifies parcels that may be worth looking up in the Assessor or SCOPI system, but it should not be interpreted as a purchase recommendation.

## 9. What data would improve the analysis most?

The highest-value next data layer is Assessor / parcel enrichment.

Priority fields:

| Field | Why it matters |
|---|---|
| beds | Required for first-time-homebuyer fit |
| baths | Required for first-time-homebuyer fit |
| building square feet | Helps separate livable homes from odd parcels |
| year built | Proxy for condition and repair risk |
| property class | Better residential/condo/land/commercial classification |
| situs address | Improves location screening |
| gross acres | Flags large/rural/land-like parcels |
| market value | Better affordability proxy than source-document value alone |
| land value / improvement value | Helps identify land-only or structure-heavy parcels |
| parcel geometry or lat/lon | Enables mapping and hazard joins |
| prior sale date / sale history | Helps identify unusual ownership or valuation patterns |

After assessor data, the next most useful layers are:

- zoning;
- urban growth area / incorporated area;
- floodplain;
- wetlands and stream buffers;
- steep slopes / landslide risk;
- shoreline jurisdiction;
- road access / frontage;
- utility or septic indicators;
- permits and code enforcement records.

## 10. Known limitations

This project should be transparent about its current limits.

### OCR limitations

Some source documents are scanned PDFs with difficult layouts. OCR can miss records, merge records, misread parcel numbers, or fail to capture owner/legal text. The project preserves review flags rather than silently treating every OCR row as perfect.

### 2020 Affidavit gap

The 2020 Affidavit of Publication did not produce usable records in the first OCR pass. It is marked as a future layout-review task rather than blocking the rest of the analysis.

### Certificate-stage coverage is partial

Certificate of Delinquency coverage is not yet complete across all years. Certificate-to-publication rates should not yet be presented as complete historical rates.

### Property characteristics are incomplete

The current lifecycle dataset contains some property-use and assessed-value fields from foreclosure documents, but it does not yet include a full Assessor join. Therefore, conclusions about bedrooms, bathrooms, property condition, livability, and exact homebuyer fit must wait for enrichment.

### Public-record names

Buyer and property-owner names appear in some public source records. The project may preserve names in reproducible data outputs, but the public narrative can use public-safe tables where appropriate.

## 11. Suggested final report structure

The final public-facing write-up could use this structure:

1. **What this project is**
2. **How tax foreclosure records were connected**
3. **Data coverage and caveats**
4. **How often parcels move from publication to final order to sale**
5. **Why minimum bids are misleading**
6. **Repeat-buyer patterns**
7. **2026 opportunity watchlist from a first-time-homebuyer lens**
8. **Future work: assessor/GIS enrichment**
9. **How to reproduce the data pipeline**

## 12. Reproducibility

The pipeline is designed to be reproducible from public PDFs stored locally in `data/raw`.

Important commands:

```powershell
python -m src.inventory.build_source_inventory
python -m src.extract.parse_machine_readable_stage_records
python -m src.extract.ocr_scanned_final_orders
python -m src.extract.ocr_scanned_affidavits
python -m src.transform.build_unified_lifecycle
python -m src.analysis.build_coverage_audit
python -m src.analysis.build_analysis_outputs
python -m src.analysis.build_2026_watchlist
```

Generated public outputs are written to:

```text
outputs/public
```

Private OCR caches are written to:

```text
data/private
```

## 13. Public-use note

Buyer and property-owner names in this dataset were transcribed from publicly available Snohomish County tax-foreclosure records. This dataset is provided for historical research, public-interest analysis, education, and reproducibility. It is not intended to be used as a marketing, solicitation, lead-generation, or contact list. Users are responsible for complying with RCW 42.56.070(8) and any other applicable law.
