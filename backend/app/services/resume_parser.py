import logging
from pathlib import Path
import pymupdf

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str | Path) -> str:
    """Extract text from a PDF file using PyMuPDF.

    Handles multi-page documents, detects blank or corrupted documents,
    and ensures proper resource cleanup.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found at: {file_path}")

    # Read into memory so MuPDF does not keep a Windows file lock if open() fails.
    pdf_bytes = path.read_bytes()

    doc = None
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        extracted_pages: list[str] = []

        for page_index in range(len(doc)):
            page = doc[page_index]
            text = page.get_text()
            if text:
                extracted_pages.append(text.strip())

        full_text = "\n\n".join(extracted_pages).strip()
        return full_text
    except Exception as exc:
        logger.error("Error parsing PDF document: %s", exc, exc_info=True)
        raise ValueError("Failed to parse PDF document. The file may be corrupted or unreadable.") from exc
    finally:
        if doc is not None:
            doc.close()

