"""
Eligibility Rule Engine.
Strict > 50% threshold for Physics, Chemistry, Mathematics, and Overall.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, List

from app.core.cutoff_calculator import CutoffResult

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 50.0  # Strict greater-than (not >=)


@dataclass
class EligibilityDecision:
    status: str  # "ELIGIBLE" | "NOT_ELIGIBLE" | "REVIEW_REQUIRED"

    physics_passed: Optional[bool]
    chemistry_passed: Optional[bool]
    mathematics_passed: Optional[bool]
    overall_passed: Optional[bool]

    rejection_reasons: List[str] = field(default_factory=list)
    review_reasons: List[str] = field(default_factory=list)

    eligibility_threshold: float = DEFAULT_THRESHOLD


def _check_subject(
    percentage: Optional[float],
    subject_name: str,
    threshold: float,
    review_reasons: List[str],
    rejection_reasons: List[str],
) -> Optional[bool]:
    """
    Check a single subject against the threshold.
    Returns True (passed), False (failed), or None (data missing → review).
    """
    if percentage is None:
        review_reasons.append(
            f"{subject_name} percentage is missing — cannot determine eligibility"
        )
        return None

    if percentage > threshold:
        return True
    else:
        rejection_reasons.append(
            f"{subject_name} percentage is {percentage:.2f}%, below the required threshold of >{threshold:.0f}%"
        )
        return False


def determine_eligibility(
    cutoff_result: CutoffResult,
    threshold: float = DEFAULT_THRESHOLD,
) -> EligibilityDecision:
    """
    Apply eligibility rules to a CutoffResult.

    A candidate is ELIGIBLE only when ALL of:
      - Physics %  > threshold
      - Chemistry % > threshold
      - Mathematics % > threshold
      - Overall %  > threshold

    REVIEW_REQUIRED if any required field is missing or ambiguous.
    NOT_ELIGIBLE if any condition fails.
    """
    rejection_reasons: List[str] = []
    review_reasons: List[str] = []

    physics_passed = _check_subject(
        cutoff_result.physics_percentage, "Physics", threshold,
        review_reasons, rejection_reasons
    )
    chemistry_passed = _check_subject(
        cutoff_result.chemistry_percentage, "Chemistry", threshold,
        review_reasons, rejection_reasons
    )
    mathematics_passed = _check_subject(
        cutoff_result.mathematics_percentage, "Mathematics", threshold,
        review_reasons, rejection_reasons
    )
    overall_passed = _check_subject(
        cutoff_result.overall_percentage, "Overall", threshold,
        review_reasons, rejection_reasons
    )

    # Add warnings from cutoff calculation
    for w in cutoff_result.warnings:
        review_reasons.append(f"[Calculation warning] {w}")

    # Missing PCM subjects always require review
    if cutoff_result.missing_subjects:
        for subj in cutoff_result.missing_subjects:
            review_reasons.append(f"Missing subject in extraction: {subj}")

    # Determine status
    all_checks = [physics_passed, chemistry_passed, mathematics_passed, overall_passed]

    if any(c is None for c in all_checks):
        # At least one required field is missing
        status = "REVIEW_REQUIRED"
    elif all(c is True for c in all_checks):
        status = "ELIGIBLE"
    else:
        status = "NOT_ELIGIBLE"

    return EligibilityDecision(
        status=status,
        physics_passed=physics_passed,
        chemistry_passed=chemistry_passed,
        mathematics_passed=mathematics_passed,
        overall_passed=overall_passed,
        rejection_reasons=rejection_reasons,
        review_reasons=review_reasons,
        eligibility_threshold=threshold,
    )
