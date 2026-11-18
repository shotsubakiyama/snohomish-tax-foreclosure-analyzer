# Agent instructions — Snohomish County Tax Foreclosure Analyzer

## Purpose and scope
This is a **finished, point-in-time public-data research project**, not a live foreclosure listing or investment recommendation service. It reconstructs parcel-year foreclosure lifecycles from fragmented Snohomish County records (2019–2026 source coverage). The public audience includes readers interested in real estate and data engineering, plus technically sophisticated reviewers. Prioritize accurate interpretation, transparent provenance, and easy access to the published dataset.

## Sources and data model
- The stages are Certificate of Delinquency → Affidavit of Publication → Final Order of Sale → Return of Sale → Excess Funds (where available).
- Distinguish appearing in a stage from a **confirmed sale**. A missing stage record can reflect incomplete coverage, not that a property never passed that stage.
- Preserve parcel/year identifiers, source-document references, matching logic, OCR confidence/review flags, and coverage limitations.
- Do not infer that the minimum bid predicts final price: it is a legal auction threshold, not an estimate of market value.
- Do not present buyer names or parcel data as evidence of wrongdoing. Avoid exposing additional sensitive or unreviewed personal details.

## Code and publication
- `src/extract/`: machine-readable parsing and OCR.
- `src/transform/`: lifecycle and sale-output transformations.
- `src/analysis/`: summary tables, charts, and watchlist-related analyses.
- `src/inventory/`: source inventory.
- `outputs/public/`: published datasets; `docs/`: methods, coverage notes, and figure assets.
- The README's Excel download is a primary deliverable. Preserve its working link and usable sheets when updating outputs.
- The project currently reports 790 parcel-year records and 124 confirmed sales; always recalculate figures from the latest actual outputs before changing counts.

## Editorial and visual standards
- Lead with what the data reveals: lifecycle attrition, minimum-bid versus winning-price multiples, sale-volume context, repeat-buyer concentration, and coverage caveats.
- Explain metrics in ordinary language. Label ratios and denominators clearly, with observation years and sample sizes.
- Avoid exaggerated conclusions, generic AI writing, or an overlong technical reproduction section on the landing page; detailed methodology belongs in linked docs.
- Charts must have interpretable axes, units, captions, and visible volume where needed. Check rendering and accessibility.

## Quality control
1. Inspect `README.md`, `data/source_manifest.csv`, and the relevant methodology document before changing extraction or interpretation.
2. Preserve source traceability and public-safe output conventions. Do not overwrite curated datasets with incomplete OCR runs.
3. Run relevant scripts and available tests where feasible; check row counts, unique parcel-year keys, joins, missingness, stage coverage, and price/bid arithmetic.
4. Validate all published CSV/JSON/XLSX outputs and README download links after regeneration; verify Excel sheet structure and charts.
5. Make changes in reviewable commits. Report the precise source files, outputs, tests, and limitations; do not claim that historical data is current.
