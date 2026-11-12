"""Serves each case's slice."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.deps import get_storage
from app.services.storage import Storage

router = APIRouter()

MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


@router.get("/cases/{case_id}/image")
async def get_case_image(case_id: str, storage: Storage = Depends(get_storage)):
    """The case's slice, as uploaded."""
    path = storage.image_path(case_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"No image for case {case_id}")
    return FileResponse(
        path,
        media_type=MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
        headers={"Cache-Control": "no-cache"},
    )
