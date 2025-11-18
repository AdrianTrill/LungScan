"""Image preprocessing utilities for CT scan images."""

import logging
from io import BytesIO
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image
import torch
from torchvision import transforms

logger = logging.getLogger(__name__)


def load_image_from_bytes(image_bytes: bytes) -> Image.Image:
    """Load an image from bytes.
    
    Args:
        image_bytes: Image file as bytes
        
    Returns:
        PIL Image object
    """
    try:
        image = Image.open(BytesIO(image_bytes))
        # Convert to RGB if necessary (handles grayscale, RGBA, etc.)
        if image.mode != "RGB":
            image = image.convert("RGB")
        return image
    except Exception as e:
        logger.error(f"Failed to load image from bytes: {str(e)}")
        raise ValueError(f"Invalid image data: {str(e)}")


def load_image_from_path(image_path: Path) -> Image.Image:
    """Load an image from file path.
    
    Args:
        image_path: Path to image file
        
    Returns:
        PIL Image object
    """
    try:
        image = Image.open(image_path)
        if image.mode != "RGB":
            image = image.convert("RGB")
        return image
    except Exception as e:
        logger.error(f"Failed to load image from path {image_path}: {str(e)}")
        raise ValueError(f"Failed to load image: {str(e)}")


def preprocess_image(
    image: Image.Image,
    size: Tuple[int, int] = (224, 224),
    mean: list = [0.485, 0.485, 0.485],
    std: list = [0.229, 0.229, 0.229],
) -> torch.Tensor:
    """Preprocess image for model inference.
    
    Args:
        image: PIL Image object
        size: Target size (width, height)
        mean: Normalization mean values
        std: Normalization std values
        
    Returns:
        Preprocessed tensor ready for model input
    """
    transform = transforms.Compose([
        transforms.Resize(size),
        transforms.ToTensor(),
        transforms.Normalize(mean=mean, std=std),
    ])
    
    tensor = transform(image)
    # Add batch dimension
    tensor = tensor.unsqueeze(0)
    return tensor


def extract_patches(
    image: Image.Image,
    patch_size: Tuple[int, int] = (224, 224),
    stride: int = 112,
) -> list[Tuple[Image.Image, Tuple[int, int]]]:
    """Extract patches from an image for sliding window analysis.
    
    Args:
        image: PIL Image object
        patch_size: Size of each patch (width, height)
        stride: Stride for sliding window
        
    Returns:
        List of (patch_image, (x, y)) tuples where (x, y) is the top-left corner
    """
    patches = []
    img_width, img_height = image.size
    patch_width, patch_height = patch_size
    
    for y in range(0, img_height - patch_height + 1, stride):
        for x in range(0, img_width - patch_width + 1, stride):
            patch = image.crop((x, y, x + patch_width, y + patch_height))
            patches.append((patch, (x, y)))
    
    # Also extract patches from edges
    # Right edge
    for y in range(0, img_height - patch_height + 1, stride):
        x = img_width - patch_width
        patch = image.crop((x, y, x + patch_width, y + patch_height))
        patches.append((patch, (x, y)))
    
    # Bottom edge
    for x in range(0, img_width - patch_width + 1, stride):
        y = img_height - patch_height
        patch = image.crop((x, y, x + patch_width, y + patch_height))
        patches.append((patch, (x, y)))
    
    # Bottom-right corner
    if img_width >= patch_width and img_height >= patch_height:
        x = img_width - patch_width
        y = img_height - patch_height
        patch = image.crop((x, y, x + patch_width, y + patch_height))
        patches.append((patch, (x, y)))
    
    return patches


def get_image_dimensions(image: Image.Image) -> Tuple[int, int]:
    """Get image dimensions.
    
    Args:
        image: PIL Image object
        
    Returns:
        (width, height) tuple
    """
    return image.size

