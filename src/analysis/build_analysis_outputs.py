"""Build analysis outputs from the unified Snohomish parcel lifecycle dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"
DOCS_DIR = PROJECT_ROOT / "docs"

LIFECYCLE_PATH = OUTPUT_DIR / "unified_parcel_lifecycle.csv"


def classify_property(use_description: object, use_code: object) -> str:
    text = f"{use_description or ''} {use_code or ''}".lower()

    if any(
        term in text
        for term in [
            "single family",
            "two family",
            "duplex",
            "residence",
            "manufactured home",
        ]
    ):
        return "Improved residential"

    if any(term in text for term in ["condo", "condominium"]):
        return "Condo"

    if any(
        term in text
        for term in [
            "vacant",
            "undeveloped",
            "recreational lot",
            "recreational",
            "land",
        ]
    ):
        return "Vacant / recreational land"

    if any(
        term in text
        for term in [
            "commercial",
            "non residential",
            "retail",
            "office",
            "industrial",
            "warehouse",
        ]
    ):
        return "Commercial / industrial"

    if text.strip():
        return "Other / unclear"

    return "Unknown"


def safe_rate(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Return a rounded rate, leaving zero-denominator rows blank."""
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")

    rate = numerator / denominator.mask(denominator == 0)
    return rate.round(3)


