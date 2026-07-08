"""
Unit tests for the eligibility engine.
Covers: strict >50 threshold, exactly 50%, missing subjects, all cases.
"""
import pytest
from app.core.cutoff_calculator import CutoffResult
from app.core.eligibility_engine import determine_eligibility, EligibilityDecision

def _make_cutoff(**kwargs) -> CutoffResult:
    defaults = dict(
        physics_percentage=75.0,
        chemistry_percentage=80.0,
        mathematics_percentage=70.0,
        maths_a_percentage=None,
        maths_b_percentage=None,
        math_mode_used="single",
        pcm_cutoff=75.0,
        cutoff_formula_used="pcm_average",
        total_obtained=700.0,
        total_maximum=1000.0,
        overall_percentage=70.0,
        missing_subjects=[],
        warnings=[],
    )
    defaults.update(kwargs)
    return CutoffResult(**defaults)


class TestEligibilityEngine:

    def test_all_above_threshold_is_eligible(self):
        cutoff = _make_cutoff(
            physics_percentage=60.0,
            chemistry_percentage=65.0,
            mathematics_percentage=55.0,
            overall_percentage=60.0,
        )
        result = determine_eligibility(cutoff, threshold=50.0)
        assert result.status == "ELIGIBLE"
        assert result.physics_passed is True
        assert result.chemistry_passed is True
        assert result.mathematics_passed is True
        assert result.overall_passed is True
        assert result.rejection_reasons == []

    def test_exactly_50_is_not_eligible(self):
        """Strict > 50 means exactly 50 FAILS."""
        cutoff = _make_cutoff(
            physics_percentage=50.0,
            chemistry_percentage=60.0,
            mathematics_percentage=60.0,
            overall_percentage=55.0,
        )
        result = determine_eligibility(cutoff, threshold=50.0)
        assert result.status == "NOT_ELIGIBLE"
        assert result.physics_passed is False
        assert "Physics" in result.rejection_reasons[0]
        assert "50.00%" in result.rejection_reasons[0]

    def test_50_point_01_is_eligible(self):
        """50.01% passes the strict >50 threshold."""
        cutoff = _make_cutoff(
            physics_percentage=50.01,
            chemistry_percentage=50.01,
            mathematics_percentage=50.01,
            overall_percentage=50.01,
        )
        result = determine_eligibility(cutoff, threshold=50.0)
        assert result.status == "ELIGIBLE"

    def test_missing_physics_requires_review(self):
        cutoff = _make_cutoff(
            physics_percentage=None,
            missing_subjects=["PHYSICS"],
        )
        result = determine_eligibility(cutoff)
        assert result.status == "REVIEW_REQUIRED"
        assert result.physics_passed is None
        assert any("Physics" in r for r in result.review_reasons)

    def test_missing_chemistry_requires_review(self):
        cutoff = _make_cutoff(chemistry_percentage=None, missing_subjects=["CHEMISTRY"])
        result = determine_eligibility(cutoff)
        assert result.status == "REVIEW_REQUIRED"

    def test_missing_mathematics_requires_review(self):
        cutoff = _make_cutoff(mathematics_percentage=None, missing_subjects=["MATHEMATICS"])
        result = determine_eligibility(cutoff)
        assert result.status == "REVIEW_REQUIRED"

    def test_missing_overall_requires_review(self):
        cutoff = _make_cutoff(overall_percentage=None)
        result = determine_eligibility(cutoff)
        assert result.status == "REVIEW_REQUIRED"

    def test_physics_below_threshold_not_eligible(self):
        cutoff = _make_cutoff(physics_percentage=30.0)
        result = determine_eligibility(cutoff)
        assert result.status == "NOT_ELIGIBLE"
        assert result.physics_passed is False
        assert len(result.rejection_reasons) >= 1

    def test_multiple_subjects_failing_lists_all_reasons(self):
        cutoff = _make_cutoff(
            physics_percentage=40.0,
            chemistry_percentage=45.0,
            mathematics_percentage=60.0,
            overall_percentage=45.0,
        )
        result = determine_eligibility(cutoff)
        assert result.status == "NOT_ELIGIBLE"
        assert result.physics_passed is False
        assert result.chemistry_passed is False
        assert result.mathematics_passed is True
        assert result.overall_passed is False
        assert len(result.rejection_reasons) == 3  # Physics, Chemistry, Overall

    def test_overall_below_threshold_alone_makes_not_eligible(self):
        cutoff = _make_cutoff(
            physics_percentage=60.0,
            chemistry_percentage=65.0,
            mathematics_percentage=70.0,
            overall_percentage=49.9,
        )
        result = determine_eligibility(cutoff)
        assert result.status == "NOT_ELIGIBLE"
        assert result.overall_passed is False

    def test_custom_threshold(self):
        cutoff = _make_cutoff(
            physics_percentage=60.0,
            chemistry_percentage=60.0,
            mathematics_percentage=60.0,
            overall_percentage=60.0,
        )
        # At threshold=65, all 60% subjects fail
        result = determine_eligibility(cutoff, threshold=65.0)
        assert result.status == "NOT_ELIGIBLE"
        assert result.eligibility_threshold == 65.0

    def test_warnings_from_cutoff_added_to_review_reasons(self):
        cutoff = _make_cutoff(
            physics_percentage=None,
            warnings=["Overall percentage calculated from sum of extracted subjects"],
            missing_subjects=["PHYSICS"],
        )
        result = determine_eligibility(cutoff)
        assert result.status == "REVIEW_REQUIRED"
        assert any("Calculation warning" in r for r in result.review_reasons)
