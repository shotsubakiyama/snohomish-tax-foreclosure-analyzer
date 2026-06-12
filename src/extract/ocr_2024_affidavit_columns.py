"""Column-aware OCR for the 2024 Snohomish County affidavit.

Run from the repository root:
    python src/extract/ocr_2024_affidavit_columns.py
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

import fitz
import pytesseract
from PIL import Image, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = PROJECT_ROOT / "data" / "raw" / "affidavits" / "2024 Affidavit of Publication for webpage.pdf"
OUTPUT_DIR = PROJECT_ROOT / "data" / "private" / "ocr_cache" / "affidavits_2024_columns"

DENSE_PAGES = {5, 6, 7, 9, 10, 11, 13, 14, 15, 17, 18, 19, 21, 22, 23}
DPI = 400

CONTENT_TOP = 0.018
CONTENT_BOTTOM = 0.970
LEFT_COLUMN_LEFT = 0.032
LEFT_COLUMN_RIGHT = 0.272
RIGHT_COLUMN_LEFT = 0.258
RIGHT_COLUMN_RIGHT = 0.505


def find_tesseract() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found

    for candidate in (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ):
        if candidate.exists():
            return str(candidate)

    return None


def render_page(page: fitz.Page) -> Image.Image:
    zoom = DPI / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def relative_crop(image: Image.Image, left: float, top: float, right: float, bottom: float) -> Image.Image:
    width, height = image.size
    box = (
        max(0, round(width * left)),
        max(0, round(height * top)),
        min(width, round(width * right)),
        min(height, round(height * bottom)),
    )
    return image.crop(box)


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    return gray.point(lambda pixel: 255 if pixel > 188 else 0)


def ocr_column(image: Image.Image) -> str:
    return pytesseract.image_to_string(
        image,
        lang="eng",
        config="--oem 3 --psm 6 -c preserve_interword_spaces=1",
    ).strip()


def write_debug_image(image: Image.Image, page_number: int, column_name: str) -> None:
    debug_dir = OUTPUT_DIR / "debug_images"
    debug_dir.mkdir(parents=True, exist_ok=True)
    image.save(debug_dir / f"page_{page_number:03d}_{column_name}.png")


def process_dense_page(page: fitz.Page, page_number: int) -> tuple[str, int, int]:
    rendered = render_page(page)

    left_column = preprocess_for_ocr(
        relative_crop(
            rendered,
            LEFT_COLUMN_LEFT,
            CONTENT_TOP,
            LEFT_COLUMN_RIGHT,
            CONTENT_BOTTOM,
        )
    )
    right_column = preprocess_for_ocr(
        relative_crop(
            rendered,
            RIGHT_COLUMN_LEFT,
            CONTENT_TOP,
            RIGHT_COLUMN_RIGHT,
            CONTENT_BOTTOM,
        )
    )

    write_debug_image(left_column, page_number, "left")
    write_debug_image(right_column, page_number, "right")

    left_text = ocr_column(left_column)
    right_text = ocr_column(right_column)

    combined = (
        f"[[PAGE_{page_number:03d}_LEFT_COLUMN]]\n"
        f"{left_text}\n\n"
        f"[[PAGE_{page_number:03d}_RIGHT_COLUMN]]\n"
        f"{right_text}\n"
    )
    return combined, len(left_text), len(right_text)


def main() -> None:
    tesseract = find_tesseract()
    if not tesseract:
        print("Tesseract OCR was not found.")
        sys.exit(2)

    pytesseract.pytesseract.tesseract_cmd = tesseract

    if not PDF_PATH.exists():
        print(f"PDF not found: {PDF_PATH}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    document = fitz.open(PDF_PATH)
    summary_rows: list[str] = []

    try:
        for page_number in sorted(DENSE_PAGES):
            if not 1 <= page_number <= len(document):
                continue

            print(f"OCR 2024 column layout: page {page_number}/{len(document)}")
            text, left_length, right_length = process_dense_page(
                document[page_number - 1],
                page_number,
            )

            (OUTPUT_DIR / f"page_{page_number:03d}.txt").write_text(
                text,
                encoding="utf-8",
            )

            summary_rows.append(
                f"{page_number}\t{left_length}\t{right_length}\t{left_length + right_length}"
            )
    finally:
        document.close()

    summary_path = OUTPUT_DIR / "page_summary.tsv"
    summary_path.write_text(
        "page\tleft_chars\tright_chars\ttotal_chars\n"
        + "\n".join(summary_rows)
        + "\n",
        encoding="utf-8",
    )

    print()
    print(f"Dense pages processed: {len(summary_rows)}")
    print(f"Column OCR cache: {OUTPUT_DIR}")
    print(f"Summary: {summary_path}")
    print(f"Debug crops: {OUTPUT_DIR / 'debug_images'}")


if __name__ == "__main__":
    main()
