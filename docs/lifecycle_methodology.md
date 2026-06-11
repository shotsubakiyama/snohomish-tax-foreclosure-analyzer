# Lifecycle Seed

This step creates the first parcel lifecycle table from records already
verified in the project.

## What is confirmed now

- Every row appeared in a Return of Sale.
- `sold_flag = true`.
- County acquisitions are identified separately from private purchases.
- Exact reported excess-funds records are joined for 2024 and 2025.

## What remains intentionally unknown

The initial table includes blank fields for:

- Certificate of Delinquency appearance
- Affidavit of Publication appearance
- Final Order appearance
- paid/redeemed before sale
- administratively pulled
- special conditions

Those will be populated in the next parsing phase rather than inferred.

## Why this structure is useful

The schema can grow without rewriting the existing public outputs. Each source
adds facts to the same parcel-year record, while retaining source and review
flags.
