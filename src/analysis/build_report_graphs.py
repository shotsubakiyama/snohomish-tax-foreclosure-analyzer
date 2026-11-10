"""Build report-ready static charts for the Snohomish foreclosure analysis.

Outputs the report charts used by the public README to docs/assets.
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

    fig, ax1 = plt.subplots(figsize=(10, 5.8))
    ax2 = ax1.twinx()

    positions = range(len(df))
    ax2.bar(
        positions,
        df["sales"],
        width=0.5,
        alpha=0.18,
        label="Confirmed sales",
    )
    ax1.plot(
        positions,
        df["median_bid_multiple"],
        marker="o",
        linewidth=2.2,
        label="Median winning-price multiple",
    )

    ax1.set_xticks(list(positions), df["year"])
    ax1.set_title("Winning prices versus minimum bids, with yearly sale volume")
    ax1.set_xlabel("Auction year")
    ax1.set_ylabel("Median winning price / minimum bid (×)")
    ax2.set_ylabel("Confirmed sales")

    for i, row in df.reset_index(drop=True).iterrows():
        ax1.annotate(
            f'{row["median_bid_multiple"]:.1f}×',
            (i, row["median_bid_multiple"]),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=8,
        )
        ax2.annotate(
            f'n={int(row["sales"])}',
            (i, row["sales"]),
            textcoords="offset points",
            xytext=(0, 4),
            ha="center",
            fontsize=8,
        )

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, loc="upper left")

    ax1.grid(True, axis="y", alpha=0.25)
    ax1.figtext(
        0.01,
        0.01,
        "Example: 12× means the median winning price was twelve times the listed minimum bid. Bars show confirmed sales in each year.",
        ha="left",
        fontsize=8,
    )
    save_current_fig(ASSET_DIR / "median_bid_multiple_by_year.png")


def main() -> None:
    missing = [
        path for path in [
            ANNUAL_FUNNEL,
            COMPETITIVENESS,
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

    print("Wrote report charts:")
    for path in [
        ASSET_DIR / "lifecycle_funnel_by_year.png",
        ASSET_DIR / "median_bid_multiple_by_year.png",
    ]:
        print(f"- {path}")


if __name__ == "__main__":
    main()
