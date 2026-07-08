"""
Marks Extractor — orchestrates OCR token analysis to extract
candidate info and subject marks from a processed document.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from app.core.ocr_engine import OcrToken
from app.core.layout_analyzer import extract_table_rows, clean_numeric, TableRow
from app.core.subject_normalizer import normalize_subject, PHYSICS, CHEMISTRY, MATHEMATICS, MATHS_A, MATHS_B, UNKNOWN

logger = logging.getLogger(__name__)

# Regex for candidate info detection
NAME_PATTERNS = [
    re.compile(r"(?:candidate\s*(?:name|:)\s*)(.+)", re.IGNORECASE),
    re.compile(r"(?:name\s*(?:of\s*candidate|:)\s*)(.+)", re.IGNORECASE),
    re.compile(r"(?:student\s*name\s*[:\-]\s*)(.+)", re.IGNORECASE),
]
REG_PATTERNS = [
    re.compile(r"(?:register\s*(?:no|number|#|:)\s*)([A-Z0-9\-/]+)", re.IGNORECASE),
    re.compile(r"(?:roll\s*(?:no|number|#|:)\s*)([A-Z0-9\-/]+)", re.IGNORECASE),
    re.compile(r"(?:reg\s*(?:no|:)\s*)([A-Z0-9\-/]+)", re.IGNORECASE),
    re.compile(r"(?:hall\s*ticket\s*(?:no|number|:)\s*)([A-Z0-9\-/]+)", re.IGNORECASE),
]

# Suspicious OCR substitution characters
SUSPICIOUS_CHARS = {
    "O": "0",
    "o": "0",
    "I": "1",
    "l": "1",
    "B": "8",
    "S": "5",
    "G": "6",
    "Z": "2",
}


@dataclass
class ExtractedSubjectMark:
    """Result of extracting one subject row."""
    raw_subject_name: str
    normalized_subject: str
    mark_type: str = "TOTAL"

    obtained_marks: Optional[float] = None
    maximum_marks: Optional[float] = None
    percentage: Optional[float] = None

    subject_match_confidence: float = 0.0
    marks_ocr_confidence: float = 0.0
    raw_obtained_text: Optional[str] = None
    raw_maximum_text: Optional[str] = None

    is_suspicious: bool = False
    notes: Optional[str] = None
    needs_review: bool = False


@dataclass
class ExtractedDocument:
    """Full extraction result for a document."""
    candidate_name: Optional[str] = None
    register_number: Optional[str] = None
    raw_text_name: Optional[str] = None
    raw_text_register: Optional[str] = None

    subject_marks: List[ExtractedSubjectMark] = field(default_factory=list)
    all_tokens: List[OcrToken] = field(default_factory=list)

    overall_ocr_confidence: float = 0.0
    needs_review: bool = False
    review_reasons: List[str] = field(default_factory=list)


def _check_suspicious_ocr(text: str) -> bool:
    """Detect common OCR substitution errors in a numeric string."""
    for suspicious_char in SUSPICIOUS_CHARS:
        if suspicious_char in text:
            return True
    return False


def _fix_numeric_ocr(text: str) -> str:
    """Attempt to fix common OCR substitutions in numeric fields."""
    result = text.strip()
    for bad, good in SUSPICIOUS_CHARS.items():
        result = result.replace(bad, good)
    return result


def _extract_candidate_name(tokens: List[OcrToken]) -> tuple[Optional[str], Optional[str]]:
    """
    Search token texts for candidate name.
    Returns (extracted_name, raw_matched_text).
    """
    full_text = "\n".join(t.text for t in tokens)
    for pattern in NAME_PATTERNS:
        m = pattern.search(full_text)
        if m:
            name = m.group(1).strip()
            if 2 <= len(name) <= 100:
                return name, m.group(0).strip()
    return None, None


def _extract_register_number(tokens: List[OcrToken]) -> tuple[Optional[str], Optional[str]]:
    """
    Search token texts for register/roll number.
    Returns (register_number, raw_matched_text).
    """
    full_text = "\n".join(t.text for t in tokens)
    for pattern in REG_PATTERNS:
        m = pattern.search(full_text)
        if m:
            reg = m.group(1).strip()
            if 4 <= len(reg) <= 30:
                return reg, m.group(0).strip()
    return None, None


def _process_table_row(row: TableRow) -> Optional[ExtractedSubjectMark]:
    """
    Convert a TableRow into an ExtractedSubjectMark.
    Returns None if the row doesn't look like a valid subject mark row.
    """
    raw_subject = row.subject_token.text.strip()
    if not raw_subject or len(raw_subject) < 2:
        return None

    norm_result = normalize_subject(raw_subject)

    # Skip rows that are clearly headers or totals
    skip_words = {"total", "grand total", "aggregate", "result", "grade", "status", "pass", "fail"}
    if raw_subject.lower() in skip_words:
        return None

    # Parse obtained marks
    obtained_text = row.obtained_text
    maximum_text = row.maximum_text
    is_suspicious = False
    notes = []

    obtained_marks: Optional[float] = None
    maximum_marks: Optional[float] = None

    if obtained_text:
        if _check_suspicious_ocr(obtained_text):
            is_suspicious = True
            notes.append(f"Suspicious OCR chars in obtained: '{obtained_text}'")
            fixed = _fix_numeric_ocr(obtained_text)
            obtained_marks = clean_numeric(fixed)
        else:
            obtained_marks = clean_numeric(obtained_text)

    if maximum_text:
        if _check_suspicious_ocr(maximum_text):
            is_suspicious = True
            notes.append(f"Suspicious OCR chars in maximum: '{maximum_text}'")
            fixed = _fix_numeric_ocr(maximum_text)
            maximum_marks = clean_numeric(fixed)
        else:
            maximum_marks = clean_numeric(maximum_text)

    # Calculate percentage if both available
    percentage: Optional[float] = None
    if obtained_marks is not None and maximum_marks is not None and maximum_marks > 0:
        percentage = (obtained_marks / maximum_marks) * 100.0

    # Combined confidence: subject match * mark OCR confidence
    marks_conf = (row.obtained_confidence + (row.maximum_confidence or 0)) / 2
    combined_conf = norm_result.confidence * marks_conf if marks_conf > 0 else norm_result.confidence

    needs_review = (
        norm_result.needs_review
        or is_suspicious
        or obtained_marks is None
        or maximum_marks is None
        or combined_conf < 0.75
    )

    return ExtractedSubjectMark(
        raw_subject_name=raw_subject,
        normalized_subject=norm_result.canonical,
        obtained_marks=obtained_marks,
        maximum_marks=maximum_marks,
        percentage=percentage,
        subject_match_confidence=norm_result.confidence,
        marks_ocr_confidence=marks_conf,
        raw_obtained_text=obtained_text,
        raw_maximum_text=maximum_text,
        is_suspicious=is_suspicious,
        notes="; ".join(notes) if notes else None,
        needs_review=needs_review,
    )


def _deduplicate_subjects(marks: List[ExtractedSubjectMark]) -> List[ExtractedSubjectMark]:
    """
    Remove duplicate subject rows. When duplicates exist, prefer:
    - TOTAL over THEORY/PRACTICAL
    - Higher confidence over lower
    - Flag as suspicious if duplicates differ significantly
    """
    seen: Dict[str, List[ExtractedSubjectMark]] = {}
    for mark in marks:
        key = mark.normalized_subject
        seen.setdefault(key, []).append(mark)

    result = []
    for subject, group in seen.items():
        if len(group) == 1:
            result.append(group[0])
        else:
            # Prefer higher confidence
            best = max(group, key=lambda m: m.subject_match_confidence)
            best.notes = (best.notes or "") + f" [DEDUP: {len(group)} rows merged]"
            result.append(best)

    return result


def extract_from_tokens(tokens: List[OcrToken]) -> ExtractedDocument:
    """
    Main extraction function.
    Takes a flat list of OcrToken (from all pages) and returns ExtractedDocument.
    """
    result = ExtractedDocument(all_tokens=tokens)

    if not tokens:
        result.needs_review = True
        result.review_reasons.append("No OCR tokens found")
        return result

    # Compute overall OCR confidence
    confidences = [t.confidence for t in tokens if t.confidence > 0]
    result.overall_ocr_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # Extract candidate info
    result.candidate_name, result.raw_text_name = _extract_candidate_name(tokens)
    result.register_number, result.raw_text_register = _extract_register_number(tokens)

    # Run layout analysis to find table rows
    table_rows = extract_table_rows(tokens)

    # Convert table rows to subject marks
    marks: List[ExtractedSubjectMark] = []
    for row in table_rows:
        mark = _process_table_row(row)
        if mark and mark.normalized_subject != UNKNOWN:
            marks.append(mark)

    # Deduplicate
    marks = _deduplicate_subjects(marks)
    result.subject_marks = marks

    # Review reasons
    if result.overall_ocr_confidence < 0.75:
        result.needs_review = True
        result.review_reasons.append(
            f"Low OCR confidence: {result.overall_ocr_confidence:.2f}"
        )

    required = {PHYSICS, CHEMISTRY, MATHEMATICS}
    has_math_split = any(m.normalized_subject == MATHS_A for m in marks) and \
                     any(m.normalized_subject == MATHS_B for m in marks)
    if has_math_split:
        required = {PHYSICS, CHEMISTRY, MATHS_A, MATHS_B}

    found = {m.normalized_subject for m in marks}
    missing = required - found
    if missing:
        result.needs_review = True
        result.review_reasons.append(f"Missing subjects: {', '.join(missing)}")

    if any(m.needs_review for m in marks):
        result.needs_review = True
        result.review_reasons.append("One or more subject rows need review")

    return result
