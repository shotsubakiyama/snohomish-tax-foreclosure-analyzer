"""Build the initial parcel lifecycle dataset.

Current coverage:
- 2019–2025 successful sales from Return of Sale records
- 2024–2025 exact excess-funds records

Later stages will add:
- initial foreclosure filing
- publication status
- final-order status
- paid/redeemed/pulled outcomes
"""

from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from src.data.auction_sales import sales
from src.data.excess_funds import excess_funds


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"


def build_lifecycle() -> pd.DataFrame:
    sales_df = pd.DataFrame(sales).copy()
    excess_df = pd.DataFrame(excess_funds).copy()

    for df in (sales_df, excess_df):
        df["auction_year"] = pd.to_numeric(df["auction_year"], errors="raise").astype("int64")
        df["sale_number"] = pd.to_numeric(df["sale_number"], errors="raise").astype("int64")
        df["parcel_number"] = (
            df["parcel_number"]
            .astype("string")
            .str.replace(r"\D", "", regex=True)
            .str.zfill(14)
        )

    sales_df["minimum_bid"] = pd.to_numeric(sales_df["minimum_bid"], errors="raise")
    sales_df["selling_price"] = pd.to_numeric(sales_df["selling_price"], errors="raise")
    sales_df["bid_multiple"] = (
        sales_df["selling_price"] / sales_df["minimum_bid"]
    ).round(4)
    sales_df["winning_bid_premium"] = (
        sales_df["selling_price"] - sales_df["minimum_bid"]
    ).round(2)

    sales_df["auction_sale_id"] = (
        sales_df["auction_year"].astype("string")
        + "-"
        + sales_df["sale_number"].astype("string").str.zfill(3)
    )
    sales_df["parcel_year_id"] = (
        sales_df["parcel_number"] + "-" + sales_df["auction_year"].astype("string")
    )

    sales_df["lifecycle_stage"] = "return_of_sale"
    sales_df["sold_flag"] = True
    sales_df["county_acquired_flag"] = sales_df["buyer_name"].str.contains(
        "Snohomish County", case=False, na=False
    )
    sales_df["private_purchaser_flag"] = ~sales_df["county_acquired_flag"]

    # Earlier-stage fields are deliberately present now, even when unknown.
    sales_df["certificate_listed_flag"] = pd.NA
    sales_df["publication_listed_flag"] = pd.NA
    sales_df["final_order_flag"] = pd.NA
    sales_df["paid_or_redeemed_before_sale_flag"] = False
    sales_df["administratively_pulled_flag"] = False
    sales_df["special_condition_flag"] = False
    sales_df["special_condition_text"] = pd.NA

    lifecycle = sales_df.merge(
        excess_df[
            [
                "auction_year",
                "sale_number",
                "parcel_number",
                "excess_funds",
                "excess_status",
            ]
        ],
        how="left",
        on=["auction_year", "sale_number", "parcel_number"],
        validate="one_to_one",
    )

    lifecycle["excess_funds"] = pd.to_numeric(
        lifecycle["excess_funds"], errors="coerce"
    )
    lifecycle["excess_funds_match_flag"] = lifecycle["excess_status"].notna()
    lifecycle["reported_excess_as_pct_of_sale"] = (
        lifecycle["excess_funds"] / lifecycle["selling_price"]
    ).round(4)

    lifecycle["source_return_of_sale_flag"] = True
    lifecycle["source_excess_funds_flag"] = lifecycle["excess_funds_match_flag"]
    lifecycle["review_status"] = "return_of_sale_verified"
    lifecycle.loc[
        lifecycle["source_excess_funds_flag"], "review_status"
    ] = "return_and_excess_verified"

    columns = [
        "auction_sale_id",
        "parcel_year_id",
        "auction_year",
        "sale_number",
        "parcel_number",
        "lifecycle_stage",
        "certificate_listed_flag",
        "publication_listed_flag",
        "final_order_flag",
        "sold_flag",
        "paid_or_redeemed_before_sale_flag",
        "administratively_pulled_flag",
        "county_acquired_flag",
        "private_purchaser_flag",
        "buyer_name",
        "minimum_bid",
        "selling_price",
        "winning_bid_premium",
        "bid_multiple",
        "excess_funds",
        "excess_status",
        "reported_excess_as_pct_of_sale",
        "excess_funds_match_flag",
        "special_condition_flag",
        "special_condition_text",
        "source_return_of_sale_flag",
        "source_excess_funds_flag",
        "review_status",
    ]
    return lifecycle[columns].sort_values(
        ["auction_year", "sale_number"]
    ).reset_index(drop=True)


def build_lifecycle_summary(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("auction_year", as_index=False)
        .agg(
            sold_records=("auction_sale_id", "count"),
            private_purchases=("private_purchaser_flag", "sum"),
            county_acquisitions=("county_acquired_flag", "sum"),
            total_minimum_bid=("minimum_bid", "sum"),
            total_selling_price=("selling_price", "sum"),
            median_bid_multiple=("bid_multiple", "median"),
            excess_records_matched=("excess_funds_match_flag", "sum"),
            total_reported_excess=("excess_funds", "sum"),
        )
        .round(4)
    )


def write_excel(
    lifecycle: pd.DataFrame,
    summary: pd.DataFrame,
    output_path: Path,
) -> None:
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        lifecycle.to_excel(writer, sheet_name="Parcel Lifecycle", index=False)
        summary.to_excel(writer, sheet_name="Annual Summary", index=False)

        notes = pd.DataFrame(
            [
                ["Dataset stage", "Initial lifecycle seed"],
                ["Sales coverage", "2019–2025"],
                ["Exact excess coverage", "2024–2025"],
                [
                    "Unknown fields",
                    "Certificate/publication/final-order fields remain blank until parsed.",
                ],
                [
                    "Interpretation",
                    "A Return of Sale row confirms the parcel was offered and sold or taken as tax title.",
                ],
            ],
            columns=["Field", "Value"],
        )
        notes.to_excel(writer, sheet_name="README", index=False)

        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for cells in ws.columns:
                width = min(
                    max(
                        max(
                            len(str(cell.value)) if cell.value is not None else 0
                            for cell in cells
                        )
                        + 2,
                        11,
                    ),
                    42,
                )
                ws.column_dimensions[cells[0].column_letter].width = width


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lifecycle = build_lifecycle()
    summary = build_lifecycle_summary(lifecycle)

    lifecycle.to_csv(
        OUTPUT_DIR / "snohomish_parcel_lifecycle_seed.csv", index=False
    )
    summary.to_csv(
        OUTPUT_DIR / "lifecycle_annual_summary.csv", index=False
    )
    write_excel(
        lifecycle,
        summary,
        OUTPUT_DIR / "snohomish_parcel_lifecycle_seed.xlsx",
    )

    records = lifecycle.where(pd.notna(lifecycle), None).to_dict(orient="records")
    (OUTPUT_DIR / "snohomish_parcel_lifecycle_seed.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Wrote {len(lifecycle):,} lifecycle seed rows")
    print(
        "Exact excess-funds matches:",
        int(lifecycle["excess_funds_match_flag"].sum()),
    )
    print(
        "Reported excess total:",
        f"${lifecycle['excess_funds'].sum(skipna=True):,.2f}",
    )


if __name__ == "__main__":
    main()
