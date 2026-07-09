"""
Full processing pipeline orchestrator.
Runs a single document through the complete OCR → extract → validate → eligibility pipeline.
"""
import logging
from pathlib import Path
from typing import List

from app.core.ocr_engine import OcrToken, get_ocr_engine
from app.core.pdf_processor import process_pdf, detect_marks_page
from app.core.image_preprocessor import ImagePreprocessor, load_image
from app.core.marks_extractor import extract_from_tokens, ExtractedDocument
from app.core.validator import validate_document
from app.core.cutoff_calculator import calculate_cutoff
from app.core.eligibility_engine import determine_eligibility
from app.core.confidence_scorer import score_document
from app.config import settings

logger = logging.getLogger(__name__)

preprocessor = ImagePreprocessor()


def run_pipeline(
    file_path: str,
    mime_type: str,
    cutoff_formula: str = "pcm_average",
    math_mode: str = "combined",
    eligibility_threshold: float = 50.0,
) -> dict:
    """
    Run the full OCR pipeline on a single document.

    Returns a dict with all pipeline results for persisting to the database.
    """
    logger.info(f"Starting pipeline for: {file_path}")
    result = {
        "document_type": "UNKNOWN",
        "page_count": 0,
        "ocr_tokens": [],
        "extracted": None,
        "validation": None,
        "cutoff": None,
        "eligibility": None,
        "confidence": None,
        "error": None,
    }

    try:
        all_tokens: List[OcrToken] = []

        if mime_type == "application/pdf":
            pages, is_native = process_pdf(file_path)
            result["page_count"] = len(pages)
            result["document_type"] = "PDF_NATIVE" if is_native else "PDF_SCANNED"

            # Filter to marks-relevant pages
            relevant_pages = detect_marks_page(pages)
            logger.info(f"Processing {len(relevant_pages)}/{len(pages)} relevant pages")

            ocr = get_ocr_engine()
            for page in relevant_pages:
                if page.is_native_text and page.text:
                    page_tokens = ocr.run_on_text(page.text, page_number=page.page_number)
                else:
                    processed = preprocessor.preprocess(page.image)
                    page_tokens = ocr.run_on_image(processed, page_number=page.page_number, original_size=page.image.shape[:2])
                all_tokens.extend(page_tokens)

        else:
            # Image file
            result["document_type"] = "IMAGE"
            result["page_count"] = 1
            img = load_image(file_path)
            processed = preprocessor.preprocess(img)
            ocr = get_ocr_engine()
            all_tokens = ocr.run_on_image(processed, page_number=1, original_size=img.shape[:2])

        result["ocr_tokens"] = all_tokens

        # Extract marks and candidate info
        extracted: ExtractedDocument = extract_from_tokens(all_tokens)
        result["extracted"] = extracted

        # Check if the document is actually a marksheet
        if not extracted.subject_marks:
            raise ValueError("Document does not appear to be a valid marksheet (no subjects or marks table detected)")

        # Validate
        validation = validate_document(extracted)
        result["validation"] = validation

        # Cutoff calculation
        cutoff = calculate_cutoff(
            extracted.subject_marks,
            cutoff_formula=cutoff_formula,
            math_mode=math_mode,
        )
        result["cutoff"] = cutoff

        # Eligibility
        eligibility = determine_eligibility(cutoff, threshold=eligibility_threshold)
        result["eligibility"] = eligibility

        # Confidence + routing
        confidence = score_document(extracted, validation)
        result["confidence"] = confidence

        logger.info(
            f"Pipeline complete: status={eligibility.status}, "
            f"confidence={confidence.combined_confidence:.2f}, "
            f"routing={confidence.routing}"
        )

    except Exception as e:
        logger.exception(f"Pipeline failed for {file_path}: {e}")
        result["error"] = str(e)

    return result
