"""Parse searchable Snohomish foreclosure-stage PDFs.

Version 3:
- only explicit county record markers (#123 or APN:) start a record;
- referenced parcel numbers inside notes no longer create false rows;
- page-spanning records are tracked separately from true review exceptions;
- duplicate parcel-stage rows are detected and flagged.
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

# Critical v3 change: a record must begin with an explicit source marker.
RECORD_ANCHOR_RE = re.compile(
    r"(?im)^\s*(?:#\s*(\d{1,4})\s+(\d{14})\b|APN:\s*(\d{14})\b)"
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
        r"\b(?:SALE\s+)?DOES NOT INCLUDE\b|\bNOT INCLUDED IN FORECLOSURE\b",
        re.IGNORECASE,
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
    record_spans_pages_flag: bool
    source_relative_path: str
    raw_record_text: str
    extraction_method: str
    duplicate_key_flag: bool
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
    return float(match.group(1).replace(",", "")) if match else None


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
    match = re.search(rf"(?im)^\s*(?:{label_pattern})\s*:\s*(.+)$", text)
    return normalize(match.group(1)) if match else None


def infer_year(filename: str, document_text: str) -> int | None:
    match = YEAR_RE.search(filename)
    if match:
        return int(match.group(1))
    years = [int(x) for x in YEAR_RE.findall(document_text[:5000])]
    return max(years) if years else None


def build_document_text(pdf: pdfplumber.PDF) -> tuple[str, list[int], list[int]]:
    parts, starts, pages = [], [], []
    current = 0
    for page_number, page in enumerate(pdf.pages, start=1):
        text = page.extract_text() or ""
        if not text.strip():
            continue
        chunk = f"\n\n[[SOURCE_PAGE_{page_number}]]\n{text}"
        starts.append(current)
        pages.append(page_number)
        parts.append(chunk)
        current += len(chunk)
    return "".join(parts), starts, pages


def page_for_offset(offset: int, starts: list[int], pages: list[int]) -> int:
    index = bisect.bisect_right(starts, offset) - 1
    return pages[max(index, 0)]


def remove_page_markers(text: str) -> str:
    return re.sub(r"\[\[SOURCE_PAGE_\d+\]\]", " ", text)


def capture_special_conditions(text: str) -> str | None:
    lines = []
    for line in remove_page_markers(text).splitlines():
        upper = line.upper()
        if any(
            phrase in upper
            for phrase in (
                "PAID IN FULL",
                "ADMINISTRATIVELY PULLED",
                "REDEEMED",
                "MUST BE SOLD WITH",
                "DOES NOT INCLUDE",
                "NOT INCLUDED IN FORECLOSURE",
                "SUBJECT TO",
                "NOTE-",
                "NOTE:",
            )
        ):
            lines.append(normalize(line) or "")
    return normalize(" | ".join(x for x in lines if x))


def split_document_records(document_text: str):
    anchors = list(RECORD_ANCHOR_RE.finditer(document_text))
    for i, anchor in enumerate(anchors):
        start = anchor.start()
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(document_text)
        sequence = int(anchor.group(1)) if anchor.group(1) else None
        parcel = anchor.group(2) or anchor.group(3)
        yield sequence, parcel, start, end, document_text[start:end]


def parse_record(
    family, year, sequence, parcel, start_page, end_page, record_text, source_path
):
    clean = remove_page_markers(record_text)
    taxpayer = field_between(
        clean,
        ["Taxpayer", "TAXPAYER/ASCEND OWNER/RECORD TITLE HOLDER/LIENHOLDER"],
    )
    owner = field_between(
        clean,
        [
            "Owner/Record Title Holder/Other Parties of Interest",
            "TAXPAYER/OWNER/RECORD TITLE HOLDER/LIENHOLDERS",
        ],
    )
    legal = field_between(clean, ["Legal", "LEGAL"])
    situs = field_between(clean, ["Situs/local street address if known", "Situs"])
    tca = first_line_value(clean, ["TCA"])
    use_line = first_line_value(clean, ["Use Code"])
    use_code, use_description = None, None
    if use_line:
        m = re.match(r"([A-Za-z0-9.-]+)\s*(.*)", use_line)
        if m:
            use_code = normalize(m.group(1))
            use_description = normalize(m.group(2))

    flags = {
        name: bool(pattern.search(clean)) for name, pattern in STATUS_PATTERNS.items()
    }

    reasons = []
    if year is None:
        reasons.append("year not inferred")
    if not legal:
        reasons.append("legal description missing")
    if not taxpayer and not owner:
        reasons.append("owner/taxpayer missing")

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
        acreage=number(first_line_value(clean, ["Size (acres)", "Size"])),
        land_value=money(first_line_value(clean, ["Land Value"])),
        improvement_value=money(first_line_value(clean, ["Improvement Value"])),
        tax_years=field_between(clean, ["Tax Years", "TAX YEARS"]),
        amount_due=money(first_line_value(clean, ["Amount due", "AMOUNT DUE"])),
        amount_paid=money(first_line_value(clean, ["Amount paid", "AMOUNT PAID"])),
        paid_in_full_flag=flags["paid_in_full_flag"],
        administratively_pulled_flag=flags["administratively_pulled_flag"],
        redeemed_flag=flags["redeemed_flag"],
        must_be_sold_with_flag=flags["must_be_sold_with_flag"],
        sale_does_not_include_flag=flags["sale_does_not_include_flag"],
        subject_to_flag=flags["subject_to_flag"],
        special_condition_text=capture_special_conditions(clean),
        source_filename=source_path.name,
        source_start_page=start_page,
        source_end_page=end_page,
        record_spans_pages_flag=start_page != end_page,
        source_relative_path=source_path.relative_to(PROJECT_ROOT).as_posix(),
        raw_record_text=normalize(clean) or "",
        extraction_method="pdf_text_explicit_anchor_v3",
        duplicate_key_flag=False,
        review_required_flag=bool(reasons),
        review_reason="; ".join(reasons),
    )


def parse_pdf(path: Path):
    with pdfplumber.open(path) as pdf:
        document_text, starts, pages = build_document_text(pdf)
    if not document_text.strip():
        return []
    year = infer_year(path.name, document_text)
    records = []
    for sequence, parcel, start, end, text in split_document_records(document_text):
        records.append(
            parse_record(
                path.parent.name,
                year,
                sequence,
                parcel,
                page_for_offset(start, starts, pages),
                page_for_offset(max(start, end - 1), starts, pages),
                text,
                path,
            )
        )
    return records


def main():
    families = {"certificates", "affidavits", "final_orders"}
    paths = sorted(
        path for family in families for path in (RAW_DIR / family).glob("*.pdf")
    )

    parsed, file_stats = [], []
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

    records_df = pd.DataFrame([asdict(r) for r in parsed])
    stats_df = pd.DataFrame(file_stats)

    if not records_df.empty:
        key_cols = [
            "document_family",
            "inferred_year",
            "source_filename",
            "sale_or_property_number",
            "parcel_number",
        ]
        duplicate_mask = records_df.duplicated(key_cols, keep=False)
        records_df.loc[duplicate_mask, "duplicate_key_flag"] = True
        records_df.loc[duplicate_mask, "review_required_flag"] = True
        records_df.loc[duplicate_mask, "review_reason"] = records_df.loc[
            duplicate_mask, "review_reason"
        ].apply(
            lambda x: "; ".join(filter(None, [x, "duplicate source key"]))
        )

        records_df = records_df.sort_values(
            [
                "document_family",
                "inferred_year",
                "sale_or_property_number",
                "parcel_number",
            ],
            na_position="last",
        ).reset_index(drop=True)

    review_df = records_df[records_df["review_required_flag"]].copy()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records_df.to_csv(OUTPUT_DIR / "machine_readable_stage_records.csv", index=False)
    stats_df.to_csv(
        OUTPUT_DIR / "machine_readable_stage_file_summary.csv", index=False
    )
    review_df.to_csv(
        OUTPUT_DIR / "machine_readable_stage_review_queue.csv", index=False
    )

    with pd.ExcelWriter(
        OUTPUT_DIR / "machine_readable_stage_records.xlsx", engine="openpyxl"
    ) as writer:
        records_df.to_excel(writer, sheet_name="Parsed Records", index=False)
        stats_df.to_excel(writer, sheet_name="File Summary", index=False)
        review_df.to_excel(writer, sheet_name="Review Queue", index=False)
        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for cells in ws.columns:
                width = min(
                    max(
                        max(
                            len(str(c.value)) if c.value is not None else 0
                            for c in cells
                        )
                        + 2,
                        11,
                    ),
                    50,
                )
                ws.column_dimensions[cells[0].column_letter].width = width

    print(f"Candidate PDFs scanned: {len(paths):,}")
    print(f"Parsed stage records: {len(records_df):,}")
    print(f"Files yielding records: {(stats_df['parsed_record_count'] > 0).sum():,}")
    print(f"Review-queue records: {len(review_df):,}")
    print(f"Page-spanning records: {int(records_df['record_spans_pages_flag'].sum()):,}")
    print(f"Duplicate source keys: {int(records_df['duplicate_key_flag'].sum()):,}")
    print("Parser version: explicit-anchor v3")


if __name__ == "__main__":
    main()
