"""
OcrToken model — individual OCR token with bounding box + confidence.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class OcrToken(Base):
    __tablename__ = "ocr_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )

    page_number: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(String(1024))
    confidence: Mapped[float] = mapped_column(Float)

    # Bounding box as [x1,y1,x2,y1,x2,y2,x1,y2] (polygon)
    bounding_box: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Simplified bbox
    x_min: Mapped[float] = mapped_column(Float, nullable=True)
    y_min: Mapped[float] = mapped_column(Float, nullable=True)
    x_max: Mapped[float] = mapped_column(Float, nullable=True)
    y_max: Mapped[float] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    document: Mapped["Document"] = relationship("Document", back_populates="ocr_tokens")
