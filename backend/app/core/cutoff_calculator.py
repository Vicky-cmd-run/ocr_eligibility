"""
Cutoff Calculation Engine.
Supports:
  1. PCM Average: (Physics% + Chemistry% + Math%) / 3
  2. Engineering 200-mark formula: Math + Physics/2 + Chemistry/2
  3. Weighted Math (A+B combined percentage)
  4. Simple Math average (A+B)/2
"""
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

from app.core.marks_extractor import ExtractedSubjectMark
from app.core.subject_normalizer import PHYSICS, CHEMISTRY, MATHEMATICS, MATHS_A, MATHS_B

logger = logging.getLogger(__name__)


@dataclass
class CutoffResult:
    physics_percentage: Optional[float]
    chemistry_percentage: Optional[float]
    mathematics_percentage: Optional[float]

    maths_a_percentage: Optional[float]
    maths_b_percentage: Optional[float]
    math_mode_used: str       # "single" | "combined" | "simple_average"

    pcm_cutoff: Optional[float]
    cutoff_formula_used: str  # "pcm_average" | "engineering_200"

    total_obtained: Optional[float]
    total_maximum: Optional[float]
    overall_percentage: Optional[float]

    missing_subjects: List[str]
    warnings: List[str]


def _subject_percentage(marks: List[ExtractedSubjectMark], subject: str) -> Optional[float]:
    """Return percentage for a given normalized subject, or None."""
    for m in marks:
        if m.normalized_subject == subject and m.percentage is not None:
            return m.percentage
    return None


def _subject_marks(marks: List[ExtractedSubjectMark], subject: str):
    """Return (obtained, maximum) for a subject, or (None, None)."""
    for m in marks:
        if m.normalized_subject == subject:
            return m.obtained_marks, m.maximum_marks
    return None, None


def calculate_cutoff(
    subject_marks: List[ExtractedSubjectMark],
    cutoff_formula: str = "pcm_average",
    math_mode: str = "combined",
) -> CutoffResult:
    """
    Calculate PCM cutoff and overall percentage from extracted subject marks.

    Args:
        subject_marks: list of ExtractedSubjectMark
        cutoff_formula: "pcm_average" or "engineering_200"
        math_mode: "combined" (weighted) or "simple_average"
    """
    missing: List[str] = []
    warnings: List[str] = []

    # --- Physics ---
    physics_pct = _subject_percentage(subject_marks, PHYSICS)
    if physics_pct is None:
        missing.append("PHYSICS")

    # --- Chemistry ---
    chemistry_pct = _subject_percentage(subject_marks, CHEMISTRY)
    if chemistry_pct is None:
        missing.append("CHEMISTRY")

    # --- Mathematics ---
    # Detect if we have single Math or Math A + Math B
    single_math_pct = _subject_percentage(subject_marks, MATHEMATICS)
    maths_a_pct = _subject_percentage(subject_marks, MATHS_A)
    maths_b_pct = _subject_percentage(subject_marks, MATHS_B)

    math_pct: Optional[float] = None
    math_mode_used = "single"

    if single_math_pct is not None:
        math_pct = single_math_pct
        math_mode_used = "single"

    elif maths_a_pct is not None or maths_b_pct is not None:
        if math_mode == "combined":
            # Weighted combined percentage: (A_obtained + B_obtained) / (A_max + B_max) * 100
            a_obt, a_max = _subject_marks(subject_marks, MATHS_A)
            b_obt, b_max = _subject_marks(subject_marks, MATHS_B)

            if (a_obt is not None and a_max is not None and a_max > 0 and
                    b_obt is not None and b_max is not None and b_max > 0):
                math_pct = (a_obt + b_obt) / (a_max + b_max) * 100.0
                math_mode_used = "combined"
            elif maths_a_pct is not None and maths_b_pct is None:
                math_pct = maths_a_pct
                math_mode_used = "single_a_only"
                warnings.append("Only Maths A found; Maths B missing")
            elif maths_b_pct is not None and maths_a_pct is None:
                math_pct = maths_b_pct
                math_mode_used = "single_b_only"
                warnings.append("Only Maths B found; Maths A missing")
            else:
                missing.append("MATHEMATICS")
        else:
            # Simple average mode
            if maths_a_pct is not None and maths_b_pct is not None:
                math_pct = (maths_a_pct + maths_b_pct) / 2.0
                math_mode_used = "simple_average"
            elif maths_a_pct is not None:
                math_pct = maths_a_pct
                math_mode_used = "simple_a_only"
                warnings.append("Only Maths A found; Maths B missing")
            elif maths_b_pct is not None:
                math_pct = maths_b_pct
                math_mode_used = "simple_b_only"
                warnings.append("Only Maths B found; Maths A missing")
            else:
                missing.append("MATHEMATICS")
    else:
        missing.append("MATHEMATICS")

    # --- PCM Cutoff ---
    pcm_cutoff: Optional[float] = None
    if physics_pct is not None and chemistry_pct is not None and math_pct is not None:
        if cutoff_formula == "pcm_average":
            pcm_cutoff = (physics_pct + chemistry_pct + math_pct) / 3.0
        elif cutoff_formula == "engineering_200":
            # Engineering cutoff: Math + Physics/2 + Chemistry/2
            # (out of 200: Math 100, Phy 50, Chem 50)
            pcm_cutoff = math_pct + (physics_pct / 2.0) + (chemistry_pct / 2.0)
        else:
            warnings.append(f"Unknown cutoff formula '{cutoff_formula}', using PCM average")
            pcm_cutoff = (physics_pct + chemistry_pct + math_pct) / 3.0
    else:
        if missing:
            warnings.append(f"PCM cutoff cannot be calculated; missing: {', '.join(missing)}")

    # --- Overall Percentage ---
    # Try to get explicit total obtained / total maximum from marksheet
    total_obtained: Optional[float] = None
    total_maximum: Optional[float] = None
    overall_pct: Optional[float] = None

    for m in subject_marks:
        raw = (m.raw_subject_name or "").lower()
        if any(w in raw for w in ("grand total", "total", "aggregate", "overall")):
            if m.obtained_marks is not None and m.maximum_marks is not None and m.maximum_marks > 0:
                total_obtained = m.obtained_marks
                total_maximum = m.maximum_marks
                overall_pct = (total_obtained / total_maximum) * 100.0
                break

    # Fallback: sum all PCM subjects if explicit total unavailable
    if overall_pct is None:
        all_obtained = []
        all_maximum = []
        for m in subject_marks:
            if m.obtained_marks is not None and m.maximum_marks is not None:
                all_obtained.append(m.obtained_marks)
                all_maximum.append(m.maximum_marks)

        if all_obtained and sum(all_maximum) > 0:
            total_obtained = sum(all_obtained)
            total_maximum = sum(all_maximum)
            overall_pct = (total_obtained / total_maximum) * 100.0
            warnings.append("Overall percentage calculated from sum of extracted subjects (no explicit total found)")

    return CutoffResult(
        physics_percentage=physics_pct,
        chemistry_percentage=chemistry_pct,
        mathematics_percentage=math_pct,
        maths_a_percentage=maths_a_pct,
        maths_b_percentage=maths_b_pct,
        math_mode_used=math_mode_used,
        pcm_cutoff=pcm_cutoff,
        cutoff_formula_used=cutoff_formula,
        total_obtained=total_obtained,
        total_maximum=total_maximum,
        overall_percentage=overall_pct,
        missing_subjects=missing,
        warnings=warnings,
    )
