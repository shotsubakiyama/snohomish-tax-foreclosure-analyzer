# Affidavit Merge Methodology

OCR Affidavit rows are merged as `publication` stage records.

This merge deliberately avoids over-cleaning OCR edge cases. Duplicate OCR
source keys are excluded. Nonduplicate review rows are retained with review
flags so the lifecycle table can be useful now while still exposing source
quality.

The 2020 Affidavit did not yield usable OCR records in the first pass and is
marked as pending future layout review rather than blocking the pipeline.
