# Report Graphs Methodology

This script generates static PNG charts for the README and report draft.

Run:

```powershell
python -m src.analysis.build_report_graphs
```

Outputs:

- `docs/assets/lifecycle_funnel_by_year.png`
- `docs/assets/median_bid_multiple_by_year.png`
- `docs/assets/minimum_bid_vs_sale_price.png`
- `docs/assets/2026_watchlist_by_category.png`
- `docs/assets/repeat_buyer_concentration.png`
- `docs/readme_graphs_and_insights_snippet.md`

The charts are intentionally simple and report-oriented. They are not meant to
replace the CSV/XLSX outputs.
