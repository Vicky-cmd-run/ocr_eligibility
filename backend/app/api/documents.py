"""
Document API endpoints — review, reprocess, OCR tokens.
"""
import uuid
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.schemas import (
    DocumentDetailResponse, OcrTokenResponse,
    ReviewSubmit, ReviewResponse,
)
from app.models.document import Document
from app.models.candidate import Candidate
from app.models.subject_mark import SubjectMark
from app.models.ocr_token import OcrToken
from app.models.extraction_result import ExtractionResult
from app.models.eligibility_result import EligibilityResult, EligibilityStatus
from app.models.review_action import ReviewAction, ReviewActionType
from app.models.audit_log import AuditLog
from app.core.cutoff_calculator import calculate_cutoff
from app.core.eligibility_engine import determine_eligibility
from app.core.marks_extractor import ExtractedSubjectMark
from app.tasks.document_tasks import process_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


async def _get_document_or_404(document_id: uuid.UUID, db: AsyncSession) -> Document:
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get document details with candidate, extraction, and eligibility data."""
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.candidate).selectinload(Candidate.subject_marks),
            selectinload(Document.extraction_result),
            selectinload(Document.eligibility_result),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentDetailResponse(
        document=doc,
        candidate=doc.candidate,
        extraction_result=doc.extraction_result,
        eligibility_result=doc.eligibility_result,
    )


@router.get("/{document_id}/ocr", response_model=List[OcrTokenResponse])
async def get_ocr_tokens(
    document_id: uuid.UUID,
    page: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get OCR tokens for a document, optionally filtered by page number."""
    await _get_document_or_404(document_id, db)

    query = select(OcrToken).where(OcrToken.document_id == document_id)
    if page is not None:
        query = query.where(OcrToken.page_number == page)
    query = query.order_by(OcrToken.y_min, OcrToken.x_min)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{document_id}/review")
async def get_review_data(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get full review data including audit trail."""
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.candidate).selectinload(Candidate.subject_marks),
            selectinload(Document.extraction_result),
            selectinload(Document.eligibility_result),
            selectinload(Document.review_actions),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "document": {
            "id": str(doc.id),
            "original_filename": doc.original_filename,
            "file_path": doc.file_path,
            "status": doc.status,
            "document_type": doc.document_type,
            "page_count": doc.page_count,
            "overall_ocr_confidence": doc.overall_ocr_confidence,
            "requires_review": doc.requires_review,
            "error_message": doc.error_message,
        },
        "candidate": {
            "name": doc.candidate.name if doc.candidate else None,
            "register_number": doc.candidate.register_number if doc.candidate else None,
            "subject_marks": [
                {
                    "id": str(sm.id),
                    "raw_subject_name": sm.raw_subject_name,
                    "normalized_subject": sm.normalized_subject,
                    "obtained_marks": sm.obtained_marks,
                    "maximum_marks": sm.maximum_marks,
                    "percentage": sm.percentage,
                    "subject_match_confidence": sm.subject_match_confidence,
                    "marks_ocr_confidence": sm.marks_ocr_confidence,
                    "raw_obtained_text": sm.raw_obtained_text,
                    "raw_maximum_text": sm.raw_maximum_text,
                    "is_suspicious": sm.is_suspicious,
                    "is_manually_corrected": sm.is_manually_corrected,
                    "notes": sm.notes,
                }
                for sm in (doc.candidate.subject_marks if doc.candidate else [])
            ],
        } if doc.candidate else None,
        "extraction_result": _serialize_extraction(doc.extraction_result),
        "eligibility_result": _serialize_eligibility(doc.eligibility_result),
        "review_actions": [
            {
                "id": str(ra.id),
                "action_type": ra.action_type,
                "reviewer": ra.reviewer,
                "before_state": ra.before_state,
                "after_state": ra.after_state,
                "notes": ra.notes,
                "created_at": ra.created_at.isoformat() if ra.created_at else None,
            }
            for ra in (doc.review_actions or [])
        ],
    }


@router.put("/{document_id}/review", response_model=ReviewResponse)
async def submit_review(
    document_id: uuid.UUID,
    payload: ReviewSubmit,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit manual review corrections.
    Applies mark corrections, recalculates eligibility, updates status.
    """
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.candidate).selectinload(Candidate.subject_marks),
            selectinload(Document.extraction_result),
            selectinload(Document.eligibility_result),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    before_state = _serialize_review_state(doc)

    # Apply subject mark corrections
    corrected_marks = []
    if doc.candidate and payload.subject_corrections:
        for correction in payload.subject_corrections:
            sm_result = await db.execute(
                select(SubjectMark).where(
                    SubjectMark.id == correction.subject_mark_id,
                    SubjectMark.candidate_id == doc.candidate.id,
                )
            )
            sm = sm_result.scalar_one_or_none()
            if sm:
                sm.obtained_marks = correction.obtained_marks
                sm.maximum_marks = correction.maximum_marks
                if sm.obtained_marks is not None and sm.maximum_marks and sm.maximum_marks > 0:
                    sm.percentage = (sm.obtained_marks / sm.maximum_marks) * 100.0
                sm.is_manually_corrected = True
                corrected_marks.append(sm)

    await db.flush()

    # Recalculate cutoff and eligibility from corrected marks
    if doc.candidate:
        all_marks = doc.candidate.subject_marks
        mock_marks = [
            ExtractedSubjectMark(
                raw_subject_name=sm.raw_subject_name,
                normalized_subject=sm.normalized_subject,
                obtained_marks=sm.obtained_marks,
                maximum_marks=sm.maximum_marks,
                percentage=sm.percentage,
                subject_match_confidence=sm.subject_match_confidence or 1.0,
                marks_ocr_confidence=sm.marks_ocr_confidence or 1.0,
            )
            for sm in all_marks
        ]

        batch = await db.get(
            __import__("app.models.batch", fromlist=["Batch"]).Batch,
            doc.batch_id,
        )
        cutoff_formula = batch.cutoff_formula if batch else "pcm_average"
        math_mode = batch.math_mode if batch else "combined"
        threshold = batch.eligibility_threshold if batch else 50.0

        cutoff = calculate_cutoff(mock_marks, cutoff_formula=cutoff_formula, math_mode=math_mode)
        eligibility = determine_eligibility(cutoff, threshold=threshold)

        # Update ExtractionResult
        er = doc.extraction_result
        if er:
            er.physics_percentage = cutoff.physics_percentage
            er.chemistry_percentage = cutoff.chemistry_percentage
            er.mathematics_percentage = cutoff.mathematics_percentage
            er.pcm_cutoff = cutoff.pcm_cutoff
            er.overall_percentage = cutoff.overall_percentage
            er.updated_at = datetime.utcnow()

        # Update EligibilityResult
        el = doc.eligibility_result
        if el:
            if payload.override_status:
                try:
                    el.status = EligibilityStatus(payload.override_status)
                    el.override_status = EligibilityStatus(payload.override_status)
                except ValueError:
                    pass
            else:
                el.status = EligibilityStatus(eligibility.status)
            el.physics_passed = eligibility.physics_passed
            el.chemistry_passed = eligibility.chemistry_passed
            el.mathematics_passed = eligibility.mathematics_passed
            el.overall_passed = eligibility.overall_passed
            el.rejection_reasons = eligibility.rejection_reasons
            el.review_reasons = eligibility.review_reasons
            el.is_manually_reviewed = True
            el.reviewed_by = payload.reviewer
            el.reviewed_at = datetime.utcnow()
            el.review_notes = payload.review_notes
            el.updated_at = datetime.utcnow()

        new_status = el.status if el else "REVIEW_REQUIRED"
        doc.status = new_status
        doc.requires_review = False
        doc.updated_at = datetime.utcnow()

    after_state = _serialize_review_state(doc)

    # Record review action
    action = ReviewAction(
        document_id=doc.id,
        action_type=ReviewActionType.MARK_CORRECTION,
        reviewer=payload.reviewer,
        before_state=before_state,
        after_state=after_state,
        notes=payload.review_notes,
    )
    db.add(action)

    # Audit log
    audit = AuditLog(
        entity_type="document",
        entity_id=str(doc.id),
        action="manual_review_submitted",
        actor=payload.reviewer,
        changes={"corrections": len(corrected_marks), "override": payload.override_status},
    )
    db.add(audit)

    final_status = doc.eligibility_result.status if doc.eligibility_result else "REVIEW_REQUIRED"

    return ReviewResponse(
        document_id=document_id,
        status="success",
        message=f"Review submitted. {len(corrected_marks)} mark(s) corrected.",
        recalculated_eligibility=str(final_status),
    )


