"""
Unit tests for the mark validation engine.
"""
import pytest
from app.core.marks_extractor import ExtractedSubjectMark, ExtractedDocument
from app.core.validator import validate_mark, validate_document
from app.core.subject_normalizer import PHYSICS, CHEMISTRY, MATHEMATICS


def _sm(subject=PHYSICS, obtained=75.0, maximum=100.0, conf=0.95, suspicious=False, raw_obt="75", raw_max="100"):
    sm = ExtractedSubjectMark(
        raw_subject_name=subject,
        normalized_subject=subject,
        obtained_marks=obtained,
        maximum_marks=maximum,
        percentage=(obtained / maximum * 100) if (obtained is not None and maximum) else None,
        subject_match_confidence=conf,
        marks_ocr_confidence=conf,
        raw_obtained_text=raw_obt,
        raw_maximum_text=raw_max,
        is_suspicious=suspicious,
    )
    return sm


class TestMarkValidation:

    def test_valid_mark_passes(self):
        result = validate_mark(_sm(obtained=75.0, maximum=100.0))
        assert result.is_valid is True
        assert result.errors == []

    def test_obtained_exceeds_maximum_is_error(self):
        result = validate_mark(_sm(obtained=110.0, maximum=100.0))
        assert result.is_valid is False
        assert any("exceed" in e.message.lower() for e in result.errors)

    def test_none_obtained_is_error(self):
        result = validate_mark(_sm(obtained=None, maximum=100.0, raw_obt="abc"))
        assert result.is_valid is False
        assert any("parse" in e.message.lower() for e in result.errors)

    def test_none_maximum_is_warning(self):
        result = validate_mark(_sm(obtained=75.0, maximum=None, raw_max=""))
        assert result.needs_review is True

    def test_negative_obtained_is_error(self):
        result = validate_mark(_sm(obtained=-5.0, maximum=100.0))
        assert result.is_valid is False

    def test_zero_maximum_is_error(self):
        result = validate_mark(_sm(obtained=0.0, maximum=0.0))
        assert result.is_valid is False

    def test_suspicious_ocr_generates_warning(self):
        result = validate_mark(_sm(suspicious=True))
        assert result.needs_review is True
        assert any("suspicious" in w.message.lower() for w in result.warnings)

    def test_low_confidence_generates_warning(self):
        result = validate_mark(_sm(conf=0.5))
        assert result.needs_review is True
        assert any("confidence" in w.message.lower() for w in result.warnings)

    def test_percentage_out_of_range_is_error(self):
        sm = _sm(obtained=110.0, maximum=100.0)
        sm.percentage = 110.0  # Force bad percentage
        result = validate_mark(sm)
        assert result.is_valid is False

    def test_unusually_high_maximum_warns(self):
        result = validate_mark(_sm(obtained=400.0, maximum=600.0))
        assert result.needs_review is True

    def test_duplicate_subject_detected(self):
        sm1 = _sm(PHYSICS, obtained=75.0, maximum=100.0)
        sm2 = _sm(PHYSICS, obtained=80.0, maximum=100.0)
        doc = ExtractedDocument(
            candidate_name="Test",
            subject_marks=[sm1, sm2],
            overall_ocr_confidence=0.95,
        )
        result = validate_document(doc)
        assert result.needs_review is True
        assert any("duplicate" in w.message.lower() for w in result.warnings)

    def test_missing_candidate_name_warns(self):
        doc = ExtractedDocument(
            candidate_name=None,
            subject_marks=[_sm()],
            overall_ocr_confidence=0.95,
        )
        result = validate_document(doc)
        assert result.needs_review is True
        assert any("name" in w.message.lower() for w in result.warnings)
