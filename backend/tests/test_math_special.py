"""
Unit tests for cutoff calculator — Math special cases (single, A+B combined, simple average).
"""
import pytest
from app.core.marks_extractor import ExtractedSubjectMark
from app.core.cutoff_calculator import calculate_cutoff
from app.core.subject_normalizer import PHYSICS, CHEMISTRY, MATHEMATICS, MATHS_A, MATHS_B


def _mark(subject: str, obtained: float, maximum: float) -> ExtractedSubjectMark:
    return ExtractedSubjectMark(
        raw_subject_name=subject,
        normalized_subject=subject,
        obtained_marks=obtained,
        maximum_marks=maximum,
        percentage=(obtained / maximum * 100) if maximum else None,
        subject_match_confidence=1.0,
        marks_ocr_confidence=1.0,
    )


class TestCutoffCalculator:

    def test_single_math_pcm_average(self):
        marks = [
            _mark(PHYSICS, 75, 100),
            _mark(CHEMISTRY, 80, 100),
            _mark(MATHEMATICS, 70, 100),
        ]
        result = calculate_cutoff(marks, cutoff_formula="pcm_average", math_mode="combined")
        assert result.physics_percentage == pytest.approx(75.0)
        assert result.chemistry_percentage == pytest.approx(80.0)
        assert result.mathematics_percentage == pytest.approx(70.0)
        assert result.pcm_cutoff == pytest.approx((75 + 80 + 70) / 3, rel=1e-3)
        assert result.math_mode_used == "single"
        assert result.missing_subjects == []

    def test_maths_ab_combined_weighted(self):
        """Maths A+B combined: (A_obt + B_obt) / (A_max + B_max) * 100"""
        marks = [
            _mark(PHYSICS, 75, 100),
            _mark(CHEMISTRY, 80, 100),
            _mark(MATHS_A, 60, 75),   # 80%
            _mark(MATHS_B, 50, 75),   # 66.67%
        ]
        result = calculate_cutoff(marks, cutoff_formula="pcm_average", math_mode="combined")
        expected_math = (60 + 50) / (75 + 75) * 100  # 73.33%
        assert result.mathematics_percentage == pytest.approx(expected_math, rel=1e-3)
        assert result.math_mode_used == "combined"
        assert result.maths_a_percentage == pytest.approx(80.0)
        assert result.maths_b_percentage == pytest.approx(50 / 75 * 100, rel=1e-3)

    def test_maths_ab_simple_average(self):
        """Simple average: (A% + B%) / 2"""
        marks = [
            _mark(PHYSICS, 75, 100),
            _mark(CHEMISTRY, 80, 100),
            _mark(MATHS_A, 60, 75),   # 80%
            _mark(MATHS_B, 50, 75),   # 66.67%
        ]
        result = calculate_cutoff(marks, cutoff_formula="pcm_average", math_mode="simple_average")
        expected_math = (80.0 + (50 / 75 * 100)) / 2
        assert result.mathematics_percentage == pytest.approx(expected_math, rel=1e-3)
        assert result.math_mode_used == "simple_average"

    def test_engineering_200_formula(self):
        """Cutoff = Math + Physics/2 + Chemistry/2"""
        marks = [
            _mark(PHYSICS, 80, 100),   # 80%
            _mark(CHEMISTRY, 70, 100), # 70%
            _mark(MATHEMATICS, 90, 100), # 90%
        ]
        result = calculate_cutoff(marks, cutoff_formula="engineering_200")
        expected = 90 + (80 / 2) + (70 / 2)  # 90 + 40 + 35 = 165
        assert result.pcm_cutoff == pytest.approx(expected, rel=1e-3)
        assert result.cutoff_formula_used == "engineering_200"

    def test_missing_all_subjects_no_cutoff(self):
        marks = []
        result = calculate_cutoff(marks)
        assert result.pcm_cutoff is None
        assert "PHYSICS" in result.missing_subjects
        assert "CHEMISTRY" in result.missing_subjects
        assert "MATHEMATICS" in result.missing_subjects

    def test_missing_physics_warns(self):
        marks = [
            _mark(CHEMISTRY, 80, 100),
            _mark(MATHEMATICS, 70, 100),
        ]
        result = calculate_cutoff(marks)
        assert result.pcm_cutoff is None
        assert "PHYSICS" in result.missing_subjects

    def test_only_maths_a_warns_and_uses_a_only(self):
        marks = [
            _mark(PHYSICS, 75, 100),
            _mark(CHEMISTRY, 80, 100),
            _mark(MATHS_A, 60, 75),
        ]
        result = calculate_cutoff(marks, math_mode="combined")
        assert "single_a_only" in result.math_mode_used
        assert result.mathematics_percentage == pytest.approx(60 / 75 * 100, rel=1e-3)
        assert any("Maths B missing" in w for w in result.warnings)

    def test_overall_percentage_from_explicit_total(self):
        """If a 'Grand Total' subject exists, use it for overall%."""
        marks = [
            _mark(PHYSICS, 75, 100),
            _mark(CHEMISTRY, 80, 100),
            _mark(MATHEMATICS, 70, 100),
            ExtractedSubjectMark(
                raw_subject_name="Grand Total",
                normalized_subject="OTHER",
                obtained_marks=500,
                maximum_marks=700,
                percentage=500/700*100,
                subject_match_confidence=1.0,
                marks_ocr_confidence=1.0,
            ),
        ]
        result = calculate_cutoff(marks)
        assert result.total_obtained == pytest.approx(500.0)
        assert result.total_maximum == pytest.approx(700.0)
        assert result.overall_percentage == pytest.approx(500/700*100, rel=1e-3)

    def test_overall_falls_back_to_sum_of_subjects(self):
        marks = [
            _mark(PHYSICS, 75, 100),
            _mark(CHEMISTRY, 80, 100),
            _mark(MATHEMATICS, 70, 100),
        ]
        result = calculate_cutoff(marks)
        assert result.overall_percentage == pytest.approx((75+80+70)/300*100, rel=1e-3)
        assert any("sum of extracted subjects" in w for w in result.warnings)

    def test_pcm_cutoff_is_none_when_math_missing(self):
        marks = [
            _mark(PHYSICS, 75, 100),
            _mark(CHEMISTRY, 80, 100),
        ]
        result = calculate_cutoff(marks)
        assert result.pcm_cutoff is None
        assert "MATHEMATICS" in result.missing_subjects
