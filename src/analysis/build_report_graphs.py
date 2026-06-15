"""Build report-ready static charts for the Snohomish foreclosure analysis.

Outputs PNG files to docs/assets and a reusable markdown snippet to docs.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"
DOCS_DIR = PROJECT_ROOT / "docs"
ASSET_DIR = DOCS_DIR / "assets"

ANNUAL_FUNNEL = OUTPUT_DIR / "analysis_annual_funnel.csv"
COMPETITIVENESS = OUTPUT_DIR / "analysis_auction_competitiveness_by_year.csv"
LIFECYCLE = OUTPUT_DIR / "unified_parcel_lifecycle.csv"
WATCHLIST = OUTPUT_DIR / "analysis_2026_homebuyer_watchlist.csv"
REPEAT_BUYERS_PUBLIC = OUTPUT_DIR / "analysis_repeat_buyer_summary_public_safe.csv"


def save_current_fig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


def prepare_year(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64").astype(str)


def build_lifecycle_funnel() -> None:
    df = pd.read_csv(ANNUAL_FUNNEL)
    df["year"] = prepare_year(df["auction_year"])

    plt.figure(figsize=(10, 5.5))
    plt.plot(df["year"], df["publications"], marker="o", label="Publications")
    plt.plot(df["year"], df["final_orders"], marker="o", label="Final Orders")
    plt.plot(df["year"], df["sold"], marker="o", label="Confirmed sales")
    plt.title("Foreclosure lifecycle funnel by year")
    plt.xlabel("Auction year")
    plt.ylabel("Parcel-year count")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.figtext(
        0.01,
        0.01,
        "Note: Publication coverage is incomplete for 2019–2020; 2026 is certificate-stage only.",
        ha="left",
        fontsize=8,
    )
    save_current_fig(ASSET_DIR / "lifecycle_funnel_by_year.png")


def build_bid_multiple_trend() -> None:
    df = pd.read_csv(COMPETITIVENESS)
    df["year"] = prepare_year(df["auction_year"])

    plt.figure(figsize=(10, 5.5))
    plt.plot(df["year"], df["median_bid_multiple"], marker="o", label="Median bid multiple")
    plt.title("Median winning bid multiple by year")
    plt.xlabel("Auction year")
    plt.ylabel("Selling price / minimum bid")
    plt.grid(True, alpha=0.3)
    plt.figtext(
        0.01,
        0.01,
        "Higher values mean winning bids were farther above minimum bid.",
        ha="left",
        fontsize=8,
    )
    save_current_fig(ASSET_DIR / "median_bid_multiple_by_year.png")


def build_minimum_bid_vs_sale_price() -> None:
    df = pd.read_csv(LIFECYCLE, dtype={"parcel_number": "string"})
    sold = df[df["sold_flag"].astype("string").str.lower().eq("true")].copy()
    sold["minimum_bid"] = pd.to_numeric(sold["minimum_bid"], errors="coerce")
    sold["selling_price"] = pd.to_numeric(sold["selling_price"], errors="coerce")
    sold = sold.dropna(subset=["minimum_bid", "selling_price"])

    plt.figure(figsize=(7.5, 7.0))
    plt.scatter(sold["minimum_bid"], sold["selling_price"], alpha=0.65)
    max_value = max(sold["minimum_bid"].max(), sold["selling_price"].max())
    plt.plot([0, max_value], [0, max_value], linestyle="--", label="Selling price = minimum bid")
    plt.title("Minimum bid versus winning sale price")
    plt.xlabel("Minimum bid")
    plt.ylabel("Selling price")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.figtext(
        0.01,
        0.01,
        "Each dot is a confirmed sale. Points above the line sold above minimum bid.",
        ha="left",
        fontsize=8,
    )
    save_current_fig(ASSET_DIR / "minimum_bid_vs_sale_price.png")


def build_2026_watchlist_category() -> None:
    df = pd.read_csv(WATCHLIST, dtype={"parcel_number": "string"})
    counts = (
        df["homebuyer_fit_category"]
        .fillna("Unknown")
        .value_counts()
        .rename_axis("category")
        .reset_index(name="count")
        .sort_values("count", ascending=True)
    )

    plt.figure(figsize=(9.5, 5.5))
    plt.barh(counts["category"], counts["count"])
    plt.title("2026 watchlist by first-time-homebuyer fit category")
    plt.xlabel("Parcel count")
    plt.ylabel("")
    plt.grid(True, axis="x", alpha=0.3)
    plt.figtext(
        0.01,
        0.01,
        "Certificate-stage watchlist only; beds, baths, building area, condition, and occupancy are not yet joined.",
        ha="left",
        fontsize=8,
    )
    save_current_fig(ASSET_DIR / "2026_watchlist_by_category.png")


def build_repeat_buyer_concentration() -> None:
    df = pd.read_csv(REPEAT_BUYERS_PUBLIC)
    top = df.sort_values(["purchase_count", "total_winning_bids"], ascending=False).head(15).copy()
    top = top.sort_values("purchase_count", ascending=True)

    plt.figure(figsize=(9.5, 6.0))
    plt.barh(top["buyer_display_name"], top["purchase_count"])
    plt.title("Repeat-buyer concentration, public-safe labels")
    plt.xlabel("Purchase count")
    plt.ylabel("")
    plt.grid(True, axis="x", alpha=0.3)
    plt.figtext(
        0.01,
        0.01,
        "Public-safe buyer labels preserve concentration patterns without showing names in the chart.",
        ha="left",
        fontsize=8,
    )
    save_current_fig(ASSET_DIR / "repeat_buyer_concentration.png")


def write_markdown_snippet() -> None:
    snippet = """# README Graphs and Professional Insights Snippet

