# Unified Lifecycle Methodology

The unified lifecycle model uses two public layers.

## Stage Events

One row per parsed source record. This preserves the source-oriented record,
page references, raw record text, and extraction method.

## Parcel Lifecycle

One row per auction year and parcel number. Descriptive property fields are
selected from the latest available foreclosure stage, while all source files
and page references remain listed.

## Conservative interpretation

The current searchable stage coverage is incomplete by year. An absent stage
flag in a scanned year is not treated as proof that the parcel skipped that
stage.

Lifecycle outcomes are therefore limited to directly supported states:

- sold to private purchaser;
- county acquired;
- explicitly paid/redeemed;
- explicitly administratively pulled;
- reached final order;
- published;
- certificate only;
- unknown.

Scanned-source extraction will expand historical stage coverage later.
