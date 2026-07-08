"""
PDF Processing module — detects native text vs. scanned PDFs,
extracts text or renders pages to images.
"""
import io
import logging
from pathlib import Path
from typing import List, Tuple, Optional

import fitz  # PyMuPDF
import pdfplumber
import numpy as np
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

NATIVE_TEXT_MIN_CHARS = 50  # minimum chars to consider a page as native-text


class PDFPage:
    """Container for a single PDF page result."""

    def __init__(
        self,
        page_number: int,
        text: Optional[str],
        image: Optional[np.ndarray],
        is_native_text: bool,
    ):
        self.page_number = page_number
        self.text = text
        self.image = image  # numpy array (BGR), or None
        self.is_native_text = is_native_text


def is_native_text_page(page: fitz.Page) -> bool:
    """
    Determine if a PDF page has a usable native text layer.
    Returns True when the extracted text has enough meaningful content.
    """
    text = page.get_text("text").strip()
    # Filter out just whitespace/newlines
    meaningful = " ".join(text.split())
    return len(meaningful) >= NATIVE_TEXT_MIN_CHARS


def render_page_to_image(page: fitz.Page, dpi: int = None) -> np.ndarray:
    """Render a PDF page to a high-resolution numpy array (BGR)."""
    if dpi is None:
        dpi = settings.pdf_dpi
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    # Convert RGB to BGR for OpenCV
    import cv2
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def extract_native_text(pdf_path: str) -> List[Tuple[int, str]]:
    """
    Extract text from each page using pdfplumber (more accurate for tables).
    Returns list of (page_number, text).
    """
    pages_text = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages_text.append((i + 1, text))
    except Exception as e:
        logger.warning(f"pdfplumber failed on {pdf_path}: {e}, falling back to PyMuPDF")
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                text = page.get_text("text") or ""
                pages_text.append((i + 1, text))
    return pages_text


def process_pdf(pdf_path: str) -> Tuple[List[PDFPage], bool]:
    """
    Process a PDF file.

    Returns:
        (pages, is_fully_native) where pages is a list of PDFPage objects.
        is_fully_native = True if all pages use native text.
    """
    pages: List[PDFPage] = []
    doc = fitz.open(pdf_path)
    all_native = True

    for i, page in enumerate(doc):
        if is_native_text_page(page):
            # Extract native text using pdfplumber for this page
            try:
                with pdfplumber.open(pdf_path) as plumber_doc:
                    if i < len(plumber_doc.pages):
                        text = plumber_doc.pages[i].extract_text() or ""
                    else:
                        text = page.get_text("text")
            except Exception:
                text = page.get_text("text")

            pages.append(PDFPage(
                page_number=i + 1,
                text=text,
                image=None,
                is_native_text=True,
            ))
        else:
            all_native = False
            img = render_page_to_image(page)
            pages.append(PDFPage(
                page_number=i + 1,
                text=None,
                image=img,
                is_native_text=False,
            ))

    doc.close()
    return pages, all_native


def detect_marks_page(pages: List[PDFPage]) -> List[PDFPage]:
    """
    Heuristically identify the most relevant pages (those likely containing marks).
    Returns filtered list; if uncertain, returns all pages.
    """
    MARKS_KEYWORDS = [
        "marks", "mark", "subject", "physics", "chemistry", "mathematics",
        "obtained", "maximum", "total", "score", "theory", "practical",
        "physics", "chem", "math", "pcm",
    ]

    scored = []
    for page in pages:
        text = (page.text or "").lower()
        score = sum(1 for kw in MARKS_KEYWORDS if kw in text)
        scored.append((score, page))

    if not scored:
        return pages

    max_score = max(s for s, _ in scored)
    if max_score == 0:
        return pages  # No marks keywords found, return all

    # Return pages with the highest keyword density
    relevant = [p for s, p in scored if s >= max(1, max_score - 1)]
    return relevant if relevant else pages
