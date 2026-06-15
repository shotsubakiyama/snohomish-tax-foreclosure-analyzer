# Scanned Affidavit OCR

This parser processes image-only Affidavits of Publication and skips affidavit
files already represented in the machine-readable stage-record output.

Run:

```powershell
python -m src.extract.ocr_scanned_affidavits
```

The first run may take several minutes. OCR text is cached under:

```text
data/private/ocr_cache/affidavits
```

Public outputs:

- `ocr_affidavit_records.csv`
- `ocr_affidavit_records.xlsx`
- `ocr_affidavit_review_queue.csv`
- `ocr_affidavit_file_summary.csv`
