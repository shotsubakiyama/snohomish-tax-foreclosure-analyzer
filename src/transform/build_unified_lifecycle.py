"""Build a unified parcel-year foreclosure lifecycle dataset.

Inputs:
- outputs/public/machine_readable_stage_records.csv
- src.data.auction_sales
- src.data.excess_funds

Outputs:
- stage_events.csv/xlsx
- unified_parcel_lifecycle.csv/xlsx/json
- lifecycle_summary.csv

The merge is conservative. It does not infer missing stages from scanned years.
"""

from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from src.data.auction_sales import sales
from src.data.excess_funds import excess_funds


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"
STAGE_PATH = OUTPUT_DIR / "machine_readable_stage_records.csv"


def normalize_parcel(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.replace(r"\D", "", regex=True)
        .str.zfill(14)
    )


def first_non_null(series: pd.Series):
    non_null = series.dropna()
    if non_null.empty:
        return pd.NA
    for value in non_null:
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
        else:
            return value
    return pd.NA


def join_unique(series: pd.Series) -> str | pd._libs.missing.NAType:
    values = []
    seen = set()
    for value in series.dropna():
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            values.append(text)
    return " | ".join(values) if values else pd.NA


def load_stage_events() -> pd.DataFrame:
    if not STAGE_PATH.exists():
        raise FileNotFoundError(
            f"Missing parsed stage records: {STAGE_PATH}\n"
            "Run: python -m src.extract.parse_machine_readable_stage_records"
        )

    df = pd.read_csv(STAGE_PATH, dtype={"parcel_number": "string"})
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
    df["stage_event_id"] = (
        df["stage_type"].astype("string")
        + "-"
        + df["auction_year"].astype("string")
        + "-"
        + df["parcel_number"]
        + "-"
        + df["source_filename"].astype("string")
        + "-p"
        + df["source_start_page"].astype("string")
    )

    # Keep all source fields. The event table is the auditable source-oriented layer.
    preferred = [
        "stage_event_id",
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
        "record_spans_pages_flag",
        "source_relative_path",
        "extraction_method",
        "review_required_flag",
        "review_reason",
        "raw_record_text",
    ]
    return df[[c for c in preferred if c in df.columns]].copy()


