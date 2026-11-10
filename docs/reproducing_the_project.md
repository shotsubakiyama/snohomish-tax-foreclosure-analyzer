# Reproducing the project

This page contains the technical steps used to rebuild the public outputs from the source records.

## Requirements

- Python
- pandas
- matplotlib
- openpyxl
- Tesseract OCR for scanned foreclosure documents

Raw public-source PDFs are stored locally under `data/raw/` and are intentionally not committed to the repository.

## Pipeline

From the repository root:

```powershell
python -m src.inventory.build_source_inventory
python -m src.extract.parse_machine_readable_stage_records
python -m src.extract.ocr_scanned_final_orders
python -m src.extract.ocr_scanned_affidavits
python -m src.transform.build_unified_lifecycle
python -m src.analysis.build_coverage_audit
python -m src.analysis.build_analysis_outputs
python -m src.analysis.build_report_graphs
```

The main transformation is `src/transform/build_unified_lifecycle.py`. It standardizes parcel numbers, links stage records by parcel and auction year, preserves source references and OCR-review flags, and joins auction-sale and excess-funds records.
