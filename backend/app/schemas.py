"""
Pydantic schemas for API request/response validation.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


# ─── Batch Schemas ───────────────────────────────────────────────────────────

class BatchCreate(BaseModel):
    name: Optional[str] = None
    cutoff_formula: str = "pcm_average"
    math_mode: str = "combined"
    eligibility_threshold: float = 50.0
    notes: Optional[str] = None


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: Optional[str]
    status: str
    total_documents: int
    queued_count: int
    processing_count: int
    completed_count: int
    failed_count: int
    eligible_count: int
    not_eligible_count: int
    review_required_count: int
    cutoff_formula: str
    math_mode: str
    eligibility_threshold: float
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


class BatchProgress(BaseModel):
    batch_id: uuid.UUID
    status: str
    total: int
    queued: int
    processing: int
    completed: int
    failed: int
    eligible: int
    not_eligible: int
    review_required: int
    progress_percent: float


# ─── Document Schemas ─────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    original_filename: str
    file_size_bytes: int
    mime_type: str
    document_type: str
    page_count: int
    status: str
    overall_ocr_confidence: Optional[float]
    requires_review: bool
    is_duplicate: bool
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime]


class SubjectMarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    raw_subject_name: str
    normalized_subject: str
    mark_type: str
    obtained_marks: Optional[float]
    maximum_marks: Optional[float]
    percentage: Optional[float]
    subject_match_confidence: Optional[float]
    marks_ocr_confidence: Optional[float]
    is_suspicious: bool
    is_manually_corrected: bool
    notes: Optional[str]


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: Optional[str]
    register_number: Optional[str]
    roll_number: Optional[str]
    exam_year: Optional[str]
    subject_marks: List[SubjectMarkResponse] = []


class ExtractionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    physics_percentage: Optional[float]
    chemistry_percentage: Optional[float]
    mathematics_percentage: Optional[float]
    maths_a_percentage: Optional[float]
    maths_b_percentage: Optional[float]
    math_mode_used: Optional[str]
    pcm_cutoff: Optional[float]
    cutoff_formula_used: Optional[str]
    total_obtained: Optional[float]
    total_maximum: Optional[float]
    overall_percentage: Optional[float]
    combined_confidence: Optional[float]
    ocr_confidence: Optional[float]
    has_missing_subjects: bool
    missing_subjects: Optional[List[str]]
    has_suspicious_values: bool
    validation_warnings: Optional[List[Dict[str, Any]]]


class EligibilityResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    physics_passed: Optional[bool]
    chemistry_passed: Optional[bool]
    mathematics_passed: Optional[bool]
    overall_passed: Optional[bool]
    eligibility_threshold: float
    rejection_reasons: Optional[List[str]]
    review_reasons: Optional[List[str]]
    is_manually_reviewed: bool
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]


class DocumentDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document: DocumentResponse
    candidate: Optional[CandidateResponse]
    extraction_result: Optional[ExtractionResultResponse]
    eligibility_result: Optional[EligibilityResultResponse]


class OcrTokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_number: int
    text: str
    confidence: float
    bounding_box: Optional[Any]
    x_min: Optional[float]
    y_min: Optional[float]
    x_max: Optional[float]
    y_max: Optional[float]


# ─── Review Schemas ───────────────────────────────────────────────────────────

class SubjectMarkCorrection(BaseModel):
    subject_mark_id: uuid.UUID
    obtained_marks: Optional[float]
    maximum_marks: Optional[float]


class ReviewSubmit(BaseModel):
    reviewer: Optional[str] = "admin"
    subject_corrections: List[SubjectMarkCorrection] = []
    override_status: Optional[str] = None  # Force ELIGIBLE / NOT_ELIGIBLE
    review_notes: Optional[str] = None


class ReviewResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    message: str
    recalculated_eligibility: Optional[str]


# ─── Upload Response ──────────────────────────────────────────────────────────

class UploadFileResult(BaseModel):
    filename: str
    document_id: Optional[uuid.UUID]
    status: str  # "queued" | "duplicate" | "error"
    message: Optional[str]


class BatchUploadResponse(BaseModel):
    batch_id: uuid.UUID
    total_uploaded: int
    queued: int
    duplicates: int
    errors: int
    results: List[UploadFileResult]
