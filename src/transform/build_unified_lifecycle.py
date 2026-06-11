"""Merge OCR Final Order records into the unified parcel lifecycle dataset.

This extends the existing unified lifecycle with:
- scanned Final Order coverage for 2019–2025;
- OCR review and repair metadata;
- source page references;
- conservative field precedence.

Duplicate OCR source keys are excluded from the unified table but remain
available in the OCR review outputs.
"""

from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from src.data.auction_sales import sales
from src.data.excess_funds import excess_funds


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"

MACHINE_STAGE_PATH = OUTPUT_DIR / "machine_readable_stage_records.csv"
OCR_FINAL_ORDER_PATH = OUTPUT_DIR / "ocr_final_order_records.csv"


def normalize_parcel(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.replace(r"\D", "", regex=True)
        .str.zfill(14)
    )


def first_non_null(series: pd.Series):
    for value in series:
        if pd.isna(value):
            continue
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
        else:
            return value
    return pd.NA


def join_unique(series: pd.Series):
    values = []
    seen = set()
    for value in series:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            values.append(text)
    return " | ".join(values) if values else pd.NA


def load_machine_stage_events() -> pd.DataFrame:
    if not MACHINE_STAGE_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(
        MACHINE_STAGE_PATH,
        dtype={"parcel_number": "string"},
    )
    df["auction_year"] = pd.to_numeric(
        df["inferred_year"], errors="coerce"
    ).astype("Int64")
    df["parcel_number"] = normalize_parcel(df["parcel_number"])

    family_to_stage = {
        "certificates": "certificate",
        "affidavits": "publication",
        "final_orders": "final_order",
    }
    df["stage_type"] = df["document_family"].map(family_to_stage)
    df["source_kind"] = "machine_readable"
    df["source_quality_rank"] = 2
    df["ocr_review_required_flag"] = False
    df["ocr_repair_applied_flag"] = False
    df["ocr_review_reason"] = pd.NA

    # Harmonize page columns.
    if "source_start_page" not in df.columns and "source_page" in df.columns:
        df["source_start_page"] = df["source_page"]
    if "source_end_page" not in df.columns:
        df["source_end_page"] = df["source_start_page"]

    return df


def load_ocr_final_order_events() -> pd.DataFrame:
    if not OCR_FINAL_ORDER_PATH.exists():
        raise FileNotFoundError(
            f"Missing OCR Final Order records: {OCR_FINAL_ORDER_PATH}\n"
            "Run: python -m src.extract.ocr_scanned_final_orders"
        )

    df = pd.read_csv(
        OCR_FINAL_ORDER_PATH,
        dtype={
            "parcel_number": "string",
            "parcel_number_raw": "string",
        },
    )

    # Exclude duplicate source keys from the unified model.
    duplicate_mask = (
        df["duplicate_key_flag"]
        .astype("string")
        .str.lower()
        .eq("true")
    )
    df = df.loc[~duplicate_mask].copy()

    df["auction_year"] = pd.to_numeric(
        df["auction_year"], errors="coerce"
    ).astype("Int64")
    df["parcel_number"] = normalize_parcel(df["parcel_number"])
    df["stage_type"] = "final_order"
    df["document_family"] = "final_orders"
    df["source_kind"] = "ocr"
    df["source_quality_rank"] = 1

    df["sale_or_property_number"] = pd.to_numeric(
        df.get("property_number"), errors="coerce"
    ).astype("Int64")

    df["ocr_review_required_flag"] = (
        df["review_required_flag"]
        .astype("string")
        .str.lower()
        .eq("true")
    )
    df["ocr_repair_applied_flag"] = (
        df["parcel_repair_applied_flag"]
        .astype("string")
        .str.lower()
        .eq("true")
    )
    df["ocr_review_reason"] = df["review_reason"]

    # Keep source-oriented raw fields.
    df["raw_record_text"] = df.get("raw_ocr_text", pd.Series(dtype="object"))
    df["extraction_method"] = df.get(
        "extraction_method",
        pd.Series(dtype="object"),
    )

    return df


