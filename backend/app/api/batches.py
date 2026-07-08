"""
Batch API endpoints.
"""
import uuid
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.schemas import (
    BatchCreate, BatchResponse, BatchProgress,
    BatchUploadResponse, UploadFileResult,
)
from app.models.batch import Batch, BatchStatus
from app.models.document import Document, DocumentStatus
from app.core.ingestion import (
    validate_file, store_file, read_upload_content,
    detect_mime_type, compute_sha256, FileIngestionError,
)
from app.tasks.document_tasks import process_document
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/batches", tags=["batches"])


@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(payload: BatchCreate, db: AsyncSession = Depends(get_db)):
    """Create a new batch."""
    batch = Batch(
        name=payload.name,
        cutoff_formula=payload.cutoff_formula,
        math_mode=payload.math_mode,
        eligibility_threshold=payload.eligibility_threshold,
        notes=payload.notes,
    )
    db.add(batch)
    await db.flush()
    return batch


@router.post("/{batch_id}/upload", response_model=BatchUploadResponse)
async def upload_files(
    batch_id: uuid.UUID,
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload 1–1000 files to an existing batch.
    Each file is validated, stored, and queued as an async Celery task.
    """
    batch = await db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if batch.status not in (BatchStatus.PENDING, BatchStatus.PROCESSING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot upload to batch with status '{batch.status}'"
        )

    if len(files) > settings.max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum per batch: {settings.max_batch_size}"
        )

    # Collect existing hashes in this batch for deduplication
    result = await db.execute(
        select(Document.file_hash).where(Document.batch_id == batch_id)
    )
    existing_hashes = {row[0] for row in result.fetchall()}

    results: List[UploadFileResult] = []
    queued = 0
    duplicates = 0
    errors = 0

    for file in files:
        try:
            content = await read_upload_content(file)
            validate_file(file, content)

            file_hash = compute_sha256(content)
            mime_type = detect_mime_type(content, file.filename or "")

            # Duplicate detection within batch
            if file_hash in existing_hashes:
                duplicates += 1
                results.append(UploadFileResult(
                    filename=file.filename or "",
                    document_id=None,
                    status="duplicate",
                    message="File already exists in this batch",
                ))
                continue

            # Store file
            stored_filename, file_path, _ = store_file(content, file.filename or "", batch_id)
            existing_hashes.add(file_hash)

            # Create Document record
            doc = Document(
                batch_id=batch_id,
                original_filename=file.filename or stored_filename,
                stored_filename=stored_filename,
                file_path=file_path,
                file_size_bytes=len(content),
                file_hash=file_hash,
                mime_type=mime_type,
                status=DocumentStatus.QUEUED,
            )
            db.add(doc)
            await db.flush()

            # Queue Celery task
            task = process_document.apply_async(
                kwargs={
                    "document_id": str(doc.id),
                    "file_path": file_path,
                    "mime_type": mime_type,
                    "batch_id": str(batch_id),
                    "cutoff_formula": batch.cutoff_formula,
                    "math_mode": batch.math_mode,
                    "eligibility_threshold": batch.eligibility_threshold,
                },
                queue="documents",
            )
            doc.celery_task_id = task.id

            queued += 1
            results.append(UploadFileResult(
                filename=file.filename or "",
                document_id=doc.id,
                status="queued",
                message=None,
            ))

        except FileIngestionError as e:
            errors += 1
            results.append(UploadFileResult(
                filename=file.filename or "",
                document_id=None,
                status="error",
                message=str(e),
            ))
        except Exception as e:
            logger.exception(f"Unexpected error uploading {file.filename}: {e}")
            errors += 1
            results.append(UploadFileResult(
                filename=file.filename or "",
                document_id=None,
                status="error",
                message=f"Internal error: {str(e)}",
            ))

    # Update batch counters
    batch.total_documents = (batch.total_documents or 0) + queued
    batch.queued_count = (batch.queued_count or 0) + queued
    if batch.status == BatchStatus.PENDING and queued > 0:
        batch.status = BatchStatus.PROCESSING
    batch.updated_at = datetime.utcnow()

    return BatchUploadResponse(
        batch_id=batch_id,
        total_uploaded=len(files),
        queued=queued,
        duplicates=duplicates,
        errors=errors,
        results=results,
    )


@router.get("", response_model=List[BatchResponse])
async def list_batches(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all batches, newest first."""
    result = await db.execute(
        select(Batch).order_by(Batch.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single batch by ID."""
    batch = await db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.get("/{batch_id}/progress", response_model=BatchProgress)
async def get_batch_progress(batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get real-time processing progress for a batch."""
    batch = await db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    total = batch.total_documents or 0
    completed = batch.completed_count or 0
    progress = (completed / total * 100) if total > 0 else 0.0

    return BatchProgress(
        batch_id=batch_id,
        status=batch.status,
        total=total,
        queued=batch.queued_count or 0,
        processing=batch.processing_count or 0,
        completed=completed,
        failed=batch.failed_count or 0,
        eligible=batch.eligible_count or 0,
        not_eligible=batch.not_eligible_count or 0,
        review_required=batch.review_required_count or 0,
        progress_percent=round(progress, 1),
    )


@router.get("/{batch_id}/results")
async def get_batch_results(
    batch_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated document results for a batch."""
    from sqlalchemy.orm import selectinload
    from app.models.candidate import Candidate
    from app.models.extraction_result import ExtractionResult
    from app.models.eligibility_result import EligibilityResult

    batch = await db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    query = (
        select(Document)
        .where(Document.batch_id == batch_id)
        .options(
            selectinload(Document.candidate).selectinload(Candidate.subject_marks),
            selectinload(Document.extraction_result),
            selectinload(Document.eligibility_result),
        )
    )

    if status_filter:
        query = query.where(Document.status == status_filter.upper())

    query = query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    documents = result.scalars().all()

    # Count total for pagination
    count_query = select(func.count()).where(Document.batch_id == batch_id)
    if status_filter:
        count_query = count_query.where(Document.status == status_filter.upper())
    count_result = await db.execute(count_query)
    total_count = count_result.scalar()

    return {
        "batch_id": str(batch_id),
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "documents": [_serialize_document(d) for d in documents],
    }


def _serialize_document(doc: Document) -> dict:
    candidate = doc.candidate
    er = doc.extraction_result
    el = doc.eligibility_result

    return {
        "id": str(doc.id),
        "original_filename": doc.original_filename,
        "status": doc.status,
        "document_type": doc.document_type,
        "page_count": doc.page_count,
        "overall_ocr_confidence": doc.overall_ocr_confidence,
        "requires_review": doc.requires_review,
        "is_duplicate": doc.is_duplicate,
        "error_message": doc.error_message,
        "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "candidate": {
            "name": candidate.name if candidate else None,
            "register_number": candidate.register_number if candidate else None,
        } if candidate else None,
        "extraction": {
            "physics_percentage": er.physics_percentage if er else None,
            "chemistry_percentage": er.chemistry_percentage if er else None,
            "mathematics_percentage": er.mathematics_percentage if er else None,
            "pcm_cutoff": er.pcm_cutoff if er else None,
            "overall_percentage": er.overall_percentage if er else None,
            "combined_confidence": er.combined_confidence if er else None,
            "cutoff_formula_used": er.cutoff_formula_used if er else None,
        } if er else None,
        "eligibility": {
            "status": el.status if el else None,
            "physics_passed": el.physics_passed if el else None,
            "chemistry_passed": el.chemistry_passed if el else None,
            "mathematics_passed": el.mathematics_passed if el else None,
            "overall_passed": el.overall_passed if el else None,
            "rejection_reasons": el.rejection_reasons if el else [],
            "is_manually_reviewed": el.is_manually_reviewed if el else False,
        } if el else None,
    }