def aggregate_stage_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    # Prefer later-stage documents when selecting representative descriptive values.
    priority = {"final_order": 3, "publication": 2, "certificate": 1}
    ranked = events.copy()
    ranked["source_priority"] = ranked["stage_type"].map(priority).fillna(0)
    ranked = ranked.sort_values(
        ["auction_year", "parcel_number", "source_priority"],
        ascending=[True, True, False],
    )

    group_cols = ["auction_year", "parcel_number"]

    flag_cols = [
        "paid_in_full_flag",
        "administratively_pulled_flag",
        "redeemed_flag",
        "must_be_sold_with_flag",
        "sale_does_not_include_flag",
        "subject_to_flag",
    ]
    for col in flag_cols:
        if col in ranked.columns:
            ranked[col] = ranked[col].fillna(False).astype(bool)

    grouped_rows = []
    for (year, parcel), group in ranked.groupby(group_cols, dropna=False):
        stage_types = set(group["stage_type"].dropna().astype(str))
        row = {
            "auction_year": year,
            "parcel_number": parcel,
            "parcel_year_id": f"{parcel}-{year}",
            "certificate_listed_flag": "certificate" in stage_types,
            "publication_listed_flag": "publication" in stage_types,
            "final_order_flag": "final_order" in stage_types,
            "stage_record_count": len(group),
            "stage_types_present": " | ".join(sorted(stage_types)),
            "source_filenames": join_unique(group["source_filename"]),
            "source_page_refs": " | ".join(
                f"{r.source_filename}:p{r.source_start_page}"
                + (
                    f"-{r.source_end_page}"
                    if r.source_end_page != r.source_start_page
                    else ""
                )
                for r in group.itertuples()
            ),
            "taxpayer_name": first_non_null(group.get("taxpayer_name", pd.Series(dtype="object"))),
            "owner_record_text": first_non_null(group.get("owner_record_text", pd.Series(dtype="object"))),
            "legal_description": first_non_null(group.get("legal_description", pd.Series(dtype="object"))),
            "situs_address": first_non_null(group.get("situs_address", pd.Series(dtype="object"))),
            "tca_code": first_non_null(group.get("tca_code", pd.Series(dtype="object"))),
            "use_code": first_non_null(group.get("use_code", pd.Series(dtype="object"))),
            "use_description": first_non_null(group.get("use_description", pd.Series(dtype="object"))),
            "acreage": first_non_null(group.get("acreage", pd.Series(dtype="float"))),
            "land_value": first_non_null(group.get("land_value", pd.Series(dtype="float"))),
            "improvement_value": first_non_null(group.get("improvement_value", pd.Series(dtype="float"))),
            "tax_years": join_unique(group.get("tax_years", pd.Series(dtype="object"))),
            "amount_due": first_non_null(group.get("amount_due", pd.Series(dtype="float"))),
            "amount_paid": first_non_null(group.get("amount_paid", pd.Series(dtype="float"))),
            "special_condition_text": join_unique(
                group.get("special_condition_text", pd.Series(dtype="object"))
            ),
            "stage_extraction_methods": join_unique(
                group.get("extraction_method", pd.Series(dtype="object"))
            ),
        }

        for col in flag_cols:
            row[col] = bool(group[col].any()) if col in group.columns else False

        grouped_rows.append(row)

    result = pd.DataFrame(grouped_rows)
    result["total_assessed_value"] = (
        pd.to_numeric(result["land_value"], errors="coerce").fillna(0)
        + pd.to_numeric(result["improvement_value"], errors="coerce").fillna(0)
    )
    result.loc[
        result["land_value"].isna() & result["improvement_value"].isna(),
        "total_assessed_value",
    ] = pd.NA
    return result


def build_sales_table() -> pd.DataFrame:
    df = pd.DataFrame(sales).copy()
    df["auction_year"] = pd.to_numeric(df["auction_year"], errors="raise").astype("int64")
    df["parcel_number"] = normalize_parcel(df["parcel_number"])
    df["sale_number"] = pd.to_numeric(df["sale_number"], errors="raise").astype("int64")
    df["minimum_bid"] = pd.to_numeric(df["minimum_bid"], errors="raise")
    df["selling_price"] = pd.to_numeric(df["selling_price"], errors="raise")
    df["bid_multiple"] = (df["selling_price"] / df["minimum_bid"]).round(4)
    df["winning_bid_premium"] = (df["selling_price"] - df["minimum_bid"]).round(2)
    df["sold_flag"] = True
    df["county_acquired_flag"] = df["buyer_name"].str.contains(
        "Snohomish County", case=False, na=False
    )
    df["private_purchaser_flag"] = ~df["county_acquired_flag"]
    df["auction_sale_id"] = (
        df["auction_year"].astype("string")
        + "-"
        + df["sale_number"].astype("string").str.zfill(3)
    )
    return df


def build_excess_table() -> pd.DataFrame:
    df = pd.DataFrame(excess_funds).copy()
    df["auction_year"] = pd.to_numeric(df["auction_year"], errors="raise").astype("int64")
    df["parcel_number"] = normalize_parcel(df["parcel_number"])
    df["sale_number"] = pd.to_numeric(df["sale_number"], errors="raise").astype("int64")
    df["excess_funds"] = pd.to_numeric(df["excess_funds"], errors="coerce")
    return df


