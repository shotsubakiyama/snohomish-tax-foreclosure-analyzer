# Final Order OCR Version 4

Version 4 supports APN-prefixed records, OCR-missing leading zeros, owner-label
variants, and common OCR misspellings such as `LEINHOLDERS`.

A 13-digit APN is repaired only by prepending a zero and is always placed in
the review queue. Both the raw and normalized parcel values are retained.
