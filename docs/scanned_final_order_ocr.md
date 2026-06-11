# Scanned Final Order OCR

## Python packages

From the repository root:

```powershell
pip install pymupdf pytesseract pillow
```

You may also add these lines to `requirements.txt`:

```text
pymupdf
pytesseract
pillow
```

## Tesseract application

The Python package does not include the OCR engine itself.

Check whether it is already installed:

```powershell
tesseract --version
```

If PowerShell cannot find it:

```powershell
winget search tesseract
```

Install the standard Windows Tesseract OCR package shown by `winget`, then
close and reopen VS Code.

## Run

```powershell
python -m src.extract.ocr_scanned_final_orders
```

The first run may take several minutes because it OCRs approximately 136 pages.
Later runs reuse cached page text from:

```text
data/private/ocr_cache/final_orders
```

That folder is already excluded from Git through `data/private/`.
