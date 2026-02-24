"""Real AI analysis service using the lung cancer detection model."""

import logging
from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F

from app.core.schemas import AnalyzeResult, Nodule
from app.core.utils import generate_nodule_id
from app.services.image_processor import (
    load_image_from_bytes,
    load_image_from_path,
    preprocess_image,
    extract_patches,
    get_image_dimensions,
)
from app.services.model_loader import (
    get_model_loader,
    CLASS_LABELS,
    IMAGE_SIZE,
    MEAN,
    STD,
)

logger = logging.getLogger(__name__)


def analyze_image(
    image_path: Optional[Path] = None,
    image_bytes: Optional[bytes] = None,
    case_id: str = "unknown",
    use_sliding_window: bool = True,
) -> AnalyzeResult:
    """Run AI analysis on a CT scan image.
    
    Args:
        image_path: Path to image file (if available)
        image_bytes: Image as bytes (if available)
        case_id: Case identifier
        use_sliding_window: If True, use sliding window for nodule detection
        
    Returns:
        AnalyzeResult with detected nodules and summary
    """
    try:
        # Load image
        if image_path and Path(image_path).exists():
            image = load_image_from_path(Path(image_path))
        elif image_bytes:
            image = load_image_from_bytes(image_bytes)
        else:
            raise ValueError("Either image_path or image_bytes must be provided")
        
        img_width, img_height = get_image_dimensions(image)
        logger.info(f"Analyzing image: {img_width}x{img_height} pixels")
        
        # Load model
        model_loader = get_model_loader()
        model = model_loader.load_model()
        device = model_loader.get_device()
        
        nodules = []
        
        if use_sliding_window and (img_width > IMAGE_SIZE or img_height > IMAGE_SIZE):
            # Use sliding window approach for large images
            logger.info("Using sliding window approach for nodule detection")
            nodules = _analyze_with_sliding_window(
                image, model, device, img_width, img_height
            )
        else:
            # Analyze entire image
            logger.info("Analyzing entire image")
            nodules = _analyze_full_image(
                image, model, device, img_width, img_height
            )
        
        # Generate summary
        if nodules:
            avg_score = sum(n.malignancy_score for n in nodules) / len(nodules)
            high_risk_count = sum(1 for n in nodules if n.malignancy_score >= 0.6)
            cancer_count = sum(1 for n in nodules if n.malignancy_score >= 0.5)
            
            summary = (
                f"Analysis complete: {len(nodules)} suspicious region(s) detected. "
                f"Average malignancy score: {avg_score:.3f}. "
                f"{high_risk_count} region(s) with high suspicion (≥0.6). "
                f"{cancer_count} region(s) showing potential cancer indicators (≥0.5). "
                "Review recommended for all detected regions."
            )
        else:
            summary = (
                "Analysis complete: No suspicious regions detected. "
                "Image appears normal. Regular follow-up recommended."
            )
        
        return AnalyzeResult(case_id=case_id, nodules=nodules, summary=summary)
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        # Return a safe result indicating analysis failure
        return AnalyzeResult(
            case_id=case_id,
            nodules=[],
            summary=f"Analysis encountered an error: {str(e)}. Please try again or contact support.",
        )


def _analyze_full_image(
    image,
    model: torch.nn.Module,
    device: torch.device,
    img_width: int,
    img_height: int,
) -> list[Nodule]:
    """Analyze the entire image as a single patch.
    
    Args:
        image: PIL Image object
        model: Loaded PyTorch model
        device: Device to run inference on
        img_width: Original image width
        img_height: Original image height
        
    Returns:
        List of detected nodules
    """
    # Preprocess image
    tensor = preprocess_image(image, size=(IMAGE_SIZE, IMAGE_SIZE), mean=MEAN, std=STD)
    tensor = tensor.to(device)
    
    # Run inference
    with torch.no_grad():
        outputs = model(tensor)
        probabilities = F.softmax(outputs, dim=1)
        probs = probabilities[0].cpu().numpy()
    
    # Get predictions
    predicted_class = int(torch.argmax(probabilities, dim=1).item())
    confidence = float(probs[predicted_class])
    class_name = CLASS_LABELS[predicted_class]
    
    logger.info(f"Prediction: {class_name} (confidence: {confidence:.3f})")
    
    nodules = []
    
    # Convert classification result to nodule detection
    # If the model predicts cancer (not "Normal"), create a nodule
    if class_name != "Normal" and confidence > 0.3:
        # Calculate malignancy score based on class and confidence
        malignancy_score = _calculate_malignancy_score(class_name, confidence)
        
        # Place nodule in center of image
        x = img_width // 2
        y = img_height // 2
        radius = min(img_width, img_height) // 10  # Adaptive radius
        
        explanation = (
            f"AI detected {class_name.lower()} with {confidence:.1%} confidence. "
            f"Region shows characteristics consistent with {class_name.lower()}. "
            f"Clinical correlation recommended."
        )
        
        nodule = Nodule(
            id=generate_nodule_id(),
            x=x,
            y=y,
            radius=radius,
            malignancy_score=malignancy_score,
            explanation=explanation,
        )
        nodules.append(nodule)
    
    return nodules


