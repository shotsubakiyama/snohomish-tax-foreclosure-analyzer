# Final Order Merge Methodology

The unified lifecycle now includes OCR-derived Final Order records from
2019–2025.

## Duplicate handling

Rows marked as duplicate source keys are excluded from the unified parcel-year
table. They remain available in the OCR review output.

## Review handling

Nonduplicate OCR rows remain in the lifecycle table even when a descriptive
field is missing. Their review and APN-repair flags remain visible.

## Field precedence

Machine-readable source values are preferred over OCR values when both exist
for the same parcel-year. OCR Final Orders provide historical coverage where
searchable source records are unavailable.
