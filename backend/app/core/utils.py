"""Utility functions for ID generation, image validation, and mock data."""

import hashlib
import random
import uuid
from pathlib import Path

# Allowed image MIME types for CT scans
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/dicom",  # DICOM format
    "application/dicom",
}


def generate_case_id() -> str:
    """Generate a unique case identifier."""
    return str(uuid.uuid4())


def generate_nodule_id() -> str:
    """Generate a unique nodule identifier."""
    return str(uuid.uuid4())


def is_valid_image_type(content_type: str) -> bool:
    """Check if the content type is a valid medical image format."""
    return content_type.lower() in ALLOWED_IMAGE_TYPES


def get_seeded_random(case_id: str) -> random.Random:
    """Create a seeded random number generator based on case_id for deterministic mocks."""
    # Hash the case_id to get a consistent seed
    seed = int(hashlib.md5(case_id.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename."""
    return Path(filename).suffix.lower()