def _analyze_with_sliding_window(
    image,
    model: torch.nn.Module,
    device: torch.device,
    img_width: int,
    img_height: int,
) -> list[Nodule]:
    """Analyze image using sliding window approach.
    
    Args:
        image: PIL Image object
        model: Loaded PyTorch model
        device: Device to run inference on
        img_width: Original image width
        img_height: Original image height
        
    Returns:
        List of detected nodules
    """
    # Extract patches with less overlap for more precise detection
    patches = extract_patches(
        image,
        patch_size=(IMAGE_SIZE, IMAGE_SIZE),
        stride=IMAGE_SIZE * 3 // 4,  # 25% overlap (reduced from 50%)
    )
    
    logger.info(f"Analyzing {len(patches)} patches")
    
    nodules = []
    threshold = 0.5  # Higher threshold to reduce false positives
    
    # Process patches in batches for efficiency
    batch_size = 8
    for i in range(0, len(patches), batch_size):
        batch_patches = patches[i : i + batch_size]
        batch_tensors = []
        patch_positions = []
        
        for patch, (x, y) in batch_patches:
            tensor = preprocess_image(
                patch, size=(IMAGE_SIZE, IMAGE_SIZE), mean=MEAN, std=STD
            )
            batch_tensors.append(tensor)
            patch_positions.append((x, y))
        
        # Stack into batch
        batch = torch.cat(batch_tensors, dim=0).to(device)
        
        # Run inference
        with torch.no_grad():
            outputs = model(batch)
            probabilities = F.softmax(outputs, dim=1)
        
        # Process results
        for j, (x, y) in enumerate(patch_positions):
            probs = probabilities[j].cpu().numpy()
            predicted_class = int(torch.argmax(probabilities[j]).item())
            confidence = float(probs[predicted_class])
            class_name = CLASS_LABELS[predicted_class]
            
            # Only create nodule if not "Normal" and confidence is above threshold
            if class_name != "Normal" and confidence > threshold:
                malignancy_score = _calculate_malignancy_score(class_name, confidence)
                
                # Center of patch in original image coordinates
                center_x = x + IMAGE_SIZE // 2
                center_y = y + IMAGE_SIZE // 2
                radius = IMAGE_SIZE // 4  # Radius based on patch size
                
                explanation = (
                    f"AI detected {class_name.lower()} in this region "
                    f"with {confidence:.1%} confidence. "
                    f"Clinical correlation recommended."
                )
                
                nodule = Nodule(
                    id=generate_nodule_id(),
                    x=center_x,
                    y=center_y,
                    radius=radius,
                    malignancy_score=malignancy_score,
                    explanation=explanation,
                )
                nodules.append(nodule)
    
    # Remove overlapping nodules (keep the one with highest score)
    nodules = _remove_overlapping_nodules(nodules)
    
    logger.info(f"Detected {len(nodules)} suspicious regions")
    return nodules


def _calculate_malignancy_score(class_name: str, confidence: float) -> float:
    """Calculate malignancy score based on class and confidence.
    
    Args:
        class_name: Predicted class name
        confidence: Model confidence (0-1)
        
    Returns:
        Malignancy score (0-1)
    """
    # Base scores for different cancer types
    base_scores = {
        "Normal": 0.0,
        "Adenocarcinoma": 0.7,
        "Large Cell Carcinoma": 0.75,
        "Squamous Cell Carcinoma": 0.8,
    }
    
    base_score = base_scores.get(class_name, 0.5)
    
    # Adjust based on confidence
    # Higher confidence -> higher malignancy score
    score = base_score * (0.5 + 0.5 * confidence)
    
    # Clamp to [0, 1]
    return min(1.0, max(0.0, score))


def _remove_overlapping_nodules(nodules: list[Nodule], overlap_threshold: float = 0.3) -> list[Nodule]:
    """Remove overlapping nodules, keeping the one with highest score.
    
    Args:
        nodules: List of detected nodules
        overlap_threshold: Minimum overlap ratio to consider as duplicate (lower = more aggressive)
        
    Returns:
        Filtered list of nodules
    """
    if not nodules:
        return []
    
    # Sort by malignancy score (highest first) to keep best detections
    sorted_nodules = sorted(nodules, key=lambda n: n.malignancy_score, reverse=True)
    
    filtered = []
    for nodule in sorted_nodules:
        # Check overlap with existing nodules using circle intersection
        overlaps = False
        for existing in filtered:
            # Calculate distance between centers
            distance = (
                (nodule.x - existing.x) ** 2 + (nodule.y - existing.y) ** 2
            ) ** 0.5
            
            # Calculate sum of radii
            sum_radii = nodule.radius + existing.radius
            
            # Circles overlap if distance < sum of radii
            # Use overlap_threshold to control how much overlap is allowed
            # Lower threshold = more aggressive removal (0.3 means 30% overlap allowed)
            if distance < sum_radii * (1 - overlap_threshold):
                overlaps = True
                break
        
        if not overlaps:
            filtered.append(nodule)
    
    return filtered

