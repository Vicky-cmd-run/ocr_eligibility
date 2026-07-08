"""
Mark Validation Engine — validates extracted marks for correctness.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.marks_extractor import ExtractedSubjectMark, ExtractedDocument

logger = logging.getLogger(__name__)


@dataclass
class ValidationWarning:
    field: str
    message: str
    severity: str  # "error" | "warning" | "info"


@dataclass
class ValidationResult:
    is_valid: bool
    warnings: List[ValidationWarning] = field(default_factory=list)
    errors: List[ValidationWarning] = field(default_factory=list)
    needs_review: bool = False

    def add_warning(self, field: str, message: str):
        self.warnings.append(ValidationWarning(field=field, message=message, severity="warning"))
        self.needs_review = True

    def add_error(self, field: str, message: str):
        self.errors.append(ValidationWarning(field=field, message=message, severity="error"))
        self.is_valid = False
        self.needs_review = True


def validate_mark(mark: ExtractedSubjectMark) -> ValidationResult:
    """
    Validate a single subject mark entry.
    Checks numeric values, obtained <= maximum, range 0–100%, etc.
    """
    result = ValidationResult(is_valid=True)

    subject = mark.normalized_subject
    raw_obtained = mark.raw_obtained_text or ""
    raw_maximum = mark.raw_maximum_text or ""

    # 1. Check obtained marks are numeric
    if mark.obtained_marks is None:
        if raw_obtained:
            result.add_error(
                f"{subject}.obtained",
                f"Could not parse obtained marks from '{raw_obtained}'"
            )
        else:
            result.add_warning(f"{subject}.obtained", "Obtained marks are missing")

    # 2. Check maximum marks are numeric
    if mark.maximum_marks is None:
        if raw_maximum:
            result.add_error(
                f"{subject}.maximum",
                f"Could not parse maximum marks from '{raw_maximum}'"
            )
        else:
            result.add_warning(f"{subject}.maximum", "Maximum marks are missing")

    # 3. obtained <= maximum
    if mark.obtained_marks is not None and mark.maximum_marks is not None:
        if mark.obtained_marks > mark.maximum_marks:
            result.add_error(
                f"{subject}.obtained",
                f"Obtained marks ({mark.obtained_marks}) exceed maximum marks ({mark.maximum_marks})"
            )

    # 4. Negative marks check
    if mark.obtained_marks is not None and mark.obtained_marks < 0:
        result.add_error(f"{subject}.obtained", f"Negative obtained marks: {mark.obtained_marks}")

    if mark.maximum_marks is not None and mark.maximum_marks <= 0:
        result.add_error(f"{subject}.maximum", f"Invalid maximum marks: {mark.maximum_marks}")

    # 5. Percentage range check
    if mark.percentage is not None:
        if not (0.0 <= mark.percentage <= 100.0):
            result.add_error(
                f"{subject}.percentage",
                f"Percentage out of range: {mark.percentage:.2f}%"
            )

    # 6. Suspicious OCR values
    if mark.is_suspicious:
        result.add_warning(
            f"{subject}.ocr",
            f"Suspicious OCR characters detected — possible substitution errors"
        )

    # 7. Maximum marks sanity check (too low or too high)
    if mark.maximum_marks is not None:
        if mark.maximum_marks < 10:
            result.add_warning(
                f"{subject}.maximum",
                f"Unusually low maximum marks: {mark.maximum_marks}"
            )
        if mark.maximum_marks > 500:
            result.add_warning(
                f"{subject}.maximum",
                f"Unusually high maximum marks: {mark.maximum_marks}"
            )

    # 8. Low OCR confidence
    if mark.marks_ocr_confidence < 0.75:
        result.add_warning(
            f"{subject}.confidence",
            f"Low OCR confidence ({mark.marks_ocr_confidence:.2f}) for marks"
        )

    return result


def validate_document(doc: ExtractedDocument) -> ValidationResult:
    """
    Validate all subject marks in an extracted document.
    Also checks for required subjects and cross-field consistency.
    """
    result = ValidationResult(is_valid=True)

    # Validate each subject mark
    for mark in doc.subject_marks:
        mark_result = validate_mark(mark)
        result.warnings.extend(mark_result.warnings)
        result.errors.extend(mark_result.errors)
        if not mark_result.is_valid:
            result.is_valid = False
        if mark_result.needs_review:
            result.needs_review = True

    # Check for duplicate subjects
    subjects_seen = {}
    for mark in doc.subject_marks:
        subj = mark.normalized_subject
        if subj in subjects_seen:
            result.add_warning(
                "subjects",
                f"Duplicate subject detected: {subj} (rows: '{subjects_seen[subj]}' and '{mark.raw_subject_name}')"
            )
        else:
            subjects_seen[subj] = mark.raw_subject_name

    # Overall OCR confidence
    if doc.overall_ocr_confidence < 0.75:
        result.add_warning(
            "document.ocr_confidence",
            f"Overall OCR confidence is low: {doc.overall_ocr_confidence:.2f}"
        )

    # Missing candidate name
    if not doc.candidate_name:
        result.add_warning("candidate.name", "Candidate name could not be extracted")

    # Missing register number
    if not doc.register_number:
        result.add_warning("candidate.register", "Register/roll number could not be extracted")

    if result.errors or result.warnings:
        result.needs_review = True

    return result
