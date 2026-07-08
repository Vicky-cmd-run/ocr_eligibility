"""
ReviewAction model — tracks admin edits during manual review.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.database import Base


class ReviewActionType(str, enum.Enum):
    MARK_CORRECTION = "MARK_CORRECTION"
    STATUS_OVERRIDE = "STATUS_OVERRIDE"
    RECALCULATION = "RECALCULATION"
    APPROVAL = "APPROVAL"
    REJECTION = "REJECTION"


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )

    action_type: Mapped[ReviewActionType] = mapped_column(
        SAEnum(ReviewActionType, name="review_action_type")
    )
    reviewer: Mapped[str] = mapped_column(String(255), nullable=True)

    # Before/after JSON snapshots
    before_state: Mapped[dict] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    document: Mapped["Document"] = relationship(
        "Document", back_populates="review_actions"
    )
