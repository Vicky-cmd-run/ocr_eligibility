"""
Celery document processing tasks.
Each document is processed independently with retries and exponential backoff.
"""
import logging
import uuid
from datetime import datetime

from celery import Task
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.celery_app import celery
from app.config import settings
from app.core.pipeline import run_pipeline

logger = logging.getLogger(__name__)

# Synchronous DB session for Celery workers
sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
SyncSession = sessionmaker(bind=sync_engine)


def get_sync_db() -> Session:
    return SyncSession()


class DocumentProcessingTask(Task):
    """Base task class with error handling."""
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        doc_id = kwargs.get("document_id") or (args[0] if args else None)
        if doc_id:
            _update_document_status(str(doc_id), "FAILED", error=str(exc))
        logger.error(f"Task {task_id} failed: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        doc_id = kwargs.get("document_id") or (args[0] if args else None)
        logger.warning(f"Retrying task {task_id} for document {doc_id}: {exc}")


def _update_document_status(document_id: str, status: str, error: str = None):
    """Update document status in the database (synchronous)."""
    from app.models.document import Document
    db = get_sync_db()
    try:
        doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
        if doc:
            doc.status = status
            doc.updated_at = datetime.utcnow()
            if error:
                doc.error_message = error[:2000]
            if status in ("COMPLETED", "ELIGIBLE", "NOT_ELIGIBLE", "REVIEW_REQUIRED", "FAILED"):
                doc.processed_at = datetime.utcnow()
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update document status: {e}")
        db.rollback()
    finally:
        db.close()


def _persist_pipeline_result(document_id: str, result: dict, batch_settings: dict):
    """Persist full pipeline result to database."""
    from app.models.document import Document
    from app.models.candidate import Candidate
    from app.models.subject_mark import SubjectMark, NormalizedSubject, MarkType
    from app.models.ocr_token import OcrToken as OcrTokenModel
    from app.models.extraction_result import ExtractionResult
    from app.models.eligibility_result import EligibilityResult, EligibilityStatus

    db = get_sync_db()
    try:
        doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
        if not doc:
            logger.error(f"Document {document_id} not found")
            return

        # Update document type
        doc.document_type = result.get("document_type", "UNKNOWN")
        doc.page_count = result.get("page_count", 1)

        extracted = result.get("extracted")
        validation = result.get("validation")
        cutoff = result.get("cutoff")
        eligibility = result.get("eligibility")
        confidence = result.get("confidence")
        error = result.get("error")

        if error:
            doc.status = "FAILED"
            doc.error_message = error[:2000]
            db.commit()
            return

        # Persist OCR tokens (limit to 500 per doc to avoid DB bloat)
        tokens = result.get("ocr_tokens", [])[:500]
        for token in tokens:
            token_model = OcrTokenModel(
                document_id=doc.id,
                page_number=token.page_number,
                text=token.text[:1024],
                confidence=token.confidence,
                bounding_box=token.bounding_box,
                x_min=token.x_min,
                y_min=token.y_min,
                x_max=token.x_max,
                y_max=token.y_max,
            )
            db.add(token_model)

        # Persist candidate
        if extracted:
            # Remove existing candidate if any (idempotent)
            existing_candidate = db.query(Candidate).filter(
                Candidate.document_id == doc.id
            ).first()
            if existing_candidate:
                db.delete(existing_candidate)
                db.flush()

            candidate = Candidate(
                document_id=doc.id,
                name=extracted.candidate_name,
                register_number=extracted.register_number,
                raw_text_name=extracted.raw_text_name,
                raw_text_register=extracted.raw_text_register,
            )
            db.add(candidate)
            db.flush()  # Get candidate.id

            # Persist subject marks
            for sm in extracted.subject_marks:
                try:
                    norm_subj = NormalizedSubject(sm.normalized_subject)
                except ValueError:
                    norm_subj = NormalizedSubject.OTHER

                subject_mark = SubjectMark(
                    candidate_id=candidate.id,
                    raw_subject_name=sm.raw_subject_name,
                    normalized_subject=norm_subj,
                    obtained_marks=sm.obtained_marks,
                    maximum_marks=sm.maximum_marks,
                    percentage=sm.percentage,
                    subject_match_confidence=sm.subject_match_confidence,
                    marks_ocr_confidence=sm.marks_ocr_confidence,
                    raw_obtained_text=sm.raw_obtained_text,
                    raw_maximum_text=sm.raw_maximum_text,
                    is_suspicious=sm.is_suspicious,
                    notes=sm.notes,
                )
                db.add(subject_mark)

        # Persist extraction result
        if cutoff and confidence:
            # Remove existing
            existing_er = db.query(ExtractionResult).filter(
                ExtractionResult.document_id == doc.id
            ).first()
            if existing_er:
                db.delete(existing_er)
                db.flush()

            validation_warnings = []
            if validation:
                validation_warnings = [
                    {"field": w.field, "message": w.message, "severity": w.severity}
                    for w in validation.warnings + validation.errors
                ]

            er = ExtractionResult(
                document_id=doc.id,
                physics_percentage=cutoff.physics_percentage,
                chemistry_percentage=cutoff.chemistry_percentage,
                mathematics_percentage=cutoff.mathematics_percentage,
                maths_a_percentage=cutoff.maths_a_percentage,
                maths_b_percentage=cutoff.maths_b_percentage,
                math_mode_used=cutoff.math_mode_used,
                pcm_cutoff=cutoff.pcm_cutoff,
                cutoff_formula_used=cutoff.cutoff_formula_used,
                total_obtained=cutoff.total_obtained,
                total_maximum=cutoff.total_maximum,
                overall_percentage=cutoff.overall_percentage,
                combined_confidence=confidence.combined_confidence,
                ocr_confidence=confidence.ocr_confidence,
                subject_match_confidence=confidence.subject_match_confidence,
                structural_confidence=confidence.structural_confidence,
                has_missing_subjects=bool(cutoff.missing_subjects),
                missing_subjects=cutoff.missing_subjects,
                has_suspicious_values=bool(
                    extracted and any(m.is_suspicious for m in extracted.subject_marks)
                ) if extracted else False,
                validation_warnings=validation_warnings,
            )
            db.add(er)

        # Persist eligibility result
        if eligibility:
            existing_el = db.query(EligibilityResult).filter(
                EligibilityResult.document_id == doc.id
            ).first()
            if existing_el:
                db.delete(existing_el)
                db.flush()

            try:
                el_status = EligibilityStatus(eligibility.status)
            except ValueError:
                el_status = EligibilityStatus.REVIEW_REQUIRED

            el = EligibilityResult(
                document_id=doc.id,
                status=el_status,
                physics_passed=eligibility.physics_passed,
                chemistry_passed=eligibility.chemistry_passed,
                mathematics_passed=eligibility.mathematics_passed,
                overall_passed=eligibility.overall_passed,
                eligibility_threshold=eligibility.eligibility_threshold,
                rejection_reasons=eligibility.rejection_reasons,
                review_reasons=eligibility.review_reasons,
            )
            db.add(el)

        # Update document final status and OCR confidence
        if confidence:
            doc.overall_ocr_confidence = confidence.combined_confidence

        if eligibility:
            if confidence and confidence.routing == "review":
                doc.status = "REVIEW_REQUIRED"
                doc.requires_review = True
            else:
                doc.status = eligibility.status
                doc.requires_review = eligibility.status == "REVIEW_REQUIRED"

        doc.processed_at = datetime.utcnow()
        db.commit()
        logger.info(f"Persisted results for document {document_id}")

    except Exception as e:
        logger.exception(f"Failed to persist results for {document_id}: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _update_batch_counts(batch_id: str):
    """Recompute batch progress counters from document statuses."""
    from app.models.batch import Batch, BatchStatus
    from app.models.document import Document, DocumentStatus
    from sqlalchemy import func

    db = get_sync_db()
    try:
        batch = db.query(Batch).filter(Batch.id == uuid.UUID(batch_id)).first()
        if not batch:
            return

        docs = db.query(Document).filter(Document.batch_id == uuid.UUID(batch_id)).all()

        statuses = [d.status for d in docs]
        batch.total_documents = len(docs)
        batch.queued_count = sum(1 for s in statuses if s == "QUEUED")
        batch.processing_count = sum(1 for s in statuses if s == "PROCESSING")
        batch.completed_count = sum(
            1 for s in statuses if s in ("COMPLETED", "ELIGIBLE", "NOT_ELIGIBLE", "REVIEW_REQUIRED")
        )
        batch.failed_count = sum(1 for s in statuses if s == "FAILED")
        batch.eligible_count = sum(1 for s in statuses if s == "ELIGIBLE")
        batch.not_eligible_count = sum(1 for s in statuses if s == "NOT_ELIGIBLE")
        batch.review_required_count = sum(1 for s in statuses if s == "REVIEW_REQUIRED")

        # Update batch status
        if batch.queued_count == 0 and batch.processing_count == 0:
            if batch.failed_count > 0 and batch.completed_count == 0:
                batch.status = BatchStatus.FAILED
            elif batch.failed_count > 0:
                batch.status = BatchStatus.PARTIALLY_FAILED
            else:
                batch.status = BatchStatus.COMPLETED
                batch.completed_at = datetime.utcnow()
        elif batch.processing_count > 0 or batch.completed_count > 0:
            batch.status = BatchStatus.PROCESSING

        batch.updated_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Failed to update batch counts: {e}")
        db.rollback()
    finally:
        db.close()


@celery.task(
    bind=True,
    base=DocumentProcessingTask,
    name="app.tasks.document_tasks.process_document",
    queue="documents",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def process_document(
    self,
    document_id: str,
    file_path: str,
    mime_type: str,
    batch_id: str,
    cutoff_formula: str = "pcm_average",
    math_mode: str = "combined",
    eligibility_threshold: float = 50.0,
):
    """
    Celery task: process a single marksheet document through the full OCR pipeline.
    Includes retry with exponential backoff on failure.
    """
    logger.info(f"Processing document {document_id} (batch {batch_id})")

    # Mark as PROCESSING
    _update_document_status(document_id, "PROCESSING")

    try:
        result = run_pipeline(
            file_path=file_path,
            mime_type=mime_type,
            cutoff_formula=cutoff_formula,
            math_mode=math_mode,
            eligibility_threshold=eligibility_threshold,
        )

        _persist_pipeline_result(
            document_id=document_id,
            result=result,
            batch_settings={
                "cutoff_formula": cutoff_formula,
                "math_mode": math_mode,
                "eligibility_threshold": eligibility_threshold,
            },
        )

        _update_batch_counts(batch_id)

        return {
            "status": "success",
            "document_id": document_id,
        }

    except Exception as exc:
        logger.error(f"Document {document_id} processing failed: {exc}")
        # Exponential backoff: 60s, 120s, 240s
        countdown = 60 * (2 ** self.request.retries)
        try:
            raise self.retry(exc=exc, countdown=countdown)
        except self.MaxRetriesExceededError:
            _update_document_status(document_id, "FAILED", error=str(exc))
            _update_batch_counts(batch_id)
            return {"status": "failed", "document_id": document_id, "error": str(exc)}
