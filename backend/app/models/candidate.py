"""
Candidate model — extracted candidate information from a marksheet.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(512), nullable=True)
    register_number: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    roll_number: Mapped[str] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[str] = mapped_column(String(50), nullable=True)
    school_name: Mapped[str] = mapped_column(String(512), nullable=True)
    exam_year: Mapped[str] = mapped_column(String(20), nullable=True)
    board: Mapped[str] = mapped_column(String(100), nullable=True)

    raw_text_name: Mapped[str] = mapped_column(String(512), nullable=True)
    raw_text_register: Mapped[str] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    document: Mapped["Document"] = relationship("Document", back_populates="candidate")
    subject_marks: Mapped[list["SubjectMark"]] = relationship(
        "SubjectMark", back_populates="candidate", cascade="all, delete-orphan"
    )
