"""Build 2026 opportunity-watchlist and public-safe repeat-buyer outputs.

The 2026 table is an early-stage watchlist, not a recommendation list. It uses
Certificate of Delinquency rows currently available in the lifecycle dataset and
scores them from the perspective of a flexible first-time homebuyer who prefers
a 2–3 bedroom / 2 bath home, but is also open to condos and selected non-SFR
opportunities.

Bedrooms/bathrooms are not yet loaded, so the score is intentionally modest and
transparent. Future assessor enrichment should replace the placeholder fit
logic.
"""

from __future__ import annotations

from pathlib import Path
import hashlib

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"
DOCS_DIR = PROJECT_ROOT / "docs"

LIFECYCLE_PATH = OUTPUT_DIR / "unified_parcel_lifecycle.csv"
REPEAT_BUYER_PATH = OUTPUT_DIR / "analysis_repeat_buyer_summary.csv"


def coerce_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.lower()
        .map({"true": True, "false": False})
        .fillna(False)
        .astype(bool)
    )


def classify_fit(use_description: object, use_code: object) -> tuple[str, int, str]:
    text = f"{use_description or ''} {use_code or ''}".lower()

    # Negative / non-home signals first.
    # Important: check this before generic "residential" because
    # "non-residential" contains the substring "residential".
    if any(
        term in text
        for term in [
            "non-residential",
            "non residential",
            "commercial",
            "industrial",
            "retail",
            "office",
            "warehouse",
        ]
    ):
        return (
            "Commercial / non-residential",
            5,
            "Probably not aligned with a first-time-homebuyer housing target.",
        )

    # Condo/attached residential before generic single-family text because
    # some source descriptions contain both "Single Family Residence" and
    # "Condominium".
    if any(
        term in text
        for term in ["condo", "condominium", "townhouse", "townhome"]
    ):
        return (
            "Condo / attached residential",
            38,
            "Condo/attached housing may fit the flexible target; verify HOA, financing, occupancy, rental restrictions, and special assessments.",
        )

    if any(
        term in text
        for term in [
            "single family",
            "residence",
            "residential",
            "manufactured home",
            "mobile home",
        ]
    ):
        return (
            "Likely residential home",
            45,
            "Potentially closest to first-time-homebuyer house target; verify bedrooms, bathrooms, condition, occupancy, and financing constraints.",
        )

    if any(
        term in text
        for term in ["vacant", "undeveloped", "recreational", "land", "lot"]
    ):
        return (
            "Vacant / land-like",
            18,
            "Could be interesting only with parcel due diligence; not a first-time-homebuyer dwelling without buildability, utilities, access, and permitting review.",
        )

    return (
        "Unknown / needs assessor check",
        25,
        "Insufficient property-type signal; needs assessor lookup before screening.",
    )


def affordability_score(value: object) -> int:
    """Simple assessed-value signal. This is not market value."""
    v = pd.to_numeric(value, errors="coerce")

    if pd.isna(v):
        return 10

    if v <= 50_000:
        # Very low assessed value is not automatically good. It may signal
        # partial interests, odd parcels, mobile-home/site issues, or bad data.
        return 15

    if v <= 250_000:
        return 25

    if v <= 450_000:
        return 20

    if v <= 700_000:
        return 12

    return 5


def assessed_value_caution(value: object) -> str:
    v = pd.to_numeric(value, errors="coerce")

    if pd.isna(v):
        return "Assessed value missing; verify with Assessor."

    if v <= 50_000:
        return (
            "Very low assessed value; high caution. Could indicate odd parcel, "
            "partial interest, land-only component, mobile-home/site issue, or source-value mismatch."
        )

    if v <= 250_000:
        return "Lower assessed-value signal; still verify structure, condition, access, and occupancy."

    if v <= 450_000:
        return "Moderate assessed-value signal; verify market value and financing constraints."

    if v <= 700_000:
        return "Higher assessed-value signal; may still be viable depending on auction price."

    return "High assessed-value signal; likely less aligned with affordability unless unusual circumstances apply."


def risk_penalty(row: pd.Series) -> int:
    penalty = 0

    if bool(row.get("ocr_review_required_flag", False)):
        penalty += 5

    if bool(row.get("ocr_repair_applied_flag", False)):
        penalty += 5

    if bool(row.get("sale_does_not_include_flag", False)):
        penalty += 20

    if bool(row.get("subject_to_flag", False)):
        penalty += 10

    if bool(row.get("must_be_sold_with_flag", False)):
        penalty += 10

    special = str(row.get("special_condition_text") or "").lower()

    if "does not include" in special or "not included" in special:
        penalty += 20

    if "subject to" in special:
        penalty += 10

    if "must be sold with" in special:
        penalty += 10

    return penalty