def main() -> None:
    if not LIFECYCLE_PATH.exists():
        raise FileNotFoundError(
            f"Missing lifecycle file: {LIFECYCLE_PATH}. "
            "Run python -m src.transform.build_unified_lifecycle first."
        )

    df = pd.read_csv(LIFECYCLE_PATH, dtype={"parcel_number": "string"})

    bool_cols = [
        "certificate_listed_flag",
        "publication_listed_flag",
        "final_order_flag",
        "sold_flag",
        "county_acquired_flag",
        "private_purchaser_flag",
        "paid_in_full_flag",
        "administratively_pulled_flag",
        "redeemed_flag",
        "ocr_review_required_flag",
        "ocr_repair_applied_flag",
    ]

    for col in bool_cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype("string")
                .str.lower()
                .map({"true": True, "false": False})
                .fillna(False)
                .astype(bool)
            )

    money_cols = [
        "minimum_bid",
        "selling_price",
        "winning_bid_premium",
        "bid_multiple",
        "total_assessed_value",
        "excess_funds",
    ]

    for col in money_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["property_category_simple"] = df.apply(
        lambda row: classify_property(
            row.get("use_description"),
            row.get("use_code"),
        ),
        axis=1,
    )

    annual_funnel = (
        df.groupby("auction_year", as_index=False)
        .agg(
            parcel_year_records=("parcel_year_id", "count"),
            certificates=("certificate_listed_flag", "sum"),
            publications=("publication_listed_flag", "sum"),
            final_orders=("final_order_flag", "sum"),
            sold=("sold_flag", "sum"),
            county_acquired=("county_acquired_flag", "sum"),
            private_sales=("private_purchaser_flag", "sum"),
            paid_or_redeemed=(
                "lifecycle_outcome",
                lambda values: (values == "paid_or_redeemed").sum(),
            ),
            administratively_pulled=("administratively_pulled_flag", "sum"),
            ocr_review_flagged=("ocr_review_required_flag", "sum"),
            ocr_repaired_apn=("ocr_repair_applied_flag", "sum"),
        )
        .sort_values("auction_year")
    )

    annual_funnel["publication_to_final_order_rate"] = safe_rate(
        annual_funnel["final_orders"],
        annual_funnel["publications"],
    )
    annual_funnel["final_order_to_sale_rate"] = safe_rate(
        annual_funnel["sold"],
        annual_funnel["final_orders"],
    )
    annual_funnel["publication_to_sale_rate"] = safe_rate(
        annual_funnel["sold"],
        annual_funnel["publications"],
    )

    sold = df[df["sold_flag"]].copy()

    competitiveness = (
        sold.groupby("auction_year", as_index=False)
        .agg(
            sales=("parcel_year_id", "count"),
            total_minimum_bid=("minimum_bid", "sum"),
            total_selling_price=("selling_price", "sum"),
            median_minimum_bid=("minimum_bid", "median"),
            median_selling_price=("selling_price", "median"),
            median_bid_multiple=("bid_multiple", "median"),
            average_bid_multiple=("bid_multiple", "mean"),
            max_bid_multiple=("bid_multiple", "max"),
            median_winning_bid_premium=("winning_bid_premium", "median"),
            total_winning_bid_premium=("winning_bid_premium", "sum"),
        )
        .round(3)
    )

    property_type_summary = (
        df.groupby(["auction_year", "property_category_simple"], as_index=False)
        .agg(
            parcel_year_records=("parcel_year_id", "count"),
            publications=("publication_listed_flag", "sum"),
            final_orders=("final_order_flag", "sum"),
            sold=("sold_flag", "sum"),
            median_assessed_value=("total_assessed_value", "median"),
            median_minimum_bid=("minimum_bid", "median"),
            median_selling_price=("selling_price", "median"),
        )
        .sort_values(
            ["auction_year", "parcel_year_records"],
            ascending=[True, False],
        )
    )

    buyer = (
        sold.groupby("buyer_name", as_index=False)
        .agg(
            purchase_count=("parcel_year_id", "count"),
            first_purchase_year=("auction_year", "min"),
            most_recent_purchase_year=("auction_year", "max"),
            years_active=("auction_year", "nunique"),
            total_winning_bids=("selling_price", "sum"),
            median_winning_bid=("selling_price", "median"),
            median_bid_multiple=("bid_multiple", "median"),
            max_bid_multiple=("bid_multiple", "max"),
        )
        .sort_values(
            ["purchase_count", "total_winning_bids"],
            ascending=[False, False],
        )
    )
    buyer["repeat_buyer_flag"] = buyer["purchase_count"] > 1

    top_bid_multiples = (
        sold.sort_values("bid_multiple", ascending=False)
        .head(50)
        [
            [
                "auction_year",
                "sale_number",
                "parcel_number",
                "situs_address",
                "use_description",
                "minimum_bid",
                "selling_price",
                "bid_multiple",
                "winning_bid_premium",
                "buyer_name",
                "source_page_refs",
            ]
        ]
    )

    review_flags = df[
        df["ocr_review_required_flag"] | df["ocr_repair_applied_flag"]
    ].copy()

    review_flags = review_flags[
        [
            "auction_year",
            "parcel_number",
            "stage_types_present",
            "lifecycle_outcome",
            "ocr_review_required_flag",
            "ocr_repair_applied_flag",
            "ocr_review_reasons",
            "source_page_refs",
            "situs_address",
            "use_description",
        ]
    ].sort_values(["auction_year", "parcel_number"])

    annual_funnel.to_csv(
        OUTPUT_DIR / "analysis_annual_funnel.csv",
        index=False,
    )
    competitiveness.to_csv(
        OUTPUT_DIR / "analysis_auction_competitiveness_by_year.csv",
        index=False,
    )
    property_type_summary.to_csv(
        OUTPUT_DIR / "analysis_property_type_summary.csv",
        index=False,
    )
    buyer.to_csv(
        OUTPUT_DIR / "analysis_repeat_buyer_summary.csv",
        index=False,
    )
    top_bid_multiples.to_csv(
        OUTPUT_DIR / "analysis_top_bid_multiples.csv",
        index=False,
    )
    review_flags.to_csv(
        OUTPUT_DIR / "analysis_review_flags.csv",
        index=False,
    )

    with pd.ExcelWriter(
        OUTPUT_DIR / "snohomish_analysis_outputs.xlsx",
        engine="openpyxl",
    ) as writer:
        annual_funnel.to_excel(
            writer,
            sheet_name="Annual Funnel",
            index=False,
        )
        competitiveness.to_excel(
            writer,
            sheet_name="Competitiveness",
            index=False,
        )
        property_type_summary.to_excel(
            writer,
            sheet_name="Property Types",
            index=False,
        )
        buyer.to_excel(
            writer,
            sheet_name="Repeat Buyers",
            index=False,
        )
        top_bid_multiples.to_excel(
            writer,
            sheet_name="Top Bid Multiples",
            index=False,
        )
        review_flags.to_excel(
            writer,
            sheet_name="Review Flags",
            index=False,
        )

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
                    48,
                )
                worksheet.column_dimensions[
                    cells[0].column_letter
                ].width = width

    notes = """# Analysis Output Notes

These analysis outputs are derived from `outputs/public/unified_parcel_lifecycle.csv`.

## Generated tables

- `analysis_annual_funnel.csv`: certificate/publication/final-order/sale counts by year.
- `analysis_auction_competitiveness_by_year.csv`: sale prices, bid multiples, and winning-bid premiums.
- `analysis_property_type_summary.csv`: lifecycle counts by simplified property category.
- `analysis_repeat_buyer_summary.csv`: buyer concentration and repeat-buyer activity.
- `analysis_top_bid_multiples.csv`: highest sale-price-to-minimum-bid examples.
- `analysis_review_flags.csv`: parcel-years that still have OCR caveats.

## Caveats

The funnel is strongest from Publication → Final Order → Sale for years with usable publication data. The 2020 Affidavit remains pending OCR/layout review. Certificate-stage coverage is partial, so certificate-to-publication rates should not yet be presented as complete historical rates.

Blank rate fields generally mean the denominator was zero or unavailable for that year.

## Suggested report framing

Use the funnel and competitiveness tables as the first public-facing analysis. Treat certificate-stage counts, OCR review flags, repaired APNs, and assessor/GIS overlays as future-version notes rather than blockers.
"""

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "analysis_outputs_notes.md").write_text(
        notes,
        encoding="utf-8",
    )

    print("Wrote analysis outputs:")
    print(f"- {OUTPUT_DIR / 'snohomish_analysis_outputs.xlsx'}")
    print(f"- {OUTPUT_DIR / 'analysis_annual_funnel.csv'}")
    print(f"- {OUTPUT_DIR / 'analysis_auction_competitiveness_by_year.csv'}")
    print(f"- {OUTPUT_DIR / 'analysis_property_type_summary.csv'}")
    print(f"- {OUTPUT_DIR / 'analysis_repeat_buyer_summary.csv'}")
    print(f"- {OUTPUT_DIR / 'analysis_top_bid_multiples.csv'}")
    print(f"- {OUTPUT_DIR / 'analysis_review_flags.csv'}")
    print()
    print("Snapshot:")
    print(annual_funnel.to_string(index=False))


if __name__ == "__main__":
    main()