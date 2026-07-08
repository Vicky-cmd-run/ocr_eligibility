"""Initial schema — all tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enums
    op.execute("CREATE TYPE batch_status AS ENUM ('PENDING','PROCESSING','COMPLETED','PARTIALLY_FAILED','FAILED')")
    op.execute("CREATE TYPE document_status AS ENUM ('QUEUED','PROCESSING','COMPLETED','ELIGIBLE','NOT_ELIGIBLE','REVIEW_REQUIRED','FAILED')")
    op.execute("CREATE TYPE document_type AS ENUM ('PDF_NATIVE','PDF_SCANNED','IMAGE','UNKNOWN')")
    op.execute("CREATE TYPE normalized_subject AS ENUM ('PHYSICS','CHEMISTRY','MATHEMATICS','MATHS_A','MATHS_B','OTHER','UNKNOWN')")
    op.execute("CREATE TYPE mark_type AS ENUM ('THEORY','PRACTICAL','TOTAL','UNKNOWN')")
    op.execute("CREATE TYPE eligibility_status AS ENUM ('ELIGIBLE','NOT_ELIGIBLE','REVIEW_REQUIRED','PENDING')")
    op.execute("CREATE TYPE review_action_type AS ENUM ('MARK_CORRECTION','STATUS_OVERRIDE','RECALCULATION','APPROVAL','REJECTION')")

    # batches
    op.create_table(
        "batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", postgresql.ENUM(name="batch_status", create_type=False), nullable=False, server_default="PENDING"),
        sa.Column("total_documents", sa.Integer, server_default="0"),
        sa.Column("queued_count", sa.Integer, server_default="0"),
        sa.Column("processing_count", sa.Integer, server_default="0"),
        sa.Column("completed_count", sa.Integer, server_default="0"),
        sa.Column("failed_count", sa.Integer, server_default="0"),
        sa.Column("eligible_count", sa.Integer, server_default="0"),
        sa.Column("not_eligible_count", sa.Integer, server_default="0"),
        sa.Column("review_required_count", sa.Integer, server_default="0"),
        sa.Column("cutoff_formula", sa.String(50), server_default="pcm_average"),
        sa.Column("math_mode", sa.String(50), server_default="combined"),
        sa.Column("eligibility_threshold", sa.Float, server_default="50.0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_batches_status", "batches", ["status"])

    # documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("stored_filename", sa.String(512), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("document_type", postgresql.ENUM(name="document_type", create_type=False), server_default="UNKNOWN"),
        sa.Column("page_count", sa.Integer, server_default="1"),
        sa.Column("status", postgresql.ENUM(name="document_status", create_type=False), server_default="QUEUED"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("overall_ocr_confidence", sa.Float, nullable=True),
        sa.Column("requires_review", sa.Boolean, server_default="false"),
        sa.Column("is_duplicate", sa.Boolean, server_default="false"),
        sa.Column("duplicate_of_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_batch_id", "documents", ["batch_id"])
    op.create_index("ix_documents_file_hash", "documents", ["file_hash"])
    op.create_index("ix_documents_status", "documents", ["status"])

    # candidates
    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), unique=True),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("register_number", sa.String(100), nullable=True),
        sa.Column("roll_number", sa.String(100), nullable=True),
        sa.Column("date_of_birth", sa.String(50), nullable=True),
        sa.Column("school_name", sa.String(512), nullable=True),
        sa.Column("exam_year", sa.String(20), nullable=True),
        sa.Column("board", sa.String(100), nullable=True),
        sa.Column("raw_text_name", sa.String(512), nullable=True),
        sa.Column("raw_text_register", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_candidates_document_id", "candidates", ["document_id"])
    op.create_index("ix_candidates_register_number", "candidates", ["register_number"])

    # subject_marks
    op.create_table(
        "subject_marks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE")),
        sa.Column("raw_subject_name", sa.String(255), nullable=False),
        sa.Column("normalized_subject", postgresql.ENUM(name="normalized_subject", create_type=False), server_default="UNKNOWN"),
        sa.Column("mark_type", postgresql.ENUM(name="mark_type", create_type=False), server_default="TOTAL"),
        sa.Column("obtained_marks", sa.Float, nullable=True),
        sa.Column("maximum_marks", sa.Float, nullable=True),
        sa.Column("percentage", sa.Float, nullable=True),
        sa.Column("subject_match_confidence", sa.Float, nullable=True),
        sa.Column("marks_ocr_confidence", sa.Float, nullable=True),
        sa.Column("raw_obtained_text", sa.String(50), nullable=True),
        sa.Column("raw_maximum_text", sa.String(50), nullable=True),
        sa.Column("is_suspicious", sa.Boolean, server_default="false"),
        sa.Column("is_manually_corrected", sa.Boolean, server_default="false"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_subject_marks_candidate_id", "subject_marks", ["candidate_id"])
    op.create_index("ix_subject_marks_normalized_subject", "subject_marks", ["normalized_subject"])

    # ocr_tokens
    op.create_table(
        "ocr_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("page_number", sa.Integer, server_default="1"),
        sa.Column("text", sa.String(1024), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("bounding_box", postgresql.JSONB, nullable=True),
        sa.Column("x_min", sa.Float, nullable=True),
        sa.Column("y_min", sa.Float, nullable=True),
        sa.Column("x_max", sa.Float, nullable=True),
        sa.Column("y_max", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ocr_tokens_document_id", "ocr_tokens", ["document_id"])

    # extraction_results
    op.create_table(
        "extraction_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), unique=True),
        sa.Column("physics_percentage", sa.Float, nullable=True),
        sa.Column("chemistry_percentage", sa.Float, nullable=True),
        sa.Column("mathematics_percentage", sa.Float, nullable=True),
        sa.Column("maths_a_percentage", sa.Float, nullable=True),
        sa.Column("maths_b_percentage", sa.Float, nullable=True),
        sa.Column("math_mode_used", sa.String(50), nullable=True),
        sa.Column("pcm_cutoff", sa.Float, nullable=True),
        sa.Column("cutoff_formula_used", sa.String(50), nullable=True),
        sa.Column("total_obtained", sa.Float, nullable=True),
        sa.Column("total_maximum", sa.Float, nullable=True),
        sa.Column("overall_percentage", sa.Float, nullable=True),
        sa.Column("combined_confidence", sa.Float, nullable=True),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("subject_match_confidence", sa.Float, nullable=True),
        sa.Column("structural_confidence", sa.Float, nullable=True),
        sa.Column("has_missing_subjects", sa.Boolean, server_default="false"),
        sa.Column("missing_subjects", postgresql.JSONB, nullable=True),
        sa.Column("has_suspicious_values", sa.Boolean, server_default="false"),
        sa.Column("validation_warnings", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_extraction_results_document_id", "extraction_results", ["document_id"])

    # eligibility_results
    op.create_table(
        "eligibility_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), unique=True),
        sa.Column("status", postgresql.ENUM(name="eligibility_status", create_type=False), server_default="PENDING"),
        sa.Column("physics_passed", sa.Boolean, nullable=True),
        sa.Column("chemistry_passed", sa.Boolean, nullable=True),
        sa.Column("mathematics_passed", sa.Boolean, nullable=True),
        sa.Column("overall_passed", sa.Boolean, nullable=True),
        sa.Column("eligibility_threshold", sa.Float, server_default="50.0"),
        sa.Column("rejection_reasons", postgresql.JSONB, nullable=True),
        sa.Column("review_reasons", postgresql.JSONB, nullable=True),
        sa.Column("is_manually_reviewed", sa.Boolean, server_default="false"),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text, nullable=True),
        sa.Column("override_status", postgresql.ENUM(name="eligibility_status", create_type=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_eligibility_results_document_id", "eligibility_results", ["document_id"])
    op.create_index("ix_eligibility_results_status", "eligibility_results", ["status"])

    # review_actions
    op.create_table(
        "review_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("action_type", postgresql.ENUM(name="review_action_type", create_type=False), nullable=False),
        sa.Column("reviewer", sa.String(255), nullable=True),
        sa.Column("before_state", postgresql.JSONB, nullable=True),
        sa.Column("after_state", postgresql.JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_review_actions_document_id", "review_actions", ["document_id"])

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column("changes", postgresql.JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("review_actions")
    op.drop_table("eligibility_results")
    op.drop_table("extraction_results")
    op.drop_table("ocr_tokens")
    op.drop_table("subject_marks")
    op.drop_table("candidates")
    op.drop_table("documents")
    op.drop_table("batches")
    op.execute("DROP TYPE IF EXISTS review_action_type")
    op.execute("DROP TYPE IF EXISTS eligibility_status")
    op.execute("DROP TYPE IF EXISTS mark_type")
    op.execute("DROP TYPE IF EXISTS normalized_subject")
    op.execute("DROP TYPE IF EXISTS document_type")
    op.execute("DROP TYPE IF EXISTS document_status")
    op.execute("DROP TYPE IF EXISTS batch_status")
