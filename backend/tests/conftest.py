"""
pytest configuration and shared fixtures.
"""
import pytest


@pytest.fixture
def sample_physics_mark():
    from app.core.marks_extractor import ExtractedSubjectMark
    from app.core.subject_normalizer import PHYSICS
    return ExtractedSubjectMark(
        raw_subject_name="Physics",
        normalized_subject=PHYSICS,
        obtained_marks=75.0,
        maximum_marks=100.0,
        percentage=75.0,
        subject_match_confidence=1.0,
        marks_ocr_confidence=0.95,
    )
