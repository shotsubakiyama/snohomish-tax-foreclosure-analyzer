"""OCR parsing for Snohomish County Final Orders of Sale.

Version 5 fixes owner-label recognition for:
- LIENHOLDER / LIENHOLDERS
- LEINHOLDER / LEINHOLDERS (source/OCR misspelling)

It also tolerates stray OCR punctuation and underscores before APN anchors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import shutil
import sys

import fitz
import pandas as pd
import pytesseract
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "data" / "raw" / "final_orders"
CACHE_DIR = PROJECT_ROOT / "data" / "private" / "ocr_cache" / "final_orders"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "public"

YEAR_RE = re.compile(r"\b(20(?:19|2[0-9]))\b")

# Permit arbitrary non-alphanumeric OCR debris before APN/# anchors.
APN_ANCHOR_RE = re.compile(
    r"(?im)^[^A-Za-z0-9]{0,20}APN\s*[:;.,]?\s*([0-9OIl|]{13,14})\b"
)
GENERAL_ANCHOR_RE = re.compile(
    r"(?im)^[^A-Za-z0-9]{0,20}(?:(\d{1,4})[^A-Za-z0-9]+)?([0-9OIl|]{13,14})\b"
)

# Correctly supports LIENHOLDER and common misspelling LEINHOLDER.
LIENHOLDER_REGEX = r"L(?:IE|EI)NHOLDERS?"

OWNER_CONTEXT_RE = re.compile(
    rf"(?is)"
    rf"(?:"
    rf"TAXPAYER(?:/REPUTED OWNER)?"
    rf"(?:/ASCEND OWNER)?"
    rf"(?:/OWNER)?"
    rf"(?:/RECORD TITLE HOLDER)?"
    rf"(?:/OTHER PARTIES OF INTEREST)?"
    rf"(?:/{LIENHOLDER_REGEX})?"
    rf"|OWNER/RECORD TITLE HOLDER/OTHER PARTIES OF INTEREST"
    rf")"
    rf"\s*[:;]"
)

STATUS_PATTERNS = {
    "paid_in_full_flag": re.compile(r"\bPAID\s*IN[-\s]*FULL\b", re.IGNORECASE),
    "administratively_pulled_flag": re.compile(
        r"\bADMINISTRATIVELY\s+PULLED\b", re.IGNORECASE
    ),
    "redeemed_flag": re.compile(r"\bREDEEMED\b", re.IGNORECASE),
    "must_be_sold_with_flag": re.compile(
        r"\bMUST\s+BE\s+(?:REDEEMED/)?SOLD\s+WITH\b", re.IGNORECASE
    ),
    "sale_does_not_include_flag": re.compile(
        r"\b(?:SALE\s+)?DOES\s+NOT\s+INCLUDE\b"
        r"|\bNOT\s+INCLUDED\s+IN\s+FORECLOSURE\b"
        r"|\bNOT\s+PART\s+OF\s+TAX\s+LIEN\s+FORECLOSURE\b",
        re.IGNORECASE,
    ),
    "subject_to_flag": re.compile(r"\bSUBJECT\s+TO\b", re.IGNORECASE),
}

OWNER_LABEL_REGEX = (
    rf"(?:"
    rf"TAXPAYER(?:/REPUTED OWNER)?"
    rf"(?:/ASCEND OWNER)?"
    rf"(?:/OWNER)?"
    rf"(?:/RECORD TITLE HOLDER)?"
    rf"(?:/OTHER PARTIES OF INTEREST)?"
    rf"(?:/{LIENHOLDER_REGEX})?"
    rf"|OWNER/RECORD TITLE HOLDER/OTHER PARTIES OF INTEREST"
    rf")"
)

NEXT_LABEL_REGEX = (
    rf"{OWNER_LABEL_REGEX}"
    r"|LEGAL"
    r"|SITUS(?:/LOCAL STREET ADDRESS IF KNOWN)?"
    r"|TCA"
    r"|USE CODE"
    r"|SIZE(?: \(ACRES\))?"
    r"|LAND VALUE"
    r"|IMPROVEMENT VALUE"
    r"|TAX YEARS"
    r"|AMOUNT (?:DUE|PAID).*?"
)


@dataclass
class OCRRecord:
    auction_year: int | None
    property_number: int | None
    parcel_number: str
    parcel_number_raw: str
    parcel_repair_applied_flag: bool
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
    extraction_method: str
    anchor_quality: str
    duplicate_key_flag: bool
    review_required_flag: bool
    review_reason: str
    raw_ocr_text: str


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n:;|,-")
    return value or None


def normalize_parcel(raw: str) -> tuple[str | None, bool]:
    translation = str.maketrans(
        {"O": "0", "o": "0", "I": "1", "l": "1", "|": "1"}
    )
    digits = re.sub(r"\D", "", raw.translate(translation))
    if len(digits) == 14:
        return digits, False
    if len(digits) == 13:
        return "0" + digits, True
    return None, False


def money(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"([\d,]+(?:\.\d{1,2})?)", value)
    return float(match.group(1).replace(",", "")) if match else None


def number(value: str | None) -> float | None:
    """Parse one numeric value from noisy OCR text."""
    if not value:
        return None

    match = re.search(r"(\d+(?:\.\d+)?)", value)
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def field_between(text: str, label_regex: str) -> str | None:
    pattern = re.compile(
        rf"(?is)(?:^|\n)\s*[^A-Za-z0-9]{{0,10}}(?:{label_regex})\s*[:;]\s*(.*?)"
        rf"(?=\n\s*[^A-Za-z0-9]{{0,10}}(?:{NEXT_LABEL_REGEX})\s*[:;]|\Z)"
    )
    match = pattern.search(text)
    return clean(match.group(1)) if match else None


def first_line(text: str, label_regex: str) -> str | None:
    match = re.search(
        rf"(?im)^\s*[^A-Za-z0-9]{{0,10}}(?:{label_regex})\s*[:;]\s*(.+)$",
        text,
    )
    return clean(match.group(1)) if match else None


def find_tesseract() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]:
        if candidate.exists():
            return str(candidate)
    return None


def infer_year(filename: str, text: str) -> int | None:
    match = YEAR_RE.search(filename)
    if match:
        return int(match.group(1))
    years = [int(x) for x in YEAR_RE.findall(text[:5000])]
    return max(years) if years else None


def cache_path(pdf_path: Path, page_number: int) -> Path:
    folder = CACHE_DIR / pdf_path.stem
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"page_{page_number:03d}.txt"


def render_and_ocr_page(page: fitz.Page, dpi: int = 300) -> str:
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return pytesseract.image_to_string(
        image, lang="eng", config="--oem 3 --psm 6"
    )


def ocr_pdf(pdf_path: Path) -> list[str]:
    document = fitz.open(pdf_path)
    texts = []
    for index, page in enumerate(document, start=1):
        cached = cache_path(pdf_path, index)
        if cached.exists():
            text = cached.read_text(encoding="utf-8", errors="replace")
        else:
            print(f"OCR {pdf_path.name}: page {index}/{len(document)}")
            text = render_and_ocr_page(page)
            cached.write_text(text, encoding="utf-8")
        texts.append(text)
    document.close()
    return texts


def build_document_text(page_texts: list[str]) -> str:
    return "\n".join(
        f"\n[[SOURCE_PAGE_{i}]]\n{text}"
        for i, text in enumerate(page_texts, start=1)
    )


def page_at_offset(document_text: str, offset: int) -> int:
    markers = list(
        re.finditer(r"\[\[SOURCE_PAGE_(\d+)\]\]", document_text[:offset])
    )
    return int(markers[-1].group(1)) if markers else 1


def find_anchors(document_text: str) -> list[dict]:
    candidates = []

    for match in APN_ANCHOR_RE.finditer(document_text):
        normalized, repaired = normalize_parcel(match.group(1))
        if not normalized:
            continue
        context = document_text[match.end(): match.end() + 800]
        if not OWNER_CONTEXT_RE.search(context):
            continue
        candidates.append(
            {
                "start": match.start(),
                "property_number": None,
                "parcel_number": normalized,
                "parcel_number_raw": match.group(1),
                "repair": repaired,
                "anchor_quality": "apn_context_validated",
            }
        )

    for match in GENERAL_ANCHOR_RE.finditer(document_text):
        normalized, repaired = normalize_parcel(match.group(2))
        if not normalized:
            continue
        context = document_text[match.end(): match.end() + 800]
        if not OWNER_CONTEXT_RE.search(context):
            continue
        candidates.append(
            {
                "start": match.start(),
                "property_number": int(match.group(1)) if match.group(1) else None,
                "parcel_number": normalized,
                "parcel_number_raw": match.group(2),
                "repair": repaired,
                "anchor_quality": (
                    "numbered_context_validated"
                    if match.group(1)
                    else "bare_context_validated"
                ),
            }
        )

    priority = {
        "apn_context_validated": 3,
        "numbered_context_validated": 2,
        "bare_context_validated": 1,
    }
    by_start = {}
    for row in candidates:
        current = by_start.get(row["start"])
        if current is None or priority[row["anchor_quality"]] > priority[current["anchor_quality"]]:
            by_start[row["start"]] = row
    return sorted(by_start.values(), key=lambda row: row["start"])


def special_text(text: str) -> str | None:
    lines = []
    for line in text.splitlines():
        upper = line.upper()
        if any(
            phrase in upper
            for phrase in (
                "PAID IN FULL",
                "PAID-IN-FULL",
                "PAIDINFULL",
                "ADMINISTRATIVELY PULLED",
                "REDEEMED",
                "MUST BE REDEEMED/SOLD",
                "MUST BE SOLD WITH",
                "DOES NOT INCLUDE",
                "NOT INCLUDED IN FORECLOSURE",
                "NOT PART OF TAX LIEN FORECLOSURE",
                "SUBJECT TO",
                "NOTE:",
                "NOTE-",
            )
        ):
            lines.append(clean(line) or "")
    return clean(" | ".join(x for x in lines if x))


def parse_pdf(pdf_path: Path):
    page_texts = ocr_pdf(pdf_path)
    document_text = build_document_text(page_texts)
    year = infer_year(pdf_path.name, document_text)
    anchors = find_anchors(document_text)

    records = []
    for index, anchor in enumerate(anchors):
        start = anchor["start"]
        end = anchors[index + 1]["start"] if index + 1 < len(anchors) else len(document_text)
        raw = document_text[start:end]
        text = re.sub(r"\[\[SOURCE_PAGE_\d+\]\]", " ", raw)

        start_page = page_at_offset(document_text, start)
        end_page = page_at_offset(document_text, max(start, end - 1))

        owner_text = field_between(text, OWNER_LABEL_REGEX)
        legal = field_between(text, r"LEGAL")
        situs = field_between(text, r"SITUS(?:/LOCAL STREET ADDRESS IF KNOWN)?")

        tca_line = first_line(text, r"TCA")
        tca_code = None
        use_code = None
        use_description = None
        acreage = None

        if tca_line:
            tca_match = re.match(r"([A-Za-z0-9.-]+)", tca_line)
            if tca_match:
                tca_code = clean(tca_match.group(1))
            use_match = re.search(
                r"Use Code\s*:\s*([A-Za-z0-9.-]+)\s*(.*?)"
                r"(?:\s+Size(?: \(acres\))?\s*:\s*([\d.]+))?$",
                tca_line,
                re.IGNORECASE,
            )
            if use_match:
                use_code = clean(use_match.group(1))
                use_description = clean(use_match.group(2))
                acreage = number(use_match.group(3))

        if use_code is None:
            use_line = first_line(text, r"USE CODE")
            if use_line:
                match = re.match(
                    r"([A-Za-z0-9.-]+)\s*(.*?)"
                    r"(?:\s+Size(?: \(acres\))?\s*:\s*([\d.]+))?$",
                    use_line,
                    re.IGNORECASE,
                )
                if match:
                    use_code = clean(match.group(1))
                    use_description = clean(match.group(2))
                    acreage = number(match.group(3))

        if acreage is None:
            acreage = number(first_line(text, r"SIZE(?: \(ACRES\))?"))

        flags = {
            name: bool(pattern.search(text))
            for name, pattern in STATUS_PATTERNS.items()
        }

        reasons = []
        if year is None:
            reasons.append("year not inferred")
        if anchor["repair"]:
            reasons.append("13-digit APN repaired by prepending zero")
        if not legal:
            reasons.append("legal description missing")
        if not owner_text:
            reasons.append("owner/taxpayer missing")
        if len(text) > 15000:
            reasons.append("unusually long record; possible missed anchor")

        records.append(
            OCRRecord(
                auction_year=year,
                property_number=anchor["property_number"],
                parcel_number=anchor["parcel_number"],
                parcel_number_raw=anchor["parcel_number_raw"],
                parcel_repair_applied_flag=anchor["repair"],
                taxpayer_name=owner_text,
                owner_record_text=owner_text,
                legal_description=legal,
                situs_address=situs,
                tca_code=tca_code,
                use_code=use_code,
                use_description=use_description,
                acreage=acreage,
                land_value=money(first_line(text, r"LAND VALUE")),
                improvement_value=money(first_line(text, r"IMPROVEMENT VALUE")),
                tax_years=field_between(text, r"TAX YEARS"),
                amount_due=money(first_line(text, r"AMOUNT DUE.*?")),
                amount_paid=money(first_line(text, r"AMOUNT PAID.*?")),
                paid_in_full_flag=flags["paid_in_full_flag"],
                administratively_pulled_flag=flags["administratively_pulled_flag"],
                redeemed_flag=flags["redeemed_flag"],
                must_be_sold_with_flag=flags["must_be_sold_with_flag"],
                sale_does_not_include_flag=flags["sale_does_not_include_flag"],
                subject_to_flag=flags["subject_to_flag"],
                special_condition_text=special_text(text),
                source_filename=pdf_path.name,
                source_start_page=start_page,
                source_end_page=end_page,
                record_spans_pages_flag=start_page != end_page,
                extraction_method="tesseract_cached_ownerlabel_v5",
                anchor_quality=anchor["anchor_quality"],
                duplicate_key_flag=False,
                review_required_flag=bool(reasons),
                review_reason="; ".join(reasons),
                raw_ocr_text=clean(text) or "",
            )
        )
    return records


def main():
    tesseract = find_tesseract()
    if not tesseract:
        print("Tesseract OCR was not found.")
        sys.exit(2)
    pytesseract.pytesseract.tesseract_cmd = tesseract

    pdf_paths = sorted(SOURCE_DIR.glob("*.pdf"))
    all_records = []
    file_stats = []

    for pdf_path in pdf_paths:
        try:
            records = parse_pdf(pdf_path)
            all_records.extend(asdict(r) for r in records)
            file_stats.append(
                {
                    "source_filename": pdf_path.name,
                    "auction_year": records[0].auction_year if records else None,
                    "record_count": len(records),
                    "review_record_count": sum(r.review_required_flag for r in records),
                    "repaired_apn_count": sum(r.parcel_repair_applied_flag for r in records),
                    "parse_error": "",
                }
            )
        except Exception as exc:
            file_stats.append(
                {
                    "source_filename": pdf_path.name,
                    "auction_year": None,
                    "record_count": 0,
                    "review_record_count": 0,
                    "repaired_apn_count": 0,
                    "parse_error": str(exc),
                }
            )

    records_df = pd.DataFrame(all_records)
    files_df = pd.DataFrame(file_stats)

    if not records_df.empty:
        duplicate_cols = [
            "auction_year",
            "source_filename",
            "property_number",
            "parcel_number",
        ]
        records_df["duplicate_key_flag"] = records_df.duplicated(
            duplicate_cols, keep=False
        )
        mask = records_df["duplicate_key_flag"]
        records_df.loc[mask, "review_required_flag"] = True
        records_df.loc[mask, "review_reason"] = records_df.loc[
            mask, "review_reason"
        ].apply(
            lambda value: "; ".join(x for x in [value, "duplicate source key"] if x)
        )
        records_df = records_df.sort_values(
            ["auction_year", "property_number", "parcel_number"],
            na_position="last",
        ).reset_index(drop=True)

    review_df = records_df[records_df["review_required_flag"]].copy()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records_df.to_csv(OUTPUT_DIR / "ocr_final_order_records.csv", index=False)
    review_df.to_csv(OUTPUT_DIR / "ocr_final_order_review_queue.csv", index=False)
    files_df.to_csv(OUTPUT_DIR / "ocr_final_order_file_summary.csv", index=False)

    excel_records = records_df.copy()
    excel_review = review_df.copy()
    for frame in (excel_records, excel_review):
        if "raw_ocr_text" in frame.columns:
            frame["raw_ocr_text"] = frame["raw_ocr_text"].str.slice(0, 32000)

    with pd.ExcelWriter(
        OUTPUT_DIR / "ocr_final_order_records.xlsx", engine="openpyxl"
    ) as writer:
        excel_records.to_excel(writer, sheet_name="OCR Records", index=False)
        excel_review.to_excel(writer, sheet_name="Review Queue", index=False)
        files_df.to_excel(writer, sheet_name="File Summary", index=False)
        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for cells in ws.columns:
                width = min(
                    max(
                        max(len(str(c.value)) if c.value is not None else 0 for c in cells) + 2,
                        11,
                    ),
                    50,
                )
                ws.column_dimensions[cells[0].column_letter].width = width

    print(f"Final Order PDFs processed: {len(pdf_paths):,}")
    print(f"OCR records extracted: {len(records_df):,}")
    print(f"Review-queue records: {len(review_df):,}")
    print("Repaired 13-digit APNs:", int(records_df["parcel_repair_applied_flag"].sum()))
    print("Duplicate source keys:", int(records_df["duplicate_key_flag"].sum()))
    print("Parser version: owner-label fix v5")


if __name__ == "__main__":
    main()
