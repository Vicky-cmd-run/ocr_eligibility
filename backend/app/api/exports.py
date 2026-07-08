"""
Export API endpoints — CSV and Excel downloads.
"""
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import io

from app.database import get_db
from app.models.batch import Batch
from app.models.document import Document
from app.models.candidate import Candidate
from app.models.extraction_result import ExtractionResult
from app.models.eligibility_result import EligibilityResult
from app.core.export_generator import generate_csv, generate_excel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/batches", tags=["exports"])


async def _fetch_batch_results(
    batch_id: uuid.UUID,
    status_filter: Optional[str],
    db: AsyncSession,
) -> list:
    query = (
        select(Document)
        .where(Document.batch_id == batch_id)
        .options(
            selectinload(Document.candidate).selectinload(Candidate.subject_marks),
            selectinload(Document.extraction_result),
            selectinload(Document.eligibility_result),
        )
        .order_by(Document.created_at.asc())
    )
    if status_filter:
        query = query.where(Document.status == status_filter.upper())

    result = await db.execute(query)
    documents = result.scalars().all()

    rows = []
    for doc in documents:
        rows.append({
            "document": {
                "id": str(doc.id),
                "original_filename": doc.original_filename,
                "status": doc.status,
            },
            "candidate": {
                "name": doc.candidate.name if doc.candidate else None,
                "register_number": doc.candidate.register_number if doc.candidate else None,
            } if doc.candidate else {},
            "extraction_result": {
                "physics_percentage": doc.extraction_result.physics_percentage if doc.extraction_result else None,
                "chemistry_percentage": doc.extraction_result.chemistry_percentage if doc.extraction_result else None,
                "mathematics_percentage": doc.extraction_result.mathematics_percentage if doc.extraction_result else None,
                "pcm_cutoff": doc.extraction_result.pcm_cutoff if doc.extraction_result else None,
                "cutoff_formula_used": doc.extraction_result.cutoff_formula_used if doc.extraction_result else None,
                "overall_percentage": doc.extraction_result.overall_percentage if doc.extraction_result else None,
                "combined_confidence": doc.extraction_result.combined_confidence if doc.extraction_result else None,
            } if doc.extraction_result else {},
            "eligibility_result": {
                "status": str(doc.eligibility_result.status) if doc.eligibility_result else None,
                "physics_passed": doc.eligibility_result.physics_passed if doc.eligibility_result else None,
                "chemistry_passed": doc.eligibility_result.chemistry_passed if doc.eligibility_result else None,
                "mathematics_passed": doc.eligibility_result.mathematics_passed if doc.eligibility_result else None,
                "overall_passed": doc.eligibility_result.overall_passed if doc.eligibility_result else None,
                "rejection_reasons": doc.eligibility_result.rejection_reasons if doc.eligibility_result else [],
                "is_manually_reviewed": doc.eligibility_result.is_manually_reviewed if doc.eligibility_result else False,
                "review_notes": doc.eligibility_result.review_notes if doc.eligibility_result else None,
            } if doc.eligibility_result else {},
        })
    return rows


@router.get("/{batch_id}/export/csv")
async def export_csv(
    batch_id: uuid.UUID,
    status: Optional[str] = Query(None),
    approval_mode: str = Query("auto"),
    db: AsyncSession = Depends(get_db),
):
    """Export batch results as CSV."""
    batch = await db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    rows = await _fetch_batch_results(batch_id, status, db)
    csv_bytes = generate_csv(rows, approval_mode=approval_mode)

    filename = f"batch_{str(batch_id)[:8]}_results.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{batch_id}/export/xlsx")
async def export_xlsx(
    batch_id: uuid.UUID,
    status: Optional[str] = Query(None),
    approval_mode: str = Query("auto"),
    db: AsyncSession = Depends(get_db),
):
    """Export batch results as Excel (.xlsx)."""
    batch = await db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    rows = await _fetch_batch_results(batch_id, status, db)
    xlsx_bytes = generate_excel(rows, approval_mode=approval_mode)

    filename = f"batch_{str(batch_id)[:8]}_results.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
