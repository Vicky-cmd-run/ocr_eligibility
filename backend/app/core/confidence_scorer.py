"""
Confidence Scorer — combines OCR, subject match, marks column,
and structural validation scores into a routing decision.
"""
from dataclasses import dataclass
from typing import List, Optional

from app.core.marks_extractor import ExtractedDocument, ExtractedSubjectMark
from app.core.validator import ValidationResult
from app.config import settings


@dataclass
class ConfidenceScore:
    ocr_confidence: float           # Average token OCR confidence
    subject_match_confidence: float # Average subject normalization confidence
    marks_column_confidence: float  # Average marks detection confidence
    structural_confidence: float    # Based on validation errors/warnings
    combined_confidence: float      # Weighted combination

    routing: str  # "auto" | "validate" | "review"
    routing_reason: str


def _average(values: List[Optional[float]]) -> float:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


def score_document(
    doc: ExtractedDocument,
    validation: ValidationResult,
) -> ConfidenceScore:
    """
    Compute combined confidence score and determine routing.

    Routing rules:
      combined >= AUTO_THRESHOLD  → "auto"   (fully automated)
      combined >= REVIEW_THRESHOLD → "validate" (auto with careful check)
      combined <  REVIEW_THRESHOLD → "review" (human review required)
    """
    auto_threshold = settings.ocr_confidence_auto_threshold
    review_threshold = settings.ocr_confidence_review_threshold

    # 1. OCR confidence: average of all token confidences
    ocr_conf = doc.overall_ocr_confidence

    # 2. Subject match confidence: average across PCM subjects
    subject_confs = [m.subject_match_confidence for m in doc.subject_marks]
    subject_conf = _average(subject_confs)

    # 3. Marks column confidence: average of marks OCR confidence
    marks_confs = [m.marks_ocr_confidence for m in doc.subject_marks if m.marks_ocr_confidence > 0]
    marks_conf = _average(marks_confs)

    # 4. Structural confidence: penalize for validation errors/warnings
    error_penalty = len(validation.errors) * 0.10
    warning_penalty = len(validation.warnings) * 0.03
    structural_conf = max(0.0, 1.0 - error_penalty - warning_penalty)

    # 5. Weighted combined confidence
    # Weights: OCR=30%, Subject=25%, Marks=25%, Structural=20%
    combined = (
        ocr_conf * 0.30
        + subject_conf * 0.25
        + marks_conf * 0.25
        + structural_conf * 0.20
    )
    combined = max(0.0, min(1.0, combined))

    # 6. Routing decision
    if combined >= auto_threshold and not validation.errors and not doc.needs_review:
        routing = "auto"
        routing_reason = f"High confidence ({combined:.2f}) — auto-processed"
    elif combined >= review_threshold:
        routing = "validate"
        routing_reason = f"Moderate confidence ({combined:.2f}) — validated carefully"
    else:
        routing = "review"
        routing_reason = (
            f"Low confidence ({combined:.2f}) — requires human review. "
            + (f"Errors: {len(validation.errors)}, Warnings: {len(validation.warnings)}" if validation.errors or validation.warnings else "")
        )

    # Force review if validation has hard errors
    if validation.errors:
        routing = "review"
        routing_reason = f"Validation errors present — human review required"

    return ConfidenceScore(
        ocr_confidence=ocr_conf,
        subject_match_confidence=subject_conf,
        marks_column_confidence=marks_conf,
        structural_confidence=structural_conf,
        combined_confidence=combined,
        routing=routing,
        routing_reason=routing_reason,
    )
