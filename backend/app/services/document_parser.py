"""
services/document_parser.py

WHAT THIS FILE DOES:
Extracts plain text from an uploaded file, regardless of format, so it
can be chunked and embedded by rag_service.py. This is step 1 of the
knowledge base pipeline: Upload -> Parse (this file) -> Chunk -> Embed ->
Store in Qdrant.

Supported: PDF, DOCX, CSV, XLSX, TXT/MD. Images (menus/price lists as
photos) need OCR — see `extract_text_from_image` which uses pytesseract;
install the `pytesseract` package + system `tesseract-ocr` binary if you
enable that path.
"""

import io
import csv


def extract_text(file_bytes: bytes, file_type: str) -> str:
    """
    Routes to the right extractor based on file_type
    ("pdf" | "docx" | "csv" | "xlsx" | "txt" | "md" | "image").
    Returns plain text, or raises ValueError for unsupported types.
    """
    file_type = file_type.lower().lstrip(".")

    if file_type == "pdf":
        return _extract_pdf(file_bytes)
    if file_type == "docx":
        return _extract_docx(file_bytes)
    if file_type == "csv":
        return _extract_csv(file_bytes)
    if file_type == "xlsx":
        return _extract_xlsx(file_bytes)
    if file_type in ("txt", "md"):
        return file_bytes.decode("utf-8", errors="ignore")
    if file_type == "image":
        return _extract_image_ocr(file_bytes)

    raise ValueError(f"Unsupported file type for knowledge base ingestion: '{file_type}'")


def _extract_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(file_bytes: bytes) -> str:
    import docx
    document = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in document.paragraphs)


def _extract_csv(file_bytes: bytes) -> str:
    text_stream = io.StringIO(file_bytes.decode("utf-8", errors="ignore"))
    reader = csv.reader(text_stream)
    rows = [", ".join(row) for row in reader]
    return "\n".join(rows)


def _extract_xlsx(file_bytes: bytes) -> str:
    from openpyxl import load_workbook
    workbook = load_workbook(io.BytesIO(file_bytes), data_only=True)
    lines = []
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(values_only=True):
            line = ", ".join(str(cell) for cell in row if cell is not None)
            if line:
                lines.append(line)
    return "\n".join(lines)


def _extract_image_ocr(file_bytes: bytes) -> str:
    import pytesseract
    from PIL import Image
    image = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(image)
