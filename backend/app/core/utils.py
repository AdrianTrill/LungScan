"""Helpers for IDs and uploaded scans."""

import re
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

# The model reads 8-bit slices; PNG and JPEG are what the browser and PIL both decode.
ALLOWED_IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def generate_case_id() -> str:
    """Generate a unique case identifier."""
    return str(uuid.uuid4())


def generate_patient_id() -> str:
    """Generate a unique patient identifier."""
    return f"patient-{uuid.uuid4().hex[:8]}"


def is_valid_image_type(content_type: str) -> bool:
    """Check if the content type is an accepted scan format."""
    return content_type.lower() in ALLOWED_IMAGE_TYPES


def display_filename(name: str | None, extension: str) -> str:
    """A safe display name for an uploaded file."""
    stem = Path(name or "").stem
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._")[:96] or "scan"
    return f"{stem}{extension}"


def read_scan(scan: UploadFile) -> tuple[bytes, str, Image.Image]:
    """Read an uploaded scan: its bytes, file extension, and RGB image."""
    content_type = (scan.content_type or "").lower()
    if not is_valid_image_type(content_type):
        raise HTTPException(
            status_code=400, detail="Unsupported file type: upload a PNG or JPEG slice"
        )
    content = scan.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The file is larger than 25 MB")
    try:
        with Image.open(BytesIO(content)) as image:
            rgb = image.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(status_code=400, detail="The file is not a readable image") from error
    return content, ALLOWED_IMAGE_TYPES[content_type], rgb