Paste this into the README after the Key findings section, or adapt into the final report.

## What this analysis suggests

This project is not just a document extraction exercise. The linked lifecycle table makes it possible to analyze the tax foreclosure process as a funnel, rather than as isolated PDFs.

### 1. Minimum bid behaves more like a legal threshold than a market signal

The auction competitiveness outputs show that winning bids often exceed the minimum bid by several multiples. For buyers, this means the minimum bid is a poor affordability proxy. For analysts, it suggests that minimum bid should be modeled as an opening constraint rather than an estimate of expected sale price.

![Median winning bid multiple by year](docs/assets/median_bid_multiple_by_year.png)

![Minimum bid versus winning sale price](docs/assets/minimum_bid_vs_sale_price.png)

### 2. The main buyer problem is triage, not just finding parcels

The lifecycle data shows that many parcels appear before the sale stage but do not ultimately become confirmed sales. A practical buyer does not only need a list of parcels; they need a way to prioritize which parcels are still active, which ones are likely residential, and which ones have enough property information to justify deeper due diligence.

![Foreclosure lifecycle funnel by year](docs/assets/lifecycle_funnel_by_year.png)

### 3. The market appears to include specialized participants

Repeat-buyer outputs show that a subset of purchasers appear across multiple auction years. This matters because first-time or occasional buyers are not only evaluating properties; they may also be competing against participants who understand the auction process, title risks, redemption dynamics, and local parcel quirks.

![Repeat-buyer concentration](docs/assets/repeat_buyer_concentration.png)

### 4. 2026 opportunities need assessor enrichment before true ranking

The 2026 watchlist is useful for screening, but not yet sufficient for purchase decisions. The next professional-grade improvement is to join assessor and GIS fields: beds, baths, building square feet, year built, property class, parcel geometry, hazard overlays, zoning, access, and utilities/septic indicators.

![2026 watchlist by fit category](docs/assets/2026_watchlist_by_category.png)

## Practical professional takeaways

- A low minimum bid should trigger due diligence, not excitement.
- The most valuable workflow is stage-based triage: certificate → publication → final order → sale.
- OCR imperfections are manageable if they are exposed with review flags instead of hidden.
- Public-safe repeat-buyer outputs let the project discuss market structure without relying on named individuals in the narrative.
- Assessor/GIS enrichment is the highest-value next data layer because it turns a foreclosure dataset into a property-screening dataset.
"""
    (DOCS_DIR / "readme_graphs_and_insights_snippet.md").write_text(snippet, encoding="utf-8")


def main() -> None:
    missing = [
        path for path in [
            ANNUAL_FUNNEL,
            COMPETITIVENESS,
            LIFECYCLE,
            WATCHLIST,
            REPEAT_BUYERS_PUBLIC,
        ]
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(
            "Missing required analysis outputs:\n"
            + "\n".join(str(path) for path in missing)
        )

    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    build_lifecycle_funnel()
    build_bid_multiple_trend()
    build_minimum_bid_vs_sale_price()
    build_2026_watchlist_category()
    build_repeat_buyer_concentration()
    write_markdown_snippet()

    print("Wrote report charts:")
    for path in [
        ASSET_DIR / "lifecycle_funnel_by_year.png",
        ASSET_DIR / "median_bid_multiple_by_year.png",
        ASSET_DIR / "minimum_bid_vs_sale_price.png",
        ASSET_DIR / "2026_watchlist_by_category.png",
        ASSET_DIR / "repeat_buyer_concentration.png",
        DOCS_DIR / "readme_graphs_and_insights_snippet.md",
    ]:
        print(f"- {path}")


if __name__ == "__main__":
    main()
