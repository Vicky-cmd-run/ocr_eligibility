"""
Unit tests for subject normalizer.
"""
import pytest
from app.core.subject_normalizer import normalize_subject, PHYSICS, CHEMISTRY, MATHEMATICS, MATHS_A, MATHS_B, UNKNOWN


class TestSubjectNormalizer:

    @pytest.mark.parametrize("raw,expected", [
        ("Physics", PHYSICS),
        ("PHYSICS", PHYSICS),
        ("Phy", PHYSICS),
        ("Phy.", PHYSICS),
        ("Physics Theory", PHYSICS),
        ("Chemistry", CHEMISTRY),
        ("CHEM", CHEMISTRY),
        ("Chem.", CHEMISTRY),
        ("Mathematics", MATHEMATICS),
        ("Maths", MATHEMATICS),
        ("Math", MATHEMATICS),
        ("Mathematics II", MATHEMATICS),
        ("Maths A", MATHS_A),
        ("Mathematics A", MATHS_A),
        ("Maths IIA", MATHS_A),
        ("Mathematics IIA", MATHS_A),
        ("Maths 2A", MATHS_A),
        ("Maths B", MATHS_B),
        ("Mathematics B", MATHS_B),
        ("Maths IIB", MATHS_B),
        ("Mathematics IIB", MATHS_B),
        ("Maths 2B", MATHS_B),
    ])
    def test_exact_aliases(self, raw, expected):
        result = normalize_subject(raw)
        assert result.canonical == expected, f"'{raw}' → expected {expected}, got {result.canonical}"
        assert result.needs_review is False or result.confidence >= 0.7

    def test_empty_string_returns_unknown(self):
        result = normalize_subject("")
        assert result.canonical == UNKNOWN
        assert result.needs_review is True

    def test_none_like_string_returns_unknown(self):
        result = normalize_subject("   ")
        assert result.canonical == UNKNOWN

    def test_fuzzy_match_physics_typo(self):
        """'Physecs' should fuzzy-match to PHYSICS."""
        result = normalize_subject("Physecs")
        assert result.canonical == PHYSICS
        assert result.method in ("fuzzy", "fuzzy_weak", "exact_partial")

    def test_fuzzy_match_chemistry_typo(self):
        result = normalize_subject("Chemistr")
        assert result.canonical == CHEMISTRY

    def test_unrecognized_subject_returns_unknown(self):
        result = normalize_subject("Botany")
        assert result.canonical == UNKNOWN

    def test_confidence_is_1_for_exact_match(self):
        result = normalize_subject("Physics")
        assert result.confidence == 1.0
        assert result.method == "exact"

    def test_fuzzy_weak_needs_review(self):
        """Very loose fuzzy matches need review."""
        result = normalize_subject("Xyzabc")
        assert result.needs_review is True

    def test_case_insensitive(self):
        assert normalize_subject("PHYSICS").canonical == PHYSICS
        assert normalize_subject("physics").canonical == PHYSICS
        assert normalize_subject("Physics").canonical == PHYSICS
