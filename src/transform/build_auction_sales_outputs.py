"""Build public auction-sales outputs from the canonical Python sales list."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json

import pandas as pd

from src.data.auction_sales import sales


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"


def normalize_sales() -> pd.DataFrame:
    """Return a validated, consistently ordered auction-sales dataframe."""
    df = pd.DataFrame(sales).copy()

    required = {
        "auction_year",
        "sale_number",
        "parcel_number",
        "minimum_bid",
        "selling_price",
        "buyer_name",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["auction_year"] = pd.to_numeric(df["auction_year"], errors="raise").astype("int64")
    df["sale_number"] = pd.to_numeric(df["sale_number"], errors="raise").astype("int64")
    df["parcel_number"] = (
        df["parcel_number"]
        .astype("string")
        .str.replace(r"\D", "", regex=True)
        .str.zfill(14)
    )
    df["minimum_bid"] = pd.to_numeric(df["minimum_bid"], errors="raise")
    df["selling_price"] = pd.to_numeric(df["selling_price"], errors="raise")
    df["buyer_name"] = df["buyer_name"].astype("string").str.strip()

    df["bid_multiple"] = (df["selling_price"] / df["minimum_bid"]).round(4)
    df["winning_bid_premium"] = (df["selling_price"] - df["minimum_bid"]).round(2)
    df["county_acquired_flag"] = (
        df["buyer_name"].str.contains("Snohomish County", case=False, na=False)
    )
    df["private_sale_flag"] = ~df["county_acquired_flag"]

    # These identifiers support later joins without assuming parcel number alone is unique.
    df["auction_sale_id"] = (
        df["auction_year"].astype("string")
        + "-"
        + df["sale_number"].astype("string").str.zfill(3)
    )
    df["parcel_year_id"] = (
        df["parcel_number"] + "-" + df["auction_year"].astype("string")
    )

    # Preserve a source-oriented column order while retaining all future fields.
    ordered = [
        "auction_sale_id",
        "parcel_year_id",
        "auction_year",
        "sale_number",
        "parcel_number",
        "minimum_bid",
        "selling_price",
        "winning_bid_premium",
        "bid_multiple",
        "buyer_name",
        "county_acquired_flag",
        "private_sale_flag",
    ]
    return df[ordered].sort_values(["auction_year", "sale_number"]).reset_index(drop=True)


def build_annual_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby("auction_year", as_index=False)
        .agg(
            properties_sold=("auction_sale_id", "count"),
            unique_parcels=("parcel_number", "nunique"),
            total_minimum_bid=("minimum_bid", "sum"),
            total_selling_price=("selling_price", "sum"),
            median_selling_price=("selling_price", "median"),
            average_bid_multiple=("bid_multiple", "mean"),
            median_bid_multiple=("bid_multiple", "median"),
            county_acquisitions=("county_acquired_flag", "sum"),
        )
    )
    summary["total_winning_bid_premium"] = (
        summary["total_selling_price"] - summary["total_minimum_bid"]
    )
    return summary.round(4)


def build_buyer_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby("buyer_name", as_index=False)
        .agg(
            purchase_count=("auction_sale_id", "count"),
            first_purchase_year=("auction_year", "min"),
            most_recent_purchase_year=("auction_year", "max"),
            auction_year_count=("auction_year", "nunique"),
            total_winning_bids=("selling_price", "sum"),
            median_winning_bid=("selling_price", "median"),
            average_bid_multiple=("bid_multiple", "mean"),
            county_acquisition_count=("county_acquired_flag", "sum"),
        )
        .sort_values(
            ["purchase_count", "total_winning_bids", "buyer_name"],
            ascending=[False, False, True],
        )
        .reset_index(drop=True)
    )
    summary["repeat_buyer_flag"] = summary["purchase_count"] > 1
    return summary.round(4)


def write_excel(
    sales_df: pd.DataFrame,
    annual_df: pd.DataFrame,
    buyer_df: pd.DataFrame,
    output_path: Path,
) -> None:
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        sales_df.to_excel(writer, sheet_name="Auction Sales", index=False)
        annual_df.to_excel(writer, sheet_name="Annual Summary", index=False)
        buyer_df.to_excel(writer, sheet_name="Buyer Summary", index=False)

        readme = pd.DataFrame(
            [
                ["Dataset", "Snohomish County tax-foreclosure auction sales"],
                ["Coverage", "2019–2025 Return of Sale records"],
                ["Canonical source", "src/data/auction_sales.py"],
                ["Build script", "src/transform/build_auction_sales_outputs.py"],
                [
                    "Use restriction",
                    "Research/analysis dataset; not intended as a solicitation or contact list.",
                ],
            ],
            columns=["Field", "Value"],
        )
        readme.to_excel(writer, sheet_name="README", index=False)

        # Basic usability formatting.
        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                max_length = max(
                    len(str(cell.value)) if cell.value is not None else 0
                    for cell in column_cells
                )
                worksheet.column_dimensions[column_cells[0].column_letter].width = min(
                    max(max_length + 2, 11), 42
                )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sales_df = normalize_sales()
    annual_df = build_annual_summary(sales_df)
    buyer_df = build_buyer_summary(sales_df)

    sales_df.to_csv(
        OUTPUT_DIR / "snohomish_auction_sales_2019_2025.csv", index=False
    )
    annual_df.to_csv(OUTPUT_DIR / "annual_summary.csv", index=False)
    buyer_df.to_csv(OUTPUT_DIR / "buyer_summary.csv", index=False)

    records = sales_df.where(pd.notna(sales_df), None).to_dict(orient="records")
    (OUTPUT_DIR / "snohomish_auction_sales_2019_2025.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    write_excel(
        sales_df,
        annual_df,
        buyer_df,
        OUTPUT_DIR / "snohomish_auction_sales_2019_2025.xlsx",
    )

    print(f"Wrote {len(sales_df):,} auction-sale rows to {OUTPUT_DIR}")
    print(f"Years: {sales_df['auction_year'].min()}–{sales_df['auction_year'].max()}")
    print(f"Unique named purchasers: {sales_df['buyer_name'].nunique():,}")


if __name__ == "__main__":
    main()
