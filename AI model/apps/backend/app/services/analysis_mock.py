"""Mock analysis service that generates deterministic fake nodule detections.

This service provides realistic mock data for development and testing.
In production, this will be replaced with actual AI model inference.
"""

from app.core.schemas import AnalyzeResult, Nodule
from app.core.utils import generate_nodule_id, get_seeded_random


def mock_analyze(case_id: str, image_width: int = 512, image_height: int = 512) -> AnalyzeResult:
    """Generate deterministic mock analysis results for a given case.

    Args:
        case_id: Unique identifier for the case (used for deterministic seeding)
        image_width: Width of the image in pixels (default: 512)
        image_height: Height of the image in pixels (default: 512)

    Returns:
        AnalyzeResult with a list of mock nodules and a summary
    """
    rng = get_seeded_random(case_id)

    # Generate 2-5 nodules
    num_nodules = rng.randint(2, 5)
    nodules = []

    explanations = [
        "Small rounded opacity with smooth margins, likely benign",
        "Irregular nodule with spiculated borders, moderate suspicion",
        "Solid nodule with well-defined edges, low malignancy risk",
        "Ground-glass opacity with mixed density, requires follow-up",
        "Subpleural nodule with calcifications, likely benign",
        "Central nodule with cavitation, high suspicion for malignancy",
        "Small nodule with halo sign, inflammatory process possible",
        "Partially solid nodule with irregular margins, moderate concern",
    ]

    malignancy_descriptors = {
        (0.0, 0.3): "low",
        (0.3, 0.6): "moderate",
        (0.6, 0.8): "high",
        (0.8, 1.0): "very high",
    }

    for i in range(num_nodules):
        # Generate position (avoid edges)
        margin = 50
        x = rng.randint(margin, image_width - margin)
        y = rng.randint(margin, image_height - margin)

        # Generate size (radius between 5 and 30 pixels)
        radius = rng.randint(5, 30)

        # Generate malignancy score
        malignancy_score = round(rng.uniform(0.1, 0.95), 3)

        # Select explanation based on score
        explanation_idx = rng.randint(0, len(explanations) - 1)
        explanation = explanations[explanation_idx]

        # Add score descriptor to explanation
        for (low, high), desc in malignancy_descriptors.items():
            if low <= malignancy_score < high:
                explanation += f" (malignancy risk: {desc})"
                break

        nodule = Nodule(
            id=generate_nodule_id(),
            x=x,
            y=y,
            radius=radius,
            malignancy_score=malignancy_score,
            explanation=explanation,
        )
        nodules.append(nodule)

    # Calculate summary statistics
    avg_score = sum(n.malignancy_score for n in nodules) / len(nodules)
    high_risk_count = sum(1 for n in nodules if n.malignancy_score >= 0.6)

    summary = (
        f"Analysis complete: {num_nodules} nodule(s) detected. "
        f"Average malignancy score: {avg_score:.3f}. "
        f"{high_risk_count} nodule(s) with high suspicion (≥0.6). "
        "Review recommended for all detected nodules."
    )

    return AnalyzeResult(case_id=case_id, nodules=nodules, summary=summary)

