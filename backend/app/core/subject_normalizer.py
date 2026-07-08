"""
Subject normalization using exact alias mapping + fuzzy matching (RapidFuzz).
Maps raw OCR subject names to canonical NormalizedSubject enum values.
"""
import re
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# Canonical subject names
PHYSICS = "PHYSICS"
CHEMISTRY = "CHEMISTRY"
MATHEMATICS = "MATHEMATICS"
MATHS_A = "MATHS_A"
MATHS_B = "MATHS_B"
OTHER = "OTHER"
UNKNOWN = "UNKNOWN"

# Exact + alias mapping (lowercase normalized keys → canonical)
EXACT_ALIASES: Dict[str, str] = {
    # Physics
    "physics": PHYSICS,
    "physics theory": PHYSICS,
    "phy": PHYSICS,
    "phy.": PHYSICS,
    "phys": PHYSICS,
    "phys.": PHYSICS,
    "physic": PHYSICS,
    "physics practical": PHYSICS,

    # Chemistry
    "chemistry": CHEMISTRY,
    "chemistry theory": CHEMISTRY,
    "chem": CHEMISTRY,
    "chem.": CHEMISTRY,
    "chm": CHEMISTRY,
    "chemistry practical": CHEMISTRY,

    # Mathematics (single)
    "mathematics": MATHEMATICS,
    "maths": MATHEMATICS,
    "math": MATHEMATICS,
    "maths theory": MATHEMATICS,
    "mathematics theory": MATHEMATICS,
    "mathematics ii": MATHEMATICS,
    "maths ii": MATHEMATICS,

    # Maths A (IIA)
    "maths a": MATHS_A,
    "mathematics a": MATHS_A,
    "maths iia": MATHS_A,
    "mathematics iia": MATHS_A,
    "maths 2a": MATHS_A,
    "mathematics 2a": MATHS_A,
    "math a": MATHS_A,
    "math 2a": MATHS_A,
    "math iia": MATHS_A,

    # Maths B (IIB)
    "maths b": MATHS_B,
    "mathematics b": MATHS_B,
    "maths iib": MATHS_B,
    "mathematics iib": MATHS_B,
    "maths 2b": MATHS_B,
    "mathematics 2b": MATHS_B,
    "math b": MATHS_B,
    "math 2b": MATHS_B,
    "math iib": MATHS_B,
}

# Fuzzy matching corpus — maps label → canonical
FUZZY_CORPUS: List[Tuple[str, str]] = [
    ("physics", PHYSICS),
    ("chemistry", CHEMISTRY),
    ("mathematics", MATHEMATICS),
    ("maths a", MATHS_A),
    ("maths b", MATHS_B),
    ("mathematics iia", MATHS_A),
    ("mathematics iib", MATHS_B),
]

FUZZY_LABELS = [label for label, _ in FUZZY_CORPUS]
FUZZY_LABEL_TO_CANONICAL = {label: canon for label, canon in FUZZY_CORPUS}

# Minimum fuzzy score to accept a match without review
FUZZY_AUTO_THRESHOLD = 80  # 0-100
FUZZY_REVIEW_THRESHOLD = 60


def _normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class NormalizationResult:
    canonical: str           # e.g. PHYSICS
    confidence: float        # 0.0–1.0
    method: str              # "exact", "fuzzy", "none"
    matched_alias: str       # the alias that was matched
    needs_review: bool       # True if confidence is low


def normalize_subject(raw_name: str) -> NormalizationResult:
    """
    Normalize a raw OCR subject name to a canonical subject.

    Pipeline:
    1. Exact alias lookup (confidence=1.0)
    2. Punctuation-removed exact lookup
    3. RapidFuzz fuzzy match
    4. If no match above threshold → UNKNOWN, needs_review=True
    """
    if not raw_name or not raw_name.strip():
        return NormalizationResult(
            canonical=UNKNOWN,
            confidence=0.0,
            method="none",
            matched_alias="",
            needs_review=True,
        )

    normalized = _normalize_text(raw_name)

    # 1. Exact match
    if normalized in EXACT_ALIASES:
        return NormalizationResult(
            canonical=EXACT_ALIASES[normalized],
            confidence=1.0,
            method="exact",
            matched_alias=normalized,
            needs_review=False,
        )

    # 2. Partial word match (for OCR fragments like "Phy" matching "physics")
    for alias, canonical in EXACT_ALIASES.items():
        if normalized.startswith(alias) or alias.startswith(normalized):
            if len(normalized) >= 3:
                conf = len(normalized) / max(len(alias), len(normalized))
                if conf >= 0.7:
                    return NormalizationResult(
                        canonical=canonical,
                        confidence=conf,
                        method="exact_partial",
                        matched_alias=alias,
                        needs_review=conf < 0.85,
                    )

    # 3. Fuzzy match
    result = process.extractOne(
        normalized,
        FUZZY_LABELS,
        scorer=fuzz.token_sort_ratio,
    )

    if result is None:
        return NormalizationResult(
            canonical=UNKNOWN,
            confidence=0.0,
            method="none",
            matched_alias="",
            needs_review=True,
        )

    matched_label, score, _ = result
    confidence = score / 100.0
    canonical = FUZZY_LABEL_TO_CANONICAL[matched_label]

    if score >= FUZZY_AUTO_THRESHOLD:
        return NormalizationResult(
            canonical=canonical,
            confidence=confidence,
            method="fuzzy",
            matched_alias=matched_label,
            needs_review=False,
        )
    elif score >= FUZZY_REVIEW_THRESHOLD:
        return NormalizationResult(
            canonical=canonical,
            confidence=confidence,
            method="fuzzy_weak",
            matched_alias=matched_label,
            needs_review=True,
        )
    else:
        return NormalizationResult(
            canonical=UNKNOWN,
            confidence=confidence,
            method="fuzzy_rejected",
            matched_alias=matched_label,
            needs_review=True,
        )
