# Source Inventory Methodology

The inventory script scans every PDF under `data/raw/`.

It does not alter or rename source files. It records:

- source family based on folder
- inferred year from filename and extracted text
- page count and file size
- percentage of pages with searchable text
- parcel-number pattern counts
- status phrases such as `PAID IN FULL` and `ADMINISTRATIVELY PULLED`
- review flags for documents that are likely scanned or ambiguous

Low text coverage is expected for scanned county filings. Those records are
not considered bad sources; they are simply routed to a later manual or OCR
review step.

Run from the repository root:

```powershell
python -m src.inventory.build_source_inventory
```
