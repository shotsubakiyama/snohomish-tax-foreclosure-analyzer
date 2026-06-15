"""Build coverage audit tables for the Snohomish foreclosure lifecycle project."""

from __future__ import annotations

from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"
DOCS_DIR = PROJECT_ROOT / "docs"

LIFECYCLE_PATH = OUTPUT_DIR / "unified_parcel_lifecycle.csv"
STAGE_EVENTS_PATH = OUTPUT_DIR / "foreclosure_stage_events.csv"
SOURCE_INVENTORY_PATH = OUTPUT_DIR / "source_inventory.csv"


def status_from_coverage(row: pd.Series) -> str:
    if row["source_document_coverage"] == "Complete" and row["parse_quality"] == "Strong":
        return "Strong"
    if row["source_document_coverage"] in {"Mostly complete", "Complete"}:
        return "Usable with caveats"
    return "Partial / future work"


def main() -> None:
    if not LIFECYCLE_PATH.exists():
        raise FileNotFoundError(f"Missing {LIFECYCLE_PATH}. Run build_unified_lifecycle first.")

    lifecycle = pd.read_csv(LIFECYCLE_PATH, dtype={"parcel_number": "string"})
    events = pd.read_csv(STAGE_EVENTS_PATH, dtype={"parcel_number": "string"}) if STAGE_EVENTS_PATH.exists() else pd.DataFrame()
    inventory = pd.read_csv(SOURCE_INVENTORY_PATH) if SOURCE_INVENTORY_PATH.exists() else pd.DataFrame()

    years = sorted(lifecycle["auction_year"].dropna().astype(int).unique())

    annual = (
        lifecycle.groupby("auction_year", as_index=False)
        .agg(
            parcel_year_records=("parcel_year_id", "count"),
            certificate_records=("certificate_listed_flag", "sum"),
            publication_records=("publication_listed_flag", "sum"),
            final_order_records=("final_order_flag", "sum"),
            sold_records=("sold_flag", "sum"),
            ocr_review_flagged_records=("ocr_review_required_flag", "sum"),
            repaired_apn_records=("ocr_repair_applied_flag", "sum"),
        )
        .sort_values("auction_year")
    )

    annual["publication_to_final_order_ratio"] = (
        annual["final_order_records"] / annual["publication_records"]
    ).round(3)
    annual["final_order_to_sale_ratio"] = (
        annual["sold_records"] / annual["final_order_records"]
    ).round(3)

    source_rows = [
        {
            "data_layer": "Return of Sale / auction sales",
            "source_document_coverage": "Complete",
            "years_covered": "2019–2025",
            "records_currently_loaded": int(lifecycle["sold_flag"].sum()),
            "parse_quality": "Strong",
            "known_gap_or_caveat": "Buyer names and sale prices are structured; earlier scanned source formatting was manually normalized.",
            "future_version_note": "Second-pass validation of buyer-name spelling and county-acquired classifications.",
            "publication_status": "Publishable now",
        },
        {
            "data_layer": "Excess funds",
            "source_document_coverage": "Partial",
            "years_covered": "2024–2025 exact matches currently loaded",
            "records_currently_loaded": int(lifecycle["excess_funds_match_flag"].sum()),
            "parse_quality": "Strong for loaded years",
            "known_gap_or_caveat": "Earlier excess-funds files are not fully integrated yet.",
            "future_version_note": "Parse older excess-funds lists and link surplus outcomes across more years.",
            "publication_status": "Publishable with coverage note",
        },
        {
            "data_layer": "Affidavit of Publication",
            "source_document_coverage": "Mostly complete",
            "years_covered": "2021–2025; 2020 pending",
            "records_currently_loaded": int(lifecycle["publication_listed_flag"].sum()),
            "parse_quality": "Usable with OCR flags",
            "known_gap_or_caveat": "2020 affidavit produced no usable records in first OCR pass; some OCR rows have review flags.",
            "future_version_note": "Target 2020 layout separately and review duplicate/repaired APN rows.",
            "publication_status": "Publishable with caveat",
        },
        {
            "data_layer": "Final Order of Sale",
            "source_document_coverage": "Complete",
            "years_covered": "2019–2025",
            "records_currently_loaded": int(lifecycle["final_order_flag"].sum()),
            "parse_quality": "Usable with OCR flags",
            "known_gap_or_caveat": "Some OCR records have missing legal/owner fields; duplicate source keys excluded from lifecycle.",
            "future_version_note": "Review 50 OCR-flagged parcel-years and verify 13 repaired APNs against Assessor/SCOPI records.",
            "publication_status": "Publishable with caveat",
        },
        {
            "data_layer": "Certificate of Delinquency",
            "source_document_coverage": "Partial",
            "years_covered": "2024 and 2026 machine-readable; older scanned years pending",
            "records_currently_loaded": int(lifecycle["certificate_listed_flag"].sum()),
            "parse_quality": "Strong for machine-readable records",
            "known_gap_or_caveat": "Older certificate PDFs not yet OCR-integrated.",
            "future_version_note": "OCR scanned certificates for 2021–2023 and 2025 to complete the earliest-stage funnel.",
            "publication_status": "Useful internally; public caveat needed",
        },
        {
            "data_layer": "Assessor / parcel characteristics",
            "source_document_coverage": "Not yet integrated",
            "years_covered": "Pending",
            "records_currently_loaded": 0,
            "parse_quality": "N/A",
            "known_gap_or_caveat": "Current property type/value fields come from foreclosure documents, not a full assessor join.",
            "future_version_note": "Join parcel IDs to assessor fields: situs, property class, building sqft, year built, assessed value, and parcel geometry.",
            "publication_status": "Future version",
        },
        {
            "data_layer": "Hazard, zoning, access, and development overlays",
            "source_document_coverage": "Not yet integrated",
            "years_covered": "Pending",
            "records_currently_loaded": 0,
            "parse_quality": "N/A",
            "known_gap_or_caveat": "No GIS-based risk overlays yet.",
            "future_version_note": "Add flood, wetland, steep-slope, zoning, UGA, road frontage, and utility/septic indicators.",
            "publication_status": "Future version",
        },
    ]

    source_coverage = pd.DataFrame(source_rows)
    source_coverage["coverage_status"] = source_coverage.apply(status_from_coverage, axis=1)

    annual.to_csv(OUTPUT_DIR / "coverage_by_year.csv", index=False)
    source_coverage.to_csv(OUTPUT_DIR / "source_coverage_audit.csv", index=False)

    markdown_lines = [
        "# Data Coverage and Future-Version Notes",
        "",
        "This project combines county foreclosure-stage records, auction-sale outcomes, and excess-funds records into a parcel-year lifecycle table. Coverage is strongest for auction sales and final orders. Publication-stage coverage is strong for 2021–2025 except for the 2020 affidavit, which remains pending layout review. Certificate-stage coverage is still partial.",
        "",
        "## Source Coverage Summary",
        "",
        source_coverage.to_markdown(index=False),
        "",
        "## Annual Lifecycle Coverage",
        "",
        annual.to_markdown(index=False),
        "",
        "## Notes for Future Versions",
        "",
        "- Review OCR-flagged parcel-years rather than treating them as publication-final.",
        "- Verify repaired 13-digit APNs against a parcel/assessor lookup before relying on those rows for parcel-specific conclusions.",
        "- Complete the 2020 Affidavit of Publication as a targeted layout task, not a blocker for the current dataset.",
        "- OCR and merge the remaining scanned Certificates of Delinquency to complete the earliest-stage funnel.",
        "- Add assessor, zoning, hazard, and parcel-geometry data after the lifecycle pipeline is stable.",
        "",
    ]

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "data_coverage_and_future_work.md").write_text("\n".join(markdown_lines), encoding="utf-8")

    print("Wrote coverage audit outputs:")
    print(f"- {OUTPUT_DIR / 'coverage_by_year.csv'}")
    print(f"- {OUTPUT_DIR / 'source_coverage_audit.csv'}")
    print(f"- {DOCS_DIR / 'data_coverage_and_future_work.md'}")
    print()
    print("Coverage snapshot:")
    print(source_coverage[["data_layer", "coverage_status", "years_covered", "publication_status"]].to_string(index=False))


if __name__ == "__main__":
    main()