def derive_outcome(row: pd.Series) -> str:
    if bool(row.get("county_acquired_flag", False)):
        return "county_acquired"
    if bool(row.get("sold_flag", False)):
        return "sold_private"
    if bool(row.get("administratively_pulled_flag", False)):
        return "administratively_pulled"
    if bool(row.get("paid_in_full_flag", False)) or bool(row.get("redeemed_flag", False)):
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

    events = load_stage_events()
    stage_wide = aggregate_stage_events(events)
    sales_df = build_sales_table()
    excess_df = build_excess_table()

    keys = ["auction_year", "parcel_number"]

    # Outer join preserves parcels found only in stage records or only in sales.
    unified = stage_wide.merge(
        sales_df,
        how="outer",
        on=keys,
        suffixes=("", "_sale"),
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

    boolean_defaults = {
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
    }
    for col, default in boolean_defaults.items():
        if col not in unified.columns:
            unified[col] = default
        unified[col] = unified[col].fillna(default).astype(bool)

    unified["parcel_year_id"] = (
        unified["parcel_number"]
        + "-"
        + unified["auction_year"].astype("Int64").astype("string")
    )
    unified["excess_funds_match_flag"] = unified["excess_status"].notna()
    unified["lifecycle_outcome"] = unified.apply(derive_outcome, axis=1)

    # Coverage notes prevent users from interpreting absent machine-readable stages as proof of absence.
    unified["machine_readable_stage_coverage_flag"] = (
        unified["certificate_listed_flag"]
        | unified["publication_listed_flag"]
        | unified["final_order_flag"]
    )
    unified["coverage_note"] = unified["machine_readable_stage_coverage_flag"].map(
        {
            True: "At least one searchable foreclosure-stage source parsed.",
            False: "No searchable stage source parsed; scanned-source coverage may still be pending.",
        }
    )

    unified = unified.sort_values(
        ["auction_year", "parcel_number"], na_position="last"
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
            paid_or_redeemed_records=("lifecycle_outcome", lambda s: (s == "paid_or_redeemed").sum()),
            total_selling_price=("selling_price", "sum"),
            total_reported_excess=("excess_funds", "sum"),
        )
    )

    events.to_csv(OUTPUT_DIR / "foreclosure_stage_events.csv", index=False)
    unified.to_csv(OUTPUT_DIR / "unified_parcel_lifecycle.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "unified_lifecycle_summary.csv", index=False)

    records = unified.where(pd.notna(unified), None).to_dict(orient="records")
    (OUTPUT_DIR / "unified_parcel_lifecycle.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    with pd.ExcelWriter(
        OUTPUT_DIR / "unified_parcel_lifecycle.xlsx", engine="openpyxl"
    ) as writer:
        unified.to_excel(writer, sheet_name="Parcel Lifecycle", index=False)
        events.to_excel(writer, sheet_name="Stage Events", index=False)
        summary.to_excel(writer, sheet_name="Annual Summary", index=False)

        notes = pd.DataFrame(
            [
                ["Dataset", "Unified parcel-year foreclosure lifecycle"],
                ["Stage coverage", "Searchable 2024 certificate, 2025 affidavit, 2026 certificate"],
                ["Sales coverage", "2019–2025 Return of Sale"],
                ["Excess coverage", "Exact records currently loaded for 2024–2025"],
                [
                    "Important limitation",
                    "Blank stage flags in scanned years do not prove a parcel skipped that stage.",
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
                            len(str(cell.value)) if cell.value is not None else 0
                            for cell in cells
                        )
                        + 2,
                        11,
                    ),
                    50,
                )
                worksheet.column_dimensions[cells[0].column_letter].width = width

    print(f"Stage-event rows: {len(events):,}")
    print(f"Unified parcel-year rows: {len(unified):,}")
    print(f"Sold records: {int(unified['sold_flag'].sum()):,}")
    print(
        "Rows with machine-readable stage coverage:",
        f"{int(unified['machine_readable_stage_coverage_flag'].sum()):,}",
    )
    print(
        "Exact excess-funds matches:",
        f"{int(unified['excess_funds_match_flag'].sum()):,}",
    )
    print("Output:", OUTPUT_DIR / "unified_parcel_lifecycle.xlsx")


if __name__ == "__main__":
    main()