@router.post("/{document_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Re-queue a document for reprocessing (e.g., after pipeline update)."""
    doc = await _get_document_or_404(document_id, db)

    batch = await db.get(
        __import__("app.models.batch", fromlist=["Batch"]).Batch,
        doc.batch_id,
    )

    doc.status = "QUEUED"
    doc.error_message = None
    doc.processed_at = None
    doc.updated_at = datetime.utcnow()

    task = process_document.apply_async(
        kwargs={
            "document_id": str(doc.id),
            "file_path": doc.file_path,
            "mime_type": doc.mime_type,
            "batch_id": str(doc.batch_id),
            "cutoff_formula": batch.cutoff_formula if batch else "pcm_average",
            "math_mode": batch.math_mode if batch else "combined",
            "eligibility_threshold": batch.eligibility_threshold if batch else 50.0,
        },
        queue="documents",
    )
    doc.celery_task_id = task.id

    return {"document_id": str(document_id), "task_id": task.id, "status": "requeued"}


def _serialize_extraction(er: Optional[ExtractionResult]) -> Optional[dict]:
    if not er:
        return None
    return {
        "physics_percentage": er.physics_percentage,
        "chemistry_percentage": er.chemistry_percentage,
        "mathematics_percentage": er.mathematics_percentage,
        "maths_a_percentage": er.maths_a_percentage,
        "maths_b_percentage": er.maths_b_percentage,
        "pcm_cutoff": er.pcm_cutoff,
        "overall_percentage": er.overall_percentage,
        "combined_confidence": er.combined_confidence,
        "has_missing_subjects": er.has_missing_subjects,
        "missing_subjects": er.missing_subjects,
        "validation_warnings": er.validation_warnings,
    }


def _serialize_eligibility(el: Optional[EligibilityResult]) -> Optional[dict]:
    if not el:
        return None
    return {
        "status": el.status,
        "physics_passed": el.physics_passed,
        "chemistry_passed": el.chemistry_passed,
        "mathematics_passed": el.mathematics_passed,
        "overall_passed": el.overall_passed,
        "rejection_reasons": el.rejection_reasons or [],
        "review_reasons": el.review_reasons or [],
        "is_manually_reviewed": el.is_manually_reviewed,
        "reviewed_by": el.reviewed_by,
        "review_notes": el.review_notes,
    }


def _serialize_review_state(doc: Document) -> dict:
    er = doc.extraction_result
    el = doc.eligibility_result
    return {
        "status": doc.status,
        "physics_pct": er.physics_percentage if er else None,
        "chemistry_pct": er.chemistry_percentage if er else None,
        "mathematics_pct": er.mathematics_percentage if er else None,
        "overall_pct": er.overall_percentage if er else None,
        "eligibility_status": str(el.status) if el else None,
    }
