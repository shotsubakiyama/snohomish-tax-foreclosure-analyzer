# Final Order OCR Version 3

Version 3 validates parcel anchors using nearby source context.

A 14-digit number is treated as a new record only when a taxpayer or owner
label appears within the next 400 characters. This captures varying exhibit
layouts while avoiding parcel numbers referenced inside legal descriptions
or notes.

The full OCR text remains in CSV. Excel display text is trimmed to avoid
Excel's 32,767-character cell limit.
