"""
File ingestion module — validation, deduplication, storage.
"""
import hashlib
import mimetypes
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Tuple

from fastapi import UploadFile, HTTPException
from app.config import settings

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


class FileIngestionError(Exception):
    """Raised when file validation fails."""
    pass


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").lower()


def validate_file(file: UploadFile, content: bytes) -> None:
    """
    Validate uploaded file — extension, MIME type, size.
    Raises FileIngestionError with a descriptive message on failure.
    """
    ext = get_file_extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise FileIngestionError(
            f"File '{file.filename}' has unsupported extension '.{ext}'. "
            f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    if len(content) > settings.max_file_size_bytes:
        raise FileIngestionError(
            f"File '{file.filename}' exceeds maximum size of {settings.max_file_size_mb} MB. "
            f"Actual size: {len(content) / 1024 / 1024:.1f} MB"
        )

    if len(content) == 0:
        raise FileIngestionError(f"File '{file.filename}' is empty.")


def compute_sha256(content: bytes) -> str:
    """Compute SHA-256 hash of file bytes."""
    return hashlib.sha256(content).hexdigest()


def detect_mime_type(content: bytes, filename: str) -> str:
    """Detect MIME type from content and filename."""
    # Try from filename first
    mime, _ = mimetypes.guess_type(filename)
    if mime and mime in ALLOWED_MIME_TYPES:
        return mime

    # Detect from magic bytes
    if content[:4] == b"%PDF":
        return "application/pdf"
    if content[:2] in (b"\xff\xd8", b"\xff\xe0", b"\xff\xe1"):
        return "image/jpeg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"

    return mime or "application/octet-stream"


def store_file(
    content: bytes,
    original_filename: str,
    batch_id: uuid.UUID,
) -> Tuple[str, str, str]:
    """
    Save uploaded file to disk under uploads/<batch_id>/<unique_id>_<original_name>.
    Returns (stored_filename, absolute_file_path, file_hash).
    """
    file_hash = compute_sha256(content)
    batch_dir = Path(settings.upload_dir) / str(batch_id)
    batch_dir.mkdir(parents=True, exist_ok=True)

    ext = get_file_extension(original_filename)
    unique_id = uuid.uuid4().hex[:8]
    stored_filename = f"{unique_id}_{Path(original_filename).stem[:50]}.{ext}"
    file_path = batch_dir / stored_filename

    with open(file_path, "wb") as f:
        f.write(content)

    return stored_filename, str(file_path), file_hash


async def read_upload_content(file: UploadFile) -> bytes:
    """Async read of file content."""
    return await file.read()


def check_duplicate_in_batch(
    file_hash: str, existing_hashes: List[str]
) -> bool:
    """Return True if hash already exists in the current batch."""
    return file_hash in existing_hashes


def cleanup_batch_uploads(batch_id: uuid.UUID) -> None:
    """Remove all stored files for a batch (e.g., on failure)."""
    batch_dir = Path(settings.upload_dir) / str(batch_id)
    if batch_dir.exists():
        shutil.rmtree(batch_dir, ignore_errors=True)
