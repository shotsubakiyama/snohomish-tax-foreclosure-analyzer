"""Parse searchable Snohomish foreclosure-stage PDFs, including page-spanning records.

Version 2 improvements:
- concatenates all searchable pages before splitting records;
- preserves starting and ending page numbers;
- captures multi-line fields up to the next known label;
- reduces false review flags caused by PDF page breaks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import bisect
import re
from typing import Iterable

import pandas as pd
import pdfplumber


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"

YEAR_RE = re.compile(r"\b(20(?:19|2[0-9]))\b")
RECORD_ANCHOR_RE = re.compile(
    r"(?im)^\s*(?:#\s*(\d{1,4})\s+|APN:\s*)?(\d{14})\b"
)

FIELD_LABELS = [
    "Taxpayer",
    "TAXPAYER/ASCEND OWNER/RECORD TITLE HOLDER/LIENHOLDER",
    "TAXPAYER/OWNER/RECORD TITLE HOLDER/LIENHOLDERS",
    "Owner/Record Title Holder/Other Parties of Interest",
    "Legal",
    "LEGAL",
    "Situs/local street address if known",
    "Situs",
    "TCA",
    "Use Code",
    "Size (acres)",
    "Size",
    "Land Value",
    "Improvement Value",
    "Tax Years",
    "TAX YEARS",
    "Amount due",
    "AMOUNT DUE",
    "Amount paid",
    "AMOUNT PAID",
]

NEXT_LABEL_PATTERN = "|".join(
    sorted((re.escape(label) for label in FIELD_LABELS), key=len, reverse=True)
)


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
        r"\b(?:SALE\s+)?DOES NOT INCLUDE\b", re.IGNORECASE
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
    tca_code: str | None
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
    source_start_page: int
    source_end_page: int
    source_relative_path: str
    raw_record_text: str
    extraction_method: str
    review_required_flag: bool
    review_reason: str


def normalize(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n:;-")
    return value or None


def money(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"([\d,]+(?:\.\d{1,2})?)", value)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"([\d.]+)", value)
    return float(match.group(1)) if match else None


def field_between(text: str, labels: Iterable[str]) -> str | None:
    label_pattern = "|".join(
        sorted((re.escape(label) for label in labels), key=len, reverse=True)
    )
    pattern = re.compile(
        rf"(?is)(?:^|\n)\s*(?:{label_pattern})\s*:\s*(.*?)"
        rf"(?=\n\s*(?:{NEXT_LABEL_PATTERN})\s*:|\Z)"
    )
    match = pattern.search(text)
    return normalize(match.group(1)) if match else None


def first_line_value(text: str, labels: Iterable[str]) -> str | None:
    label_pattern = "|".join(
        sorted((re.escape(label) for label in labels), key=len, reverse=True)
    )
    pattern = re.compile(rf"(?im)^\s*(?:{label_pattern})\s*:\s*(.+)$")
    match = pattern.search(text)
    return normalize(match.group(1)) if match else None


def infer_year(filename: str, document_text: str) -> int | None:
    filename_match = YEAR_RE.search(filename)
    if filename_match:
        return int(filename_match.group(1))

    years = [int(x) for x in YEAR_RE.findall(document_text[:5000])]
    return max(years) if years else None


def build_document_text(pdf: pdfplumber.PDF) -> tuple[str, list[int], list[int]]:
    """Return text, page start offsets, and page numbers for searchable pages."""
    parts: list[str] = []
    starts: list[int] = []
    page_numbers: list[int] = []
    current = 0

    for page_number, page in enumerate(pdf.pages, start=1):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue

        marker = f"\n\n[[SOURCE_PAGE_{page_number}]]\n"
        chunk = marker + page_text
        starts.append(current)
        page_numbers.append(page_number)
        parts.append(chunk)
        current += len(chunk)

    return "".join(parts), starts, page_numbers


def page_for_offset(offset: int, page_starts: list[int], page_numbers: list[int]) -> int:
    index = bisect.bisect_right(page_starts, offset) - 1
    if index < 0:
        return page_numbers[0]
    return page_numbers[index]


def remove_page_markers(text: str) -> str:
    return re.sub(r"\[\[SOURCE_PAGE_\d+\]\]", " ", text)


def capture_special_conditions(record_text: str) -> str | None:
    cleaned = remove_page_markers(record_text)
    lines: list[str] = []
    for line in cleaned.splitlines():
        upper = line.upper()
        if any(
            phrase in upper
            for phrase in (
                "PAID IN FULL",
                "ADMINISTRATIVELY PULLED",
                "REDEEMED",
                "MUST BE SOLD WITH",
                "DOES NOT INCLUDE",
                "SUBJECT TO",
                "NOTE-",
                "NOTE:",
            )
        ):
            lines.append(normalize(line) or "")
    return normalize(" | ".join(x for x in lines if x))


def split_document_records(
    document_text: str,
) -> list[tuple[int | None, str, int, int, str]]:
    anchors = list(RECORD_ANCHOR_RE.finditer(document_text))
    records: list[tuple[int | None, str, int, int, str]] = []

    for index, anchor in enumerate(anchors):
        start = anchor.start()
        end = anchors[index + 1].start() if index + 1 < len(anchors) else len(document_text)
        sequence = int(anchor.group(1)) if anchor.group(1) else None
        parcel = anchor.group(2)
        records.append((sequence, parcel, start, end, document_text[start:end]))

    return records


def parse_record(
    *,
    family: str,
    year: int | None,
    sequence: int | None,
    parcel: str,
    start_page: int,
    end_page: int,
    record_text: str,
    source_path: Path,
) -> ParsedStageRecord:
    clean_record = remove_page_markers(record_text)

    taxpayer = field_between(
        clean_record,
        [
            "Taxpayer",
            "TAXPAYER/ASCEND OWNER/RECORD TITLE HOLDER/LIENHOLDER",
        ],
    )
    owner = field_between(
        clean_record,
        [
            "Owner/Record Title Holder/Other Parties of Interest",
            "TAXPAYER/OWNER/RECORD TITLE HOLDER/LIENHOLDERS",
        ],
    )
    legal = field_between(clean_record, ["Legal", "LEGAL"])
    situs = field_between(
        clean_record,
        ["Situs/local street address if known", "Situs"],
    )

    tca = first_line_value(clean_record, ["TCA"])
    use_line = first_line_value(clean_record, ["Use Code"])
    use_code = None
    use_description = None
    if use_line:
        match = re.match(r"([A-Za-z0-9.-]+)\s*(.*)", use_line)
        if match:
            use_code = normalize(match.group(1))
            use_description = normalize(match.group(2))

    acreage = number(
        first_line_value(clean_record, ["Size (acres)", "Size"])
    )
    land_value = money(first_line_value(clean_record, ["Land Value"]))
    improvement_value = money(
        first_line_value(clean_record, ["Improvement Value"])
    )
    tax_years = field_between(clean_record, ["Tax Years", "TAX YEARS"])
    amount_due = money(
        first_line_value(clean_record, ["Amount due", "AMOUNT DUE"])
    )
    amount_paid = money(
        first_line_value(clean_record, ["Amount paid", "AMOUNT PAID"])
    )

    flags = {
        name: bool(pattern.search(clean_record))
        for name, pattern in STATUS_PATTERNS.items()
    }

    reasons: list[str] = []
    if year is None:
        reasons.append("year not inferred")
    if not legal:
        reasons.append("legal description missing")
    if not taxpayer and not owner:
        reasons.append("owner/taxpayer missing")
    if start_page != end_page:
        reasons.append("record spans pages; verify page join")

    return ParsedStageRecord(
        document_family=family,
        inferred_year=year,
        sale_or_property_number=sequence,
        parcel_number=parcel.zfill(14),
        taxpayer_name=taxpayer,
        owner_record_text=owner,
        legal_description=legal,
        situs_address=situs,
        tca_code=tca,
        use_code=use_code,
        use_description=use_description,
        acreage=acreage,
        land_value=land_value,
        improvement_value=improvement_value,
        tax_years=tax_years,
        amount_due=amount_due,
        amount_paid=amount_paid,
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
        special_condition_text=capture_special_conditions(clean_record),
        source_filename=source_path.name,
        source_start_page=start_page,
        source_end_page=end_page,
        source_relative_path=source_path.relative_to(PROJECT_ROOT).as_posix(),
        raw_record_text=normalize(clean_record) or "",
        extraction_method="pdf_text_document_regex_v2",
        review_required_flag=bool(reasons),
        review_reason="; ".join(reasons),
    )


def parse_pdf(path: Path) -> list[ParsedStageRecord]:
    with pdfplumber.open(path) as pdf:
        document_text, page_starts, page_numbers = build_document_text(pdf)

    if not document_text.strip():
        return []

    year = infer_year(path.name, document_text)
    records: list[ParsedStageRecord] = []

    for sequence, parcel, start, end, record_text in split_document_records(
        document_text
    ):
        records.append(
            parse_record(
                family=path.parent.name,
                year=year,
                sequence=sequence,
                parcel=parcel,
                start_page=page_for_offset(start, page_starts, page_numbers),
                end_page=page_for_offset(max(start, end - 1), page_starts, page_numbers),
                record_text=record_text,
                source_path=path,
            )
        )

    return records


def main() -> None:
    families = {"certificates", "affidavits", "final_orders"}
    paths = sorted(
        path
        for family in families
        for path in (RAW_DIR / family).glob("*.pdf")
    )

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
    review_df = (
        records_df[records_df["review_required_flag"]].copy()
        if not records_df.empty
        else records_df.copy()
    )

    records_df.to_csv(
        OUTPUT_DIR / "machine_readable_stage_records.csv",
        index=False,
    )
    stats_df.to_csv(
        OUTPUT_DIR / "machine_readable_stage_file_summary.csv",
        index=False,
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

    missing_legal = (
        int(records_df["legal_description"].isna().sum())
        if not records_df.empty
        else 0
    )
    missing_owner = (
        int(
            (
                records_df["taxpayer_name"].isna()
                & records_df["owner_record_text"].isna()
            ).sum()
        )
        if not records_df.empty
        else 0
    )

    print(f"Candidate PDFs scanned: {len(paths):,}")
    print(f"Parsed stage records: {len(records_df):,}")
    print(f"Files yielding records: {(stats_df['parsed_record_count'] > 0).sum():,}")
    print(f"Review-queue records: {len(review_df):,}")
    print(f"Records missing legal description: {missing_legal:,}")
    print(f"Records missing owner/taxpayer: {missing_owner:,}")
    print("Parser version: document-wide v2")


if __name__ == "__main__":
    main()