def harmonize_stage_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "stage_type",
        "document_family",
        "auction_year",
        "sale_or_property_number",
        "parcel_number",
        "taxpayer_name",
        "owner_record_text",
        "legal_description",
        "situs_address",
        "tca_code",
        "use_code",
        "use_description",
        "acreage",
        "land_value",
        "improvement_value",
        "tax_years",
        "amount_due",
        "amount_paid",
        "paid_in_full_flag",
        "administratively_pulled_flag",
        "redeemed_flag",
        "must_be_sold_with_flag",
        "sale_does_not_include_flag",
        "subject_to_flag",
        "special_condition_text",
        "source_filename",
        "source_start_page",
        "source_end_page",
        "source_relative_path",
        "source_kind",
        "source_quality_rank",
        "extraction_method",
        "ocr_review_required_flag",
        "ocr_repair_applied_flag",
        "ocr_review_reason",
        "raw_record_text",
    ]

    result = df.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = pd.NA
    return result[columns]


def build_stage_events() -> pd.DataFrame:
    machine = harmonize_stage_columns(load_machine_stage_events())
    ocr = harmonize_stage_columns(load_ocr_final_order_events())

    events = pd.concat([machine, ocr], ignore_index=True)

    events["stage_event_id"] = (
        events["stage_type"].astype("string")
        + "-"
        + events["auction_year"].astype("string")
        + "-"
        + events["parcel_number"].astype("string")
        + "-"
        + events["source_filename"].astype("string")
        + "-p"
        + events["source_start_page"].astype("string")
    )

    bool_cols = [
        "paid_in_full_flag",
        "administratively_pulled_flag",
        "redeemed_flag",
        "must_be_sold_with_flag",
        "sale_does_not_include_flag",
        "subject_to_flag",
        "ocr_review_required_flag",
        "ocr_repair_applied_flag",
    ]
    for col in bool_cols:
        events[col] = (
            events[col]
            .astype("string")
            .str.lower()
            .map({"true": True, "false": False})
            .fillna(False)
            .astype(bool)
        )

    ordered = ["stage_event_id"] + [
        col for col in events.columns if col != "stage_event_id"
    ]
    return events[ordered].sort_values(
        ["auction_year", "parcel_number", "source_quality_rank"],
        ascending=[True, True, False],
        na_position="last",
    ).reset_index(drop=True)


