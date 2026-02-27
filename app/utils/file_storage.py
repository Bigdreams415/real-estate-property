"""
utils/file_storage.py

Handles saving uploaded image files to local disk.
Swap out `save_upload_file` internals later for S3 / Cloudinary / etc.
without touching any router code.
"""

import os
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException, status
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────
# Set MEDIA_ROOT env var in production to point to your persistent volume.
# Defaults to ./media/properties relative to where the app runs.

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "media"))
PROPERTY_IMAGES_DIR = MEDIA_ROOT / "properties"

# Base URL served by your FastAPI static files mount (or a CDN prefix)
# e.g. https://api.yourapp.com  →  https://api.yourapp.com/media/properties/abc.jpg
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024

# Map file extensions → canonical content type
_EXT_TO_CONTENT_TYPE = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _ensure_dirs():
    PROPERTY_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_content_type(file: UploadFile) -> tuple[str, str]:
    """
    Return (content_type, extension) for the uploaded file.

    iOS / some Android clients send 'application/octet-stream' instead of the
    real MIME type, so we fall back to inspecting the filename extension.
    Raises HTTPException if the type cannot be determined or is not allowed.
    """
    content_type = (file.content_type or "").lower()

    # If the client gave us a proper image MIME type, use it directly
    if content_type in ALLOWED_IMAGE_TYPES:
        return content_type, _CONTENT_TYPE_TO_EXT[content_type]

    # Fall back to file extension (handles octet-stream from iOS simulator)
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext in ALLOWED_EXTENSIONS:
        resolved_type = _EXT_TO_CONTENT_TYPE[ext]
        return resolved_type, ext if ext != ".jpeg" else ".jpg"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Cannot determine image type for '{filename}' "
            f"(content-type: '{content_type}'). "
            "Please upload a JPEG, PNG, or WebP image."
        ),
    )


async def save_property_image(file: UploadFile) -> str:
    """
    Validate, save an uploaded image file, and return its public URL.

    Raises HTTPException on invalid type or oversized file.
    Returns: full URL string, e.g. 'http://localhost:8000/media/properties/uuid.jpg'
    """
    _ensure_dirs()

    # ── Resolve content type (handles iOS octet-stream) ───────────────────────
    _content_type, ext = _resolve_content_type(file)

    # ── Read file bytes ───────────────────────────────────────────────────────
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image '{file.filename}' exceeds {MAX_IMAGE_SIZE_MB}MB limit.",
        )

    # ── Save to disk ──────────────────────────────────────────────────────────
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = PROPERTY_IMAGES_DIR / filename

    async with aiofiles.open(file_path, "wb") as out:
        await out.write(contents)

    # ── Return public URL ─────────────────────────────────────────────────────
    return f"{BASE_URL}/media/properties/{filename}"


async def save_property_images(files: list[UploadFile]) -> list[str]:
    """Save multiple images and return their URLs in order."""
    urls = []
    for f in files:
        url = await save_property_image(f)
        urls.append(url)
    return urls


def delete_property_image(image_url: str):
    """
    Delete an image file from disk given its full URL.
    Safe to call even if the file doesn't exist.
    """
    try:
        filename = image_url.split("/media/properties/")[-1]
        file_path = PROPERTY_IMAGES_DIR / filename
        if file_path.exists():
            file_path.unlink()
    except Exception:
        pass  # Non-fatal — log in production