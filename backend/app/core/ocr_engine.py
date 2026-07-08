"""
OCR Engine — wraps PaddleOCR with structured output.
Produces tokens with text, bounding box, and confidence score per page.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OcrToken:
    """A single OCR-detected text token."""
    text: str
    confidence: float
    page_number: int
    # Polygon bounding box [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    bounding_box: List[List[float]] = field(default_factory=list)
    # Simplified AABB
    x_min: float = 0.0
    y_min: float = 0.0
    x_max: float = 0.0
    y_max: float = 0.0


def _bbox_to_aabb(bbox: List[List[float]]) -> tuple:
    """Convert polygon bbox to axis-aligned bounding box (x_min, y_min, x_max, y_max)."""
    if not bbox:
        return 0.0, 0.0, 0.0, 0.0
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return min(xs), min(ys), max(xs), max(ys)


class OCREngine:
    """
    Singleton wrapper around PaddleOCR.
    Lazy-initializes the model on first use to avoid loading at import time.
    """

    _instance: Optional["OCREngine"] = None
    _ocr = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_ocr(self):
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
                device = "gpu" if settings.paddleocr_use_gpu else "cpu"
                self._ocr = PaddleOCR(
                    use_textline_orientation=True,
                    lang=settings.paddleocr_lang,
                    device=device,
                    enable_mkldnn=False,
                )
                logger.info("PaddleOCR initialized successfully")
            except ImportError:
                logger.error("PaddleOCR not installed. Install paddlepaddle and paddleocr.")
                raise
        return self._ocr

    def run_on_image(self, image: np.ndarray, page_number: int = 1) -> List[OcrToken]:
        """
        Run OCR on a numpy BGR image.
        Returns list of OcrToken sorted by top-to-bottom, left-to-right position.
        """
        ocr = self._get_ocr()
        try:
            result = ocr.ocr(image, cls=True)
        except Exception as e:
            logger.error(f"PaddleOCR failed on page {page_number}: {e}")
            return []

        tokens: List[OcrToken] = []

        if not result:
            return tokens

        for line_result in result:
            if not line_result:
                continue
            for item in line_result:
                if not item or len(item) < 2:
                    continue
                bbox_raw, (text, conf) = item
                if not text or not text.strip():
                    continue

                # Normalize bounding box to list of [x,y] pairs
                bbox = [[float(p[0]), float(p[1])] for p in bbox_raw]
                x_min, y_min, x_max, y_max = _bbox_to_aabb(bbox)

                tokens.append(OcrToken(
                    text=text.strip(),
                    confidence=float(conf),
                    page_number=page_number,
                    bounding_box=bbox,
                    x_min=x_min,
                    y_min=y_min,
                    x_max=x_max,
                    y_max=y_max,
                ))

        # Sort top-to-bottom (y), then left-to-right (x)
        tokens.sort(key=lambda t: (t.y_min, t.x_min))
        return tokens

    def run_on_text(self, text: str, page_number: int = 1) -> List[OcrToken]:
        """
        Convert native text (already extracted from PDF) into pseudo-tokens.
        Each line becomes a token with confidence=1.0 and no spatial info.
        """
        tokens = []
        y = 0.0
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                y += 20
                continue
            tokens.append(OcrToken(
                text=line,
                confidence=1.0,
                page_number=page_number,
                bounding_box=[],
                x_min=0.0,
                y_min=y,
                x_max=1000.0,
                y_max=y + 20,
            ))
            y += 22
        return tokens


def get_ocr_engine() -> OCREngine:
    return OCREngine()
