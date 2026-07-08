"""
EligibilityResult — final eligibility determination per document.
"""
import uuid
from datetime import datetime
from sqlalchemy import Float, DateTime, ForeignKey, Text, String, JSON, Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.database import Base


class EligibilityStatus(str, enum.Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    PENDING = "PENDING"


class EligibilityResult(Base):
    __tablename__ = "eligibility_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    status: Mapped[EligibilityStatus] = mapped_column(
        SAEnum(EligibilityStatus, name="eligibility_status"),
        default=EligibilityStatus.PENDING,
        index=True,
    )

    physics_passed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    chemistry_passed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    mathematics_passed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    overall_passed: Mapped[bool] = mapped_column(Boolean, nullable=True)

    eligibility_threshold: Mapped[float] = mapped_column(Float, default=50.0)

    rejection_reasons: Mapped[dict] = mapped_column(JSON, nullable=True)  # list of strings
    review_reasons: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Manual review
    is_manually_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[str] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str] = mapped_column(Text, nullable=True)
    override_status: Mapped[EligibilityStatus] = mapped_column(
        SAEnum(EligibilityStatus, name="eligibility_status", create_constraint=False),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="eligibility_result"
    )
