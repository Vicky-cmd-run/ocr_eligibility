"""
Document model — represents a single uploaded marksheet file.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.database import Base


class DocumentStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


class DocumentType(str, enum.Enum):
    PDF_NATIVE = "PDF_NATIVE"
    PDF_SCANNED = "PDF_SCANNED"
    IMAGE = "IMAGE"
    UNKNOWN = "UNKNOWN"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id", ondelete="CASCADE"), index=True
    )

    # File metadata
    original_filename: Mapped[str] = mapped_column(String(512))
    stored_filename: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(Text)
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    file_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256
    mime_type: Mapped[str] = mapped_column(String(100))
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type"), default=DocumentType.UNKNOWN
    )
    page_count: Mapped[int] = mapped_column(Integer, default=1)

    # Processing
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.QUEUED,
        index=True,
    )
    celery_task_id: Mapped[str] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # OCR quality
    overall_ocr_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    batch: Mapped["Batch"] = relationship("Batch", back_populates="documents")
    candidate: Mapped["Candidate"] = relationship(
        "Candidate", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    ocr_tokens: Mapped[list["OcrToken"]] = relationship(
        "OcrToken", back_populates="document", cascade="all, delete-orphan"
    )
    extraction_result: Mapped["ExtractionResult"] = relationship(
        "ExtractionResult", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    eligibility_result: Mapped["EligibilityResult"] = relationship(
        "EligibilityResult", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    review_actions: Mapped[list["ReviewAction"]] = relationship(
        "ReviewAction", back_populates="document", cascade="all, delete-orphan"
    )