def aggregate_stage_events(events: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for (year, parcel), group in events.groupby(
        ["auction_year", "parcel_number"],
        dropna=False,
    ):
        ranked = group.sort_values(
            ["source_quality_rank", "stage_type"],
            ascending=[False, False],
        )
        stages = set(ranked["stage_type"].dropna().astype(str))

        source_refs = []
        for record in ranked.itertuples():
            start_page = record.source_start_page
            end_page = record.source_end_page
            if pd.isna(start_page):
                page_text = ""
            elif pd.isna(end_page) or start_page == end_page:
                page_text = f":p{int(float(start_page))}"
            else:
                page_text = (
                    f":p{int(float(start_page))}-"
                    f"{int(float(end_page))}"
                )
            source_refs.append(f"{record.source_filename}{page_text}")

        row = {
            "auction_year": year,
            "parcel_number": parcel,
            "parcel_year_id": f"{parcel}-{year}",
            "certificate_listed_flag": "certificate" in stages,
            "publication_listed_flag": "publication" in stages,
            "final_order_flag": "final_order" in stages,
            "stage_record_count": len(ranked),
            "stage_types_present": " | ".join(sorted(stages)),
            "source_filenames": join_unique(ranked["source_filename"]),
            "source_page_refs": " | ".join(source_refs),
            "source_kinds_present": join_unique(ranked["source_kind"]),
            "taxpayer_name": first_non_null(ranked["taxpayer_name"]),
            "owner_record_text": first_non_null(
                ranked["owner_record_text"]
            ),
            "legal_description": first_non_null(
                ranked["legal_description"]
            ),
            "situs_address": first_non_null(ranked["situs_address"]),
            "tca_code": first_non_null(ranked["tca_code"]),
            "use_code": first_non_null(ranked["use_code"]),
            "use_description": first_non_null(
                ranked["use_description"]
            ),
            "acreage": first_non_null(ranked["acreage"]),
            "land_value": first_non_null(ranked["land_value"]),
            "improvement_value": first_non_null(
                ranked["improvement_value"]
            ),
            "tax_years": join_unique(ranked["tax_years"]),
            "amount_due": first_non_null(ranked["amount_due"]),
            "amount_paid": first_non_null(ranked["amount_paid"]),
            "special_condition_text": join_unique(
                ranked["special_condition_text"]
            ),
            "ocr_final_order_flag": bool(
                (
                    (ranked["stage_type"] == "final_order")
                    & (ranked["source_kind"] == "ocr")
                ).any()
            ),
            "ocr_review_required_flag": bool(
                ranked["ocr_review_required_flag"].any()
            ),
            "ocr_repair_applied_flag": bool(
                ranked["ocr_repair_applied_flag"].any()
            ),
            "ocr_review_reasons": join_unique(
                ranked["ocr_review_reason"]
            ),
            "stage_extraction_methods": join_unique(
                ranked["extraction_method"]
            ),
        }

        for flag in [
            "paid_in_full_flag",
            "administratively_pulled_flag",
            "redeemed_flag",
            "must_be_sold_with_flag",
            "sale_does_not_include_flag",
            "subject_to_flag",
        ]:
            row[flag] = bool(ranked[flag].any())

        rows.append(row)

    result = pd.DataFrame(rows)
    result["land_value"] = pd.to_numeric(
        result["land_value"], errors="coerce"
    )
    result["improvement_value"] = pd.to_numeric(
        result["improvement_value"], errors="coerce"
    )
    result["total_assessed_value"] = (
        result["land_value"].fillna(0)
        + result["improvement_value"].fillna(0)
    )
    result.loc[
        result["land_value"].isna()
        & result["improvement_value"].isna(),
        "total_assessed_value",
    ] = pd.NA
    return result


def build_sales_table() -> pd.DataFrame:
    df = pd.DataFrame(sales).copy()
    df["auction_year"] = pd.to_numeric(
        df["auction_year"], errors="raise"
    ).astype("int64")
    df["parcel_number"] = normalize_parcel(df["parcel_number"])
    df["sale_number"] = pd.to_numeric(
        df["sale_number"], errors="raise"
    ).astype("int64")
    df["minimum_bid"] = pd.to_numeric(
        df["minimum_bid"], errors="raise"
    )
    df["selling_price"] = pd.to_numeric(
        df["selling_price"], errors="raise"
    )
    df["bid_multiple"] = (
        df["selling_price"] / df["minimum_bid"]
    ).round(4)
    df["winning_bid_premium"] = (
        df["selling_price"] - df["minimum_bid"]
    ).round(2)
    df["sold_flag"] = True
    df["county_acquired_flag"] = df["buyer_name"].str.contains(
        "Snohomish County", case=False, na=False
    )
    df["private_purchaser_flag"] = ~df["county_acquired_flag"]
    return df


def build_excess_table() -> pd.DataFrame:
    df = pd.DataFrame(excess_funds).copy()
    df["auction_year"] = pd.to_numeric(
        df["auction_year"], errors="raise"
    ).astype("int64")
    df["parcel_number"] = normalize_parcel(df["parcel_number"])
    df["sale_number"] = pd.to_numeric(
        df["sale_number"], errors="raise"
    ).astype("int64")
    df["excess_funds"] = pd.to_numeric(
        df["excess_funds"], errors="coerce"
    )
    return df


def derive_outcome(row: pd.Series) -> str:
    if bool(row.get("county_acquired_flag", False)):
        return "county_acquired"
    if bool(row.get("sold_flag", False)):
        return "sold_private"
    if bool(row.get("administratively_pulled_flag", False)):
        return "administratively_pulled"
    if bool(row.get("paid_in_full_flag", False)) or bool(
        row.get("redeemed_flag", False)
    ):
        return "paid_or_redeemed"
    if bool(row.get("final_order_flag", False)):
        return "reached_final_order"
    if bool(row.get("publication_listed_flag", False)):
        return "published"
    if bool(row.get("certificate_listed_flag", False)):
        return "certificate_only"
    return "unknown"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    events = build_stage_events()
    stage_wide = aggregate_stage_events(events)
    sales_df = build_sales_table()
    excess_df = build_excess_table()

    keys = ["auction_year", "parcel_number"]
    unified = stage_wide.merge(
        sales_df,
        how="outer",
        on=keys,
        validate="one_to_one",
    )

    unified = unified.merge(
        excess_df[
            [
                "auction_year",
                "parcel_number",
                "sale_number",
                "excess_funds",
                "excess_status",
            ]
        ],
        how="left",
        on=["auction_year", "parcel_number", "sale_number"],
        validate="one_to_one",
    )

    bool_defaults = {
        "certificate_listed_flag": False,
        "publication_listed_flag": False,
        "final_order_flag": False,
        "sold_flag": False,
        "county_acquired_flag": False,
        "private_purchaser_flag": False,
        "paid_in_full_flag": False,
        "administratively_pulled_flag": False,
        "redeemed_flag": False,
        "must_be_sold_with_flag": False,
        "sale_does_not_include_flag": False,
        "subject_to_flag": False,
        "ocr_final_order_flag": False,
        "ocr_review_required_flag": False,
        "ocr_repair_applied_flag": False,
    }

    for col, default in bool_defaults.items():
        if col not in unified.columns:
            unified[col] = default
        unified[col] = unified[col].fillna(default).astype(bool)

    unified["parcel_year_id"] = (
        unified["parcel_number"]
        + "-"
        + unified["auction_year"].astype("Int64").astype("string")
    )
    unified["excess_funds_match_flag"] = unified[
        "excess_status"
    ].notna()
    unified["lifecycle_outcome"] = unified.apply(
        derive_outcome, axis=1
    )

    unified["stage_coverage_flag"] = (
        unified["certificate_listed_flag"]
        | unified["publication_listed_flag"]
        | unified["final_order_flag"]
    )

    unified = unified.sort_values(
        ["auction_year", "parcel_number"],
        na_position="last",
    ).reset_index(drop=True)

    summary = (
        unified.groupby("auction_year", as_index=False)
        .agg(
            parcel_year_records=("parcel_year_id", "count"),
            certificate_records=("certificate_listed_flag", "sum"),
            publication_records=("publication_listed_flag", "sum"),
            final_order_records=("final_order_flag", "sum"),
            sold_records=("sold_flag", "sum"),
            county_acquisitions=("county_acquired_flag", "sum"),
            paid_or_redeemed_records=(
                "lifecycle_outcome",
                lambda values: (values == "paid_or_redeemed").sum(),
            ),
            administratively_pulled_records=(
                "administratively_pulled_flag",
                "sum",
            ),
            ocr_review_records=(
                "ocr_review_required_flag",
                "sum",
            ),
            ocr_repaired_apn_records=(
                "ocr_repair_applied_flag",
                "sum",
            ),
            total_selling_price=("selling_price", "sum"),
            total_reported_excess=("excess_funds", "sum"),
        )
    )

    events.to_csv(
        OUTPUT_DIR / "foreclosure_stage_events.csv",
        index=False,
    )
    unified.to_csv(
        OUTPUT_DIR / "unified_parcel_lifecycle.csv",
        index=False,
    )
    summary.to_csv(
        OUTPUT_DIR / "unified_lifecycle_summary.csv",
        index=False,
    )

    records = unified.where(
        pd.notna(unified), None
    ).to_dict(orient="records")
    (
        OUTPUT_DIR / "unified_parcel_lifecycle.json"
    ).write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    excel_events = events.copy()
    if "raw_record_text" in excel_events.columns:
        excel_events["raw_record_text"] = (
            excel_events["raw_record_text"]
            .astype("string")
            .str.slice(0, 32000)
        )

    with pd.ExcelWriter(
        OUTPUT_DIR / "unified_parcel_lifecycle.xlsx",
        engine="openpyxl",
    ) as writer:
        unified.to_excel(
            writer,
            sheet_name="Parcel Lifecycle",
            index=False,
        )
        excel_events.to_excel(
            writer,
            sheet_name="Stage Events",
            index=False,
        )
        summary.to_excel(
            writer,
            sheet_name="Annual Summary",
            index=False,
        )

        notes = pd.DataFrame(
            [
                [
                    "Dataset",
                    "Unified parcel-year foreclosure lifecycle",
                ],
                [
                    "Final Order coverage",
                    "OCR Final Orders for 2019–2025",
                ],
                [
                    "Duplicate handling",
                    "Duplicate OCR source keys excluded from unified table",
                ],
                [
                    "Review handling",
                    "Nonduplicate OCR review records retained and flagged",
                ],
                [
                    "APN repairs",
                    "13-digit OCR APNs retained with repair flag",
                ],
            ],
            columns=["Field", "Value"],
        )
        notes.to_excel(
            writer,
            sheet_name="README",
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
                    50,
                )
                worksheet.column_dimensions[
                    cells[0].column_letter
                ].width = width

    print(f"Stage-event rows: {len(events):,}")
    print(f"Unified parcel-year rows: {len(unified):,}")
    print(
        "Final Order parcel-years:",
        int(unified["final_order_flag"].sum()),
    )
    print(
        "Confirmed sold records:",
        int(unified["sold_flag"].sum()),
    )
    print(
        "OCR review-flagged parcel-years:",
        int(unified["ocr_review_required_flag"].sum()),
    )
    print(
        "OCR repaired-APN parcel-years:",
        int(unified["ocr_repair_applied_flag"].sum()),
    )
    print(
        "Output:",
        OUTPUT_DIR / "unified_parcel_lifecycle.xlsx",
    )


if __name__ == "__main__":
    main()
