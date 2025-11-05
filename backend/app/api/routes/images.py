"""Image serving endpoint for CT scan images."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
import requests
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()

# Path to static images directory
STATIC_IMAGES_DIR = Path(__file__).parent.parent.parent.parent / "static" / "images"
LOCAL_CT_SCAN_JPG = STATIC_IMAGES_DIR / "ct_scan_sample.jpg"
LOCAL_CT_SCAN_PNG = STATIC_IMAGES_DIR / "ct_scan_sample.png"

# Sample CT scan image URLs for demo purposes
# Using publicly available medical imaging samples
# These are actual CT scan images (grayscale medical imaging)

# Primary: Direct link to CT scan image (no thumbnails to avoid pink/colored versions)
SAMPLE_CT_SCAN_URL = "https://upload.wikimedia.org/wikipedia/commons/8/8d/CT_scan_of_lungs.jpg"

# Alternative 1: Another CT scan image (direct link)
ALTERNATIVE_CT_SCAN_URL_1 = "https://upload.wikimedia.org/wikipedia/commons/e/e8/CT_chest_axial.png"

# Alternative 2: CT scan from medical imaging (direct link)
ALTERNATIVE_CT_SCAN_URL_2 = "https://upload.wikimedia.org/wikipedia/commons/a/a0/Chest_CT_scan.jpg"


@router.get("/cases/{case_id}/image")
async def get_case_image(case_id: str):
    """Get the CT scan image for a case.
    
    For demo purposes, returns a sample CT scan image for Emily Brown's case.
    In production, this would fetch the actual uploaded image from storage.
    """
    # For Emily Brown's case (case-004), return a sample CT scan
    if case_id == "case-004":
        # First, try to serve local file if it exists (try PNG first, then JPG)
        for local_file, media_type in [(LOCAL_CT_SCAN_PNG, "image/png"), (LOCAL_CT_SCAN_JPG, "image/jpeg")]:
            if local_file.exists() and local_file.stat().st_size > 10000:  # Check file exists and is reasonable size (>10KB)
                try:
                    logger.info(f"Serving local CT scan image: {local_file}")
                    return FileResponse(
                        local_file,
                        media_type=media_type,
                        headers={
                            "Cache-Control": "public, max-age=3600",
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Allow-Methods": "GET, OPTIONS",
                            "Access-Control-Allow-Headers": "*",
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to serve local file {local_file}: {str(e)}")
        
        # Fallback: Try multiple online image sources
        image_urls = [
            SAMPLE_CT_SCAN_URL,
            ALTERNATIVE_CT_SCAN_URL_1,
            ALTERNATIVE_CT_SCAN_URL_2,
        ]
        
        for img_url in image_urls:
            try:
                # Fetch the sample image and proxy it
                logger.info(f"Attempting to fetch image from: {img_url}")
                response = requests.get(img_url, timeout=15, stream=True)
                response.raise_for_status()
                
                # Read the image content
                image_content = response.content
                
                # Check if we got a valid image (not too small, likely an error page)
                if len(image_content) > 5000:  # Ensure it's a real image, not an error page
                    logger.info(f"Successfully fetched image, size: {len(image_content)} bytes")
                    return Response(
                        content=image_content,
                        media_type=response.headers.get("Content-Type", "image/jpeg"),
                        headers={
                            "Cache-Control": "public, max-age=3600",
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Allow-Methods": "GET, OPTIONS",
                            "Access-Control-Allow-Headers": "*",
                        }
                    )
                else:
                    logger.warning(f"Image too small, likely not valid: {len(image_content)} bytes")
            except Exception as e:
                logger.warning(f"Failed to fetch from {img_url}: {str(e)}")
                continue
        
        # If all sources fail, return error
        logger.error("All image sources failed")
        raise HTTPException(status_code=500, detail="Failed to load CT scan image")
    
    # For other cases, you could implement logic to fetch actual uploaded images
    # For now, return 404 for other cases
    raise HTTPException(status_code=404, detail="Image not found for this case")

