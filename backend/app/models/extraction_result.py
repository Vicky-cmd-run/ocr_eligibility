"""
ExtractionResult — aggregated extraction results for a document.
"""
import uuid
from datetime import datetime
from sqlalchemy import Float, Boolean, DateTime, ForeignKey, Text, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ExtractionResult(Base):
    __tablename__ = "extraction_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # PCM percentages
    physics_percentage: Mapped[float] = mapped_column(Float, nullable=True)
    chemistry_percentage: Mapped[float] = mapped_column(Float, nullable=True)
    mathematics_percentage: Mapped[float] = mapped_column(Float, nullable=True)

    # Math breakdown
    maths_a_percentage: Mapped[float] = mapped_column(Float, nullable=True)
    maths_b_percentage: Mapped[float] = mapped_column(Float, nullable=True)
    math_mode_used: Mapped[str] = mapped_column(String(50), nullable=True)

    # Cutoff
    pcm_cutoff: Mapped[float] = mapped_column(Float, nullable=True)
    cutoff_formula_used: Mapped[str] = mapped_column(String(50), nullable=True)

    # Overall
    total_obtained: Mapped[float] = mapped_column(Float, nullable=True)
    total_maximum: Mapped[float] = mapped_column(Float, nullable=True)
    overall_percentage: Mapped[float] = mapped_column(Float, nullable=True)

    # Confidence
    combined_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    subject_match_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    structural_confidence: Mapped[float] = mapped_column(Float, nullable=True)

    # Flags
    has_missing_subjects: Mapped[bool] = mapped_column(Boolean, default=False)
    missing_subjects: Mapped[dict] = mapped_column(JSON, nullable=True)  # list of missing
    has_suspicious_values: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_warnings: Mapped[dict] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="extraction_result"
    )