def status_note(row: pd.Series) -> str:
    if bool(row.get("final_order_flag", False)):
        return "Reached Final Order stage."

    if bool(row.get("publication_listed_flag", False)):
        return "Reached Publication stage."

    if bool(row.get("certificate_listed_flag", False)):
        return "Certificate-stage only so far; monitor for publication/final-order movement."

    return "Stage unknown."


def buyer_hash(name: object) -> str:
    text = str(name or "").strip().lower()

    if not text:
        return ""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def main() -> None:
    if not LIFECYCLE_PATH.exists():
        raise FileNotFoundError(
            f"Missing lifecycle file: {LIFECYCLE_PATH}. "
            "Run build_unified_lifecycle first."
        )

    df = pd.read_csv(LIFECYCLE_PATH, dtype={"parcel_number": "string"})

    for col in [
        "certificate_listed_flag",
        "publication_listed_flag",
        "final_order_flag",
        "sold_flag",
        "ocr_review_required_flag",
        "ocr_repair_applied_flag",
        "sale_does_not_include_flag",
        "subject_to_flag",
        "must_be_sold_with_flag",
    ]:
        if col in df.columns:
            df[col] = coerce_bool(df[col])

    for col in [
        "land_value",
        "improvement_value",
        "total_assessed_value",
        "amount_due",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    watch = df[
        (pd.to_numeric(df["auction_year"], errors="coerce") == 2026)
        & df["certificate_listed_flag"]
    ].copy()

    fit_results = watch.apply(
        lambda row: classify_fit(
            row.get("use_description"),
            row.get("use_code"),
        ),
        axis=1,
    )

    watch["homebuyer_fit_category"] = [x[0] for x in fit_results]
    watch["homebuyer_fit_base_score"] = [x[1] for x in fit_results]
    watch["homebuyer_fit_note"] = [x[2] for x in fit_results]

    watch["assessed_value_signal_score"] = watch[
        "total_assessed_value"
    ].apply(affordability_score)

    watch["assessed_value_caution"] = watch[
        "total_assessed_value"
    ].apply(assessed_value_caution)

    watch["risk_penalty"] = watch.apply(risk_penalty, axis=1)

    watch["early_watch_score"] = (
        watch["homebuyer_fit_base_score"]
        + watch["assessed_value_signal_score"]
        - watch["risk_penalty"]
    ).clip(lower=0, upper=100)

    watch["current_stage_note"] = watch.apply(status_note, axis=1)

    watch["next_due_diligence_step"] = (
        "Look up parcel in Assessor/SCOPI; verify situs, property class, beds/baths, "
        "building sqft, year built, occupancy, access, utilities/septic, liens, "
        "and whether the parcel remains active."
    )

    watch["bed_bath_status"] = (
        "Not yet loaded; future assessor enrichment needed."
    )

    preferred_cols = [
        "early_watch_score",
        "homebuyer_fit_category",
        "auction_year",
        "parcel_number",
        "situs_address",
        "use_description",
        "use_code",
        "bed_bath_status",
        "land_value",
        "improvement_value",
        "total_assessed_value",
        "assessed_value_caution",
        "amount_due",
        "tax_years",
        "certificate_listed_flag",
        "publication_listed_flag",
        "final_order_flag",
        "sold_flag",
        "current_stage_note",
        "homebuyer_fit_note",
        "next_due_diligence_step",
        "ocr_review_required_flag",
        "ocr_repair_applied_flag",
        "ocr_review_reasons",
        "source_page_refs",
        "source_filenames",
    ]

    for col in preferred_cols:
        if col not in watch.columns:
            watch[col] = pd.NA

    watch = watch[preferred_cols].sort_values(
        ["early_watch_score", "total_assessed_value"],
        ascending=[False, True],
        na_position="last",
    )

    watch.to_csv(
        OUTPUT_DIR / "analysis_2026_homebuyer_watchlist.csv",
        index=False,
    )

    # Repeat-buyer outputs: one with names, one public-safe.
    if REPEAT_BUYER_PATH.exists():
        buyers = pd.read_csv(REPEAT_BUYER_PATH)
        buyers["buyer_hash"] = buyers["buyer_name"].apply(buyer_hash)
        buyers["buyer_display_name"] = buyers.apply(
            lambda row: f"Buyer {row.name + 1:03d}",
            axis=1,
        )

        public_cols = [
            "buyer_display_name",
            "buyer_hash",
            "purchase_count",
            "first_purchase_year",
            "most_recent_purchase_year",
            "years_active",
            "total_winning_bids",
            "median_winning_bid",
            "median_bid_multiple",
            "max_bid_multiple",
            "repeat_buyer_flag",
        ]

        for col in public_cols:
            if col not in buyers.columns:
                buyers[col] = pd.NA

        buyers.to_csv(
            OUTPUT_DIR / "analysis_repeat_buyer_summary_with_names.csv",
            index=False,
        )
        buyers[public_cols].to_csv(
            OUTPUT_DIR / "analysis_repeat_buyer_summary_public_safe.csv",
            index=False,
        )
    else:
        buyers = pd.DataFrame()
        public_cols = []

    with pd.ExcelWriter(
        OUTPUT_DIR / "snohomish_2026_watchlist_and_public_safe_outputs.xlsx",
        engine="openpyxl",
    ) as writer:
        watch.to_excel(
            writer,
            sheet_name="2026 Watchlist",
            index=False,
        )

        if not buyers.empty:
            buyers.to_excel(
                writer,
                sheet_name="Repeat Buyers With Names",
                index=False,
            )
            buyers[public_cols].to_excel(
                writer,
                sheet_name="Repeat Buyers Public Safe",
                index=False,
            )

        notes = pd.DataFrame(
            [
                [
                    "Purpose",
                    "Early 2026 watchlist from Certificate-stage records.",
                ],
                [
                    "User lens",
                    "Flexible first-time homebuyer; ideal 2–3 bed / 2 bath; house preferred; condos also interesting.",
                ],
                [
                    "Major caveat",
                    "Bedrooms and bathrooms are not yet loaded; score uses source-document property-type text only.",
                ],
                [
                    "Assessed-value caveat",
                    "Very low assessed values are not automatically good and may indicate odd parcels or source-value issues.",
                ],
                [
                    "Public names",
                    "Repeat-buyer outputs include both named and public-safe versions.",
                ],
                [
                    "Not investment advice",
                    "Watchlist is a screening tool only and requires parcel-level due diligence.",
                ],
            ],
            columns=["Field", "Value"],
        )

        notes.to_excel(writer, sheet_name="README", index=False)

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions

            for cells in worksheet.columns:
                width = min(
                    max(
                        max(
                            len(str(cell.value))
                            if cell.value is not None
                            else 0
                            for cell in cells
                        )
                        + 2,
                        11,
                    ),
                    60,
                )
                worksheet.column_dimensions[
                    cells[0].column_letter
                ].width = width

    notes_md = """# 2026 Opportunity Watchlist and Public-Safe Buyer Outputs

## 2026 watchlist framing

The 2026 table is an early-stage watchlist built from Certificate of Delinquency
records currently loaded into the lifecycle table. It is not a recommendation
list.

The scoring lens is a flexible first-time homebuyer:

- ideal target: 2–3 bedrooms and 2 bathrooms;
- house preferred;
- condos/townhomes still interesting;
- rural or less conventional properties are not automatically excluded.

Current limitation: beds, bathrooms, building area, condition, occupancy, HOA
status, utilities, septic, and parcel geometry are not yet loaded. Those should
come from future assessor/GIS enrichment.

Very low assessed values are not automatically attractive. They may indicate
partial interests, odd parcels, source-value issues, mobile-home/site issues,
land-only components, or other risks that require parcel-level verification.

## Repeat-buyer names

The project currently keeps buyer names because they appear in public Return of
Sale records and are useful for reproducibility. However, the output also
includes a public-safe repeat-buyer table with stable hashed buyer IDs and
generic display names. This makes it easy to remove names from the public report
later while preserving concentration and repeat-participant analysis.

## Future data that would materially improve the watchlist

- Assessor parcel/building attributes: beds, baths, building sqft, year built,
  property class, land/improvement values, situs address, and prior sale.
- GIS geometry: parcel shape, road frontage, access, incorporated area, UGA,
  zoning, and future land use.
- Hazard/environment overlays: floodplain, wetland, stream buffer, steep slope,
  shoreline jurisdiction, and landslide risk.
- Utility/septic indicators where available.
- Permit/code records: recent permits, code enforcement, demolition, unsafe
  structures, and septic/health notes.
- Manual image review from assessor photos, aerial imagery, and street view.

These should be future-version enhancements, not blockers for the current
lifecycle analysis.
"""

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (
        DOCS_DIR / "2026_watchlist_and_public_safe_buyers.md"
    ).write_text(
        notes_md,
        encoding="utf-8",
    )

    print("Wrote 2026 opportunity and public-safe buyer outputs:")
    print(f"- {OUTPUT_DIR / 'analysis_2026_homebuyer_watchlist.csv'}")
    print(
        f"- {OUTPUT_DIR / 'analysis_repeat_buyer_summary_with_names.csv'}"
    )
    print(
        f"- {OUTPUT_DIR / 'analysis_repeat_buyer_summary_public_safe.csv'}"
    )
    print(
        f"- {OUTPUT_DIR / 'snohomish_2026_watchlist_and_public_safe_outputs.xlsx'}"
    )
    print(f"- {DOCS_DIR / '2026_watchlist_and_public_safe_buyers.md'}")
    print()
    print("2026 watchlist snapshot:")

    if watch.empty:
        print("No 2026 certificate-stage records found.")
    else:
        print(
            watch[
                [
                    "early_watch_score",
                    "homebuyer_fit_category",
                    "parcel_number",
                    "situs_address",
                    "use_description",
                    "total_assessed_value",
                    "amount_due",
                ]
            ]
            .head(20)
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()