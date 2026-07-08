"""
SubjectMark model — per-subject extracted marks.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.database import Base


class NormalizedSubject(str, enum.Enum):
    PHYSICS = "PHYSICS"
    CHEMISTRY = "CHEMISTRY"
    MATHEMATICS = "MATHEMATICS"
    MATHS_A = "MATHS_A"
    MATHS_B = "MATHS_B"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class MarkType(str, enum.Enum):
    THEORY = "THEORY"
    PRACTICAL = "PRACTICAL"
    TOTAL = "TOTAL"
    UNKNOWN = "UNKNOWN"


class SubjectMark(Base):
    __tablename__ = "subject_marks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        index=True,
    )

    raw_subject_name: Mapped[str] = mapped_column(String(255))
    normalized_subject: Mapped[NormalizedSubject] = mapped_column(
        SAEnum(NormalizedSubject, name="normalized_subject"),
        default=NormalizedSubject.UNKNOWN,
        index=True,
    )
    mark_type: Mapped[MarkType] = mapped_column(
        SAEnum(MarkType, name="mark_type"), default=MarkType.TOTAL
    )

    obtained_marks: Mapped[float] = mapped_column(Float, nullable=True)
    maximum_marks: Mapped[float] = mapped_column(Float, nullable=True)
    percentage: Mapped[float] = mapped_column(Float, nullable=True)

    # OCR provenance
    subject_match_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    marks_ocr_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    raw_obtained_text: Mapped[str] = mapped_column(String(50), nullable=True)
    raw_maximum_text: Mapped[str] = mapped_column(String(50), nullable=True)

    # Flags
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False)
    is_manually_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    candidate: Mapped["Candidate"] = relationship(
        "Candidate", back_populates="subject_marks"
    )
