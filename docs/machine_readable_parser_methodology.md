# Machine-Readable Stage Parser

This parser processes searchable text in:

- Certificates of Delinquency
- Affidavits of Publication
- Final Orders of Sale

It deliberately skips image-only pages rather than attempting broad OCR.

## Output files

- `machine_readable_stage_records.csv`
- `machine_readable_stage_records.xlsx`
- `machine_readable_stage_file_summary.csv`
- `machine_readable_stage_review_queue.csv`

## Design principles

- Preserve raw record text.
- Preserve source filename and page number.
- Extract more fields than the current report requires.
- Mark missing or ambiguous records for review.
- Never infer a paid, redeemed, or pulled status unless the source text says so.
- Treat this as a first-pass parser, not final publication-quality data.

## Next phase

Once this output is reviewed, the parsed rows will be normalized and merged into
the parcel lifecycle table. Image-only PDFs will then be processed using a
targeted review approach.
