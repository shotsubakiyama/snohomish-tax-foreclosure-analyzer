"""Inventory raw Snohomish County foreclosure source PDFs.

Scans data/raw recursively and writes a CSV/XLSX inventory with:
- document family
- inferred year
- filename and path
- file size
- page count
- searchable-text coverage
- parcel-number pattern counts
- status-phrase counts
- review flags
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re

import pandas as pd
import pdfplumber


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"


PARCEL_PATTERN = re.compile(r"\b\d{14}\b")
YEAR_PATTERN = re.compile(r"\b(20(?:19|2[0-9]))\b")

STATUS_PATTERNS = {
    "paid_in_full_count": re.compile(r"\bPAID IN FULL\b", re.IGNORECASE),
    "administratively_pulled_count": re.compile(
        r"\bADMINISTRATIVELY PULLED\b", re.IGNORECASE
    ),
    "must_be_sold_with_count": re.compile(
        r"\bMUST BE SOLD WITH\b", re.IGNORECASE
    ),
    "sale_does_not_include_count": re.compile(
        r"\bSALE DOES NOT INCLUDE\b", re.IGNORECASE
    ),
    "subject_to_count": re.compile(r"\bSUBJECT TO\b", re.IGNORECASE),
    "redeemed_count": re.compile(r"\bREDEEMED\b", re.IGNORECASE),
}


@dataclass
class InventoryRow:
    source_id: str
    document_family: str
    inferred_year: int | None
    filename: str
    relative_path: str
    file_size_bytes: int
    page_count: int
    pages_with_text: int
    text_coverage_pct: float
    total_extracted_characters: int
    parcel_number_occurrences: int
    unique_parcel_numbers: int
    paid_in_full_count: int
    administratively_pulled_count: int
    must_be_sold_with_count: int
    sale_does_not_include_count: int
    subject_to_count: int
    redeemed_count: int
    inferred_from_filename_flag: bool
    inferred_from_content_flag: bool
    review_required_flag: bool
    review_reason: str


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "source"


def infer_year(filename: str, extracted_text: str) -> tuple[int | None, bool, bool]:
    filename_years = [int(x) for x in YEAR_PATTERN.findall(filename)]
    content_years = [int(x) for x in YEAR_PATTERN.findall(extracted_text[:20000])]

    filename_year = filename_years[0] if filename_years else None
    content_year = content_years[0] if content_years else None

    if filename_year is not None:
        return filename_year, True, content_year is not None
    if content_year is not None:
        return content_year, False, True
    return None, False, False


def inspect_pdf(path: Path) -> InventoryRow:
    relative_path = path.relative_to(PROJECT_ROOT).as_posix()
    document_family = path.parent.name

    page_count = 0
    pages_with_text = 0
    text_parts: list[str] = []

    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages_with_text += 1
                    text_parts.append(text)
    except Exception as exc:
        return InventoryRow(
            source_id=slugify(f"{document_family}-{path.stem}"),
            document_family=document_family,
            inferred_year=None,
            filename=path.name,
            relative_path=relative_path,
            file_size_bytes=path.stat().st_size,
            page_count=0,
            pages_with_text=0,
            text_coverage_pct=0.0,
            total_extracted_characters=0,
            parcel_number_occurrences=0,
            unique_parcel_numbers=0,
            paid_in_full_count=0,
            administratively_pulled_count=0,
            must_be_sold_with_count=0,
            sale_does_not_include_count=0,
            subject_to_count=0,
            redeemed_count=0,
            inferred_from_filename_flag=False,
            inferred_from_content_flag=False,
            review_required_flag=True,
            review_reason=f"PDF open/extraction error: {exc}",
        )

    extracted_text = "\n".join(text_parts)
    parcel_numbers = PARCEL_PATTERN.findall(extracted_text)
    inferred_year, from_filename, from_content = infer_year(
        path.name, extracted_text
    )

    status_counts = {
        key: len(pattern.findall(extracted_text))
        for key, pattern in STATUS_PATTERNS.items()
    }

    coverage = round((pages_with_text / page_count * 100), 2) if page_count else 0.0
    review_reasons: list[str] = []

    if inferred_year is None:
        review_reasons.append("year not inferred")
    if coverage < 50:
        review_reasons.append("low searchable-text coverage")
    if len(parcel_numbers) == 0:
        review_reasons.append("no parcel-number patterns extracted")
    if document_family not in {
        "affidavits",
        "certificates",
        "excess_funds",
        "final_orders",
        "returns",
    }:
        review_reasons.append("unexpected document-family folder")

    return InventoryRow(
        source_id=slugify(f"{document_family}-{inferred_year or 'unknown'}-{path.stem}"),
        document_family=document_family,
        inferred_year=inferred_year,
        filename=path.name,
        relative_path=relative_path,
        file_size_bytes=path.stat().st_size,
        page_count=page_count,
        pages_with_text=pages_with_text,
        text_coverage_pct=coverage,
        total_extracted_characters=len(extracted_text),
        parcel_number_occurrences=len(parcel_numbers),
        unique_parcel_numbers=len(set(parcel_numbers)),
        paid_in_full_count=status_counts["paid_in_full_count"],
        administratively_pulled_count=status_counts[
            "administratively_pulled_count"
        ],
        must_be_sold_with_count=status_counts["must_be_sold_with_count"],
        sale_does_not_include_count=status_counts[
            "sale_does_not_include_count"
        ],
        subject_to_count=status_counts["subject_to_count"],
        redeemed_count=status_counts["redeemed_count"],
        inferred_from_filename_flag=from_filename,
        inferred_from_content_flag=from_content,
        review_required_flag=bool(review_reasons),
        review_reason="; ".join(review_reasons),
    )


def main() -> None:
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"Raw source folder not found: {RAW_DIR}")

    pdf_paths = sorted(RAW_DIR.rglob("*.pdf"))
    if not pdf_paths:
        raise FileNotFoundError(f"No PDFs found under: {RAW_DIR}")

    rows = [asdict(inspect_pdf(path)) for path in pdf_paths]
    df = pd.DataFrame(rows).sort_values(
        ["document_family", "inferred_year", "filename"],
        na_position="last",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "source_inventory.csv"
    xlsx_path = OUTPUT_DIR / "source_inventory.xlsx"

    df.to_csv(csv_path, index=False)

    summary = (
        df.groupby("document_family", as_index=False)
        .agg(
            file_count=("filename", "count"),
            total_pages=("page_count", "sum"),
            searchable_pages=("pages_with_text", "sum"),
            total_unique_parcel_patterns=("unique_parcel_numbers", "sum"),
            review_required_files=("review_required_flag", "sum"),
        )
    )

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Source Inventory", index=False)
        summary.to_excel(writer, sheet_name="Family Summary", index=False)

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

    print(f"Inventoried {len(df):,} PDF files")
    print(f"Total pages: {int(df['page_count'].sum()):,}")
    print(f"Files needing review: {int(df['review_required_flag'].sum()):,}")
    print(f"CSV: {csv_path}")
    print(f"Excel: {xlsx_path}")


if __name__ == "__main__":
    main()
