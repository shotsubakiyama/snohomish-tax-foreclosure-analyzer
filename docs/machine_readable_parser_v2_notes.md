# Machine-Readable Parser Version 2

Version 2 parses each searchable PDF as a continuous document instead of
splitting records independently on every page.

This matters because county records commonly begin at the bottom of one page
and continue onto the next. The first parser could therefore find a parcel
number but miss its legal description or owner fields.

Version 2:

- joins page-spanning records;
- captures multi-line fields;
- records start and end page numbers;
- retains a review flag for page-spanning records;
- overwrites the same public output files produced by version 1.

Run:

```powershell
python -m src.extract.parse_machine_readable_stage_records
```
