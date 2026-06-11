"""Parse machine-readable Snohomish foreclosure-stage PDFs.

The parser is intentionally conservative:
- it only parses pages with extracted text;
- it preserves raw source text;
- it records source filename/page;
- it routes uncertain records to review rather than inventing values.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import re
from typing import Iterable

import pandas as pd
import pdfplumber


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"


PARCEL_RE = re.compile(r"(?im)^\s*(?:APN:|PARCEL\s*#?|#)?\s*(\d{14})\b")
SALE_NUMBER_RE = re.compile(r"(?im)^\s*#\s*(\d{1,4})\s+(\d{14})\b")
YEAR_RE = re.compile(r"\b(20(?:19|2[0-9]))\b")
MONEY_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{1,2})?)")
NUMBER_RE = re.compile(r"([\d.]+)")


FIELD_PATTERNS = {
    "taxpayer_name": [
        re.compile(r"(?im)^\s*Taxpayer:\s*(.+)$"),
        re.compile(r"(?im)^\s*TAXPAYER/ASCEND OWNER/RECORD TITLE HOLDER/LIENHOLDER:\s*(.+)$"),
    ],
    "owner_record_text": [
        re.compile(r"(?im)^\s*Owner/Record Title Holder/Other Parties of Interest:\s*(.+)$"),
        re.compile(r"(?im)^\s*TAXPAYER/OWNER/RECORD TITLE HOLDER/LIENHOLDERS:\s*(.+)$"),
    ],
    "legal_description": [
        re.compile(r"(?im)^\s*Legal:\s*(.+)$"),
        re.compile(r"(?im)^\s*LEGAL:\s*(.+)$"),
    ],
    "situs_address": [
        re.compile(r"(?im)^\s*Situs/local street address if known:\s*(.+)$"),
        re.compile(r"(?im)^\s*Situs:\s*(.+)$"),
    ],
    "use_code": [
        re.compile(r"(?im)^\s*Use Code:\s*([A-Za-z0-9.-]+)"),
        re.compile(r"(?im)^\s*TCA:\s*([A-Za-z0-9.-]+)"),
    ],
    "use_description": [
        re.compile(r"(?im)^\s*Use Code:\s*[A-Za-z0-9.-]+\s+(.+)$"),
        re.compile(r"(?im)^\s*TCA:\s*[A-Za-z0-9.-]+\s+Use Code:\s*[A-Za-z0-9.-]+\s+(.+)$"),
    ],
    "acreage": [
        re.compile(r"(?im)^\s*Size \(acres\):\s*([\d.]+)"),
        re.compile(r"(?im)^\s*Size:\s*([\d.]+)\s*Acres"),
    ],
    "land_value": [
        re.compile(r"(?im)^\s*Land Value:\s*\$?\s*([\d,]+(?:\.\d{1,2})?)"),
    ],
    "improvement_value": [
        re.compile(r"(?im)^\s*Improvement Value:\s*\$?\s*([\d,]+(?:\.\d{1,2})?)"),
    ],
    "tax_years": [
        re.compile(r"(?im)^\s*TAX YEARS:\s*(.+)$"),
        re.compile(r"(?im)^\s*Tax Years:\s*(.+)$"),
    ],
    "amount_due": [
        re.compile(r"(?im)^\s*AMOUNT DUE.*?:\s*\$?\s*([\d,]+(?:\.\d{1,2})?)"),
        re.compile(r"(?im)^\s*Amount due.*?:\s*\$?\s*([\d,]+(?:\.\d{1,2})?)"),
    ],
    "amount_paid": [
        re.compile(r"(?im)^\s*AMOUNT PAID.*?:\s*\$?\s*([\d,]+(?:\.\d{1,2})?)"),
        re.compile(r"(?im)^\s*Amount paid.*?:\s*\$?\s*([\d,]+(?:\.\d{1,2})?)"),
    ],
}


STATUS_PATTERNS = {
    "paid_in_full_flag": re.compile(r"\bPAID IN FULL\b", re.IGNORECASE),
    "administratively_pulled_flag": re.compile(
        r"\bADMINISTRATIVELY PULLED\b", re.IGNORECASE
    ),
    "redeemed_flag": re.compile(r"\bREDEEMED\b", re.IGNORECASE),
    "must_be_sold_with_flag": re.compile(
        r"\bMUST BE SOLD WITH\b", re.IGNORECASE
    ),
    "sale_does_not_include_flag": re.compile(
        r"\bSALE DOES NOT INCLUDE\b", re.IGNORECASE
    ),
    "subject_to_flag": re.compile(r"\bSUBJECT TO\b", re.IGNORECASE),
}


@dataclass
class ParsedStageRecord:
    document_family: str
    inferred_year: int | None
    sale_or_property_number: int | None
    parcel_number: str
    taxpayer_name: str | None
    owner_record_text: str | None
    legal_description: str | None
    situs_address: str | None
    use_code: str | None
    use_description: str | None
    acreage: float | None
    land_value: float | None
    improvement_value: float | None
    tax_years: str | None
    amount_due: float | None
    amount_paid: float | None
    paid_in_full_flag: bool
    administratively_pulled_flag: bool
    redeemed_flag: bool
    must_be_sold_with_flag: bool
    sale_does_not_include_flag: bool
    subject_to_flag: bool
    special_condition_text: str | None
    source_filename: str
    source_page: int
    source_relative_path: str
    raw_record_text: str
    extraction_method: str
    review_required_flag: bool
    review_reason: str


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def money_to_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def first_match(text: str, patterns: Iterable[re.Pattern]) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return clean_text(match.group(1))
    return None


def infer_year(filename: str, text: str) -> int | None:
    filename_match = YEAR_RE.search(filename)
    if filename_match:
        return int(filename_match.group(1))

    # Prefer court/certificate years near the beginning of the document.
    early = text[:3000]
    years = [int(x) for x in YEAR_RE.findall(early)]
    if years:
        return max(years)
    return None


def split_page_into_records(text: str) -> list[tuple[int | None, str, str]]:
    """Return tuples of (sale/property number, parcel number, record text)."""
    anchors: list[tuple[int, int | None, str]] = []

    for match in SALE_NUMBER_RE.finditer(text):
        anchors.append((match.start(), int(match.group(1)), match.group(2)))

    # Fallback for APN-led records where there is no explicit # sequence.
    if not anchors:
        for match in PARCEL_RE.finditer(text):
            anchors.append((match.start(), None, match.group(1)))

    if not anchors:
        return []

    records: list[tuple[int | None, str, str]] = []
    for index, (start, sequence, parcel) in enumerate(anchors):
        end = anchors[index + 1][0] if index + 1 < len(anchors) else len(text)
        records.append((sequence, parcel, text[start:end].strip()))
    return records


def capture_special_conditions(record_text: str) -> str | None:
    lines = []
    for line in record_text.splitlines():
        normalized = line.strip()
        upper = normalized.upper()
        if any(
            phrase in upper
            for phrase in (
                "PAID IN FULL",
                "ADMINISTRATIVELY PULLED",
                "REDEEMED",
                "MUST BE SOLD WITH",
                "SALE DOES NOT INCLUDE",
                "SUBJECT TO",
            )
        ):
            lines.append(normalized)
    return clean_text(" | ".join(lines)) if lines else None


def parse_record(
    *,
    document_family: str,
    year: int | None,
    sequence: int | None,
    parcel_number: str,
    record_text: str,
    source_path: Path,
    page_number: int,
) -> ParsedStageRecord:
    extracted: dict[str, str | None] = {
        field: first_match(record_text, patterns)
        for field, patterns in FIELD_PATTERNS.items()
    }

    review_reasons: list[str] = []
    if year is None:
        review_reasons.append("year not inferred")
    if not extracted["legal_description"]:
        review_reasons.append("legal description missing")
    if not extracted["taxpayer_name"] and not extracted["owner_record_text"]:
        review_reasons.append("owner/taxpayer missing")

    flags = {
        name: bool(pattern.search(record_text))
        for name, pattern in STATUS_PATTERNS.items()
    }

    return ParsedStageRecord(
        document_family=document_family,
        inferred_year=year,
        sale_or_property_number=sequence,
        parcel_number=parcel_number.zfill(14),
        taxpayer_name=extracted["taxpayer_name"],
        owner_record_text=extracted["owner_record_text"],
        legal_description=extracted["legal_description"],
        situs_address=extracted["situs_address"],
        use_code=extracted["use_code"],
        use_description=extracted["use_description"],
        acreage=float(extracted["acreage"]) if extracted["acreage"] else None,
        land_value=money_to_float(extracted["land_value"]),
        improvement_value=money_to_float(extracted["improvement_value"]),
        tax_years=extracted["tax_years"],
        amount_due=money_to_float(extracted["amount_due"]),
        amount_paid=money_to_float(extracted["amount_paid"]),
        paid_in_full_flag=flags["paid_in_full_flag"],
        administratively_pulled_flag=flags[
            "administratively_pulled_flag"
        ],
        redeemed_flag=flags["redeemed_flag"],
        must_be_sold_with_flag=flags["must_be_sold_with_flag"],
        sale_does_not_include_flag=flags[
            "sale_does_not_include_flag"
        ],
        subject_to_flag=flags["subject_to_flag"],
        special_condition_text=capture_special_conditions(record_text),
        source_filename=source_path.name,
        source_page=page_number,
        source_relative_path=source_path.relative_to(PROJECT_ROOT).as_posix(),
        raw_record_text=clean_text(record_text) or "",
        extraction_method="pdf_text_regex",
        review_required_flag=bool(review_reasons),
        review_reason="; ".join(review_reasons),
    )


def parse_pdf(path: Path) -> list[ParsedStageRecord]:
    family = path.parent.name
    records: list[ParsedStageRecord] = []

    with pdfplumber.open(path) as pdf:
        document_text_parts: list[str] = []
        page_texts: list[str] = []

        for page in pdf.pages:
            page_text = page.extract_text() or ""
            page_texts.append(page_text)
            if page_text.strip():
                document_text_parts.append(page_text)

        document_text = "\n".join(document_text_parts)
        year = infer_year(path.name, document_text)

        for page_index, page_text in enumerate(page_texts, start=1):
            if not page_text.strip():
                continue

            for sequence, parcel, record_text in split_page_into_records(page_text):
                records.append(
                    parse_record(
                        document_family=family,
                        year=year,
                        sequence=sequence,
                        parcel_number=parcel,
                        record_text=record_text,
                        source_path=path,
                        page_number=page_index,
                    )
                )

    return records


def main() -> None:
    candidate_families = {"certificates", "affidavits", "final_orders"}
    paths = sorted(
        path
        for family in candidate_families
        for path in (RAW_DIR / family).glob("*.pdf")
    )

    if not paths:
        raise FileNotFoundError("No candidate PDFs found.")

    parsed: list[ParsedStageRecord] = []
    file_stats: list[dict] = []

    for path in paths:
        try:
            records = parse_pdf(path)
            parsed.extend(records)
            file_stats.append(
                {
                    "document_family": path.parent.name,
                    "filename": path.name,
                    "parsed_record_count": len(records),
                    "parse_error": "",
                }
            )
        except Exception as exc:
            file_stats.append(
                {
                    "document_family": path.parent.name,
                    "filename": path.name,
                    "parsed_record_count": 0,
                    "parse_error": str(exc),
                }
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    records_df = pd.DataFrame([asdict(record) for record in parsed])
    if not records_df.empty:
        records_df = records_df.sort_values(
            [
                "document_family",
                "inferred_year",
                "sale_or_property_number",
                "parcel_number",
            ],
            na_position="last",
        ).reset_index(drop=True)

    stats_df = pd.DataFrame(file_stats)

    records_df.to_csv(
        OUTPUT_DIR / "machine_readable_stage_records.csv",
        index=False,
    )
    stats_df.to_csv(
        OUTPUT_DIR / "machine_readable_stage_file_summary.csv",
        index=False,
    )

    review_df = (
        records_df[records_df["review_required_flag"]]
        if not records_df.empty
        else records_df
    )
    review_df.to_csv(
        OUTPUT_DIR / "machine_readable_stage_review_queue.csv",
        index=False,
    )

    with pd.ExcelWriter(
        OUTPUT_DIR / "machine_readable_stage_records.xlsx",
        engine="openpyxl",
    ) as writer:
        records_df.to_excel(writer, sheet_name="Parsed Records", index=False)
        stats_df.to_excel(writer, sheet_name="File Summary", index=False)
        review_df.to_excel(writer, sheet_name="Review Queue", index=False)

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

    print(f"Candidate PDFs scanned: {len(paths):,}")
    print(f"Parsed stage records: {len(records_df):,}")
    print(f"Files yielding records: {(stats_df['parsed_record_count'] > 0).sum():,}")
    print(f"Review-queue records: {len(review_df):,}")
    print(
        "Output:",
        OUTPUT_DIR / "machine_readable_stage_records.xlsx",
    )


if __name__ == "__main__":
    main()
