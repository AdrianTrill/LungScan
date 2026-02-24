"""Model loader service for downloading and loading the lung cancer detection model from Hugging Face."""

import logging
from pathlib import Path
from typing import Optional

import torch
from huggingface_hub import hf_hub_download
from torch import nn
import torchvision.transforms as transforms
from torchvision import models

logger = logging.getLogger(__name__)

# Model repository on Hugging Face
MODEL_REPO = "dorsar/lung-cancer-detection"
# The Hugging Face repo keeps weights under the Model/ directory
# (see https://huggingface.co/dorsar/lung-cancer-detection/tree/main/Model)
MODEL_FILENAME = "Model/lung_cancer_detection_model.pth"

# Class labels for the model
CLASS_LABELS = [
    "Adenocarcinoma",
    "Large Cell Carcinoma",
    "Normal",
    "Squamous Cell Carcinoma",
]

# Image preprocessing parameters
IMAGE_SIZE = 224  # Standard input size for most CNN models
MEAN = [0.485, 0.485, 0.485]  # Grayscale normalization
STD = [0.229, 0.229, 0.229]


class LungCancerModel(nn.Module):
    """Model architecture that matches the Hugging Face checkpoint.

    The published weights are based on a ResNet-50 backbone with a custom
    fully-connected head (stored as `fc.0`, `fc.3`, etc. in the checkpoint).
    """

    def __init__(self, num_classes: int = 4):
        super().__init__()
        # Initialize ResNet-50 backbone (no pretrained weights, since the HF
        # checkpoint already contains the tuned weights)
        self.resnet = models.resnet50(weights=None)
        in_features = self.resnet.fc.in_features
        self.resnet.fc = nn.Identity()

        # Classification head (Sequential so layer names match checkpoint keys)
        # Match HF checkpoint head dimensions (256 hidden units)
        self.fc = nn.Sequential(
            nn.Linear(in_features, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        features = self.resnet(x)
        logits = self.fc(features)
        return logits


class ModelLoader:
    """Service for loading and managing the lung cancer detection model."""
    
    def __init__(self):
        self.model: Optional[torch.nn.Module] = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.transform = transforms.Compose([
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(mean=MEAN, std=STD),
        ])
        logger.info(f"Model will run on device: {self.device}")
    
    def load_model(self, model_path: Optional[Path] = None) -> torch.nn.Module:
        """Load the model from file or download from Hugging Face if not present.
        
        Args:
            model_path: Optional local path to model file. If None, downloads from HF.
            
        Returns:
            Loaded PyTorch model
        """
        if self.model is not None:
            return self.model
        
        try:
            if model_path and Path(model_path).exists():
                logger.info(f"Loading model from local path: {model_path}")
                model_file = model_path
            else:
                # Download model from Hugging Face
                logger.info(f"Downloading model from Hugging Face: {MODEL_REPO}")
                model_file = hf_hub_download(
                    repo_id=MODEL_REPO,
                    filename=MODEL_FILENAME,
                    cache_dir=Path.home() / ".cache" / "huggingface" / "lungscan",
                )
                logger.info(f"Model downloaded to: {model_file}")
            
            # Initialize model architecture
            model = LungCancerModel(num_classes=len(CLASS_LABELS))
            
            # Load weights
            checkpoint = torch.load(model_file, map_location=self.device)
            
            # Handle different checkpoint formats
            if isinstance(checkpoint, dict):
                if "model_state_dict" in checkpoint:
                    model.load_state_dict(checkpoint["model_state_dict"])
                elif "state_dict" in checkpoint:
                    model.load_state_dict(checkpoint["state_dict"])
                else:
                    model.load_state_dict(checkpoint)
            else:
                model.load_state_dict(checkpoint)
            
            model.to(self.device)
            model.eval()  # Set to evaluation mode
            
            self.model = model
            logger.info("Model loaded successfully")
            return model
            
        except FileNotFoundError as e:
            logger.error(f"Model file not found: {str(e)}")
            raise RuntimeError(
                f"Model file not found. Please ensure the model is available at {MODEL_REPO} "
                "or provide a local model path."
            )
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}", exc_info=True)
            # Try to provide more helpful error message
            error_msg = (
                f"Failed to load model from {MODEL_REPO}. "
                f"Error: {str(e)}. "
                "The model architecture might not match, or the checkpoint format is different. "
                "Please check the Hugging Face repository for the correct model format."
            )
            raise RuntimeError(error_msg) from e
    
    def get_transform(self):
        """Get the image preprocessing transform."""
        return self.transform
    
    def get_device(self):
        """Get the device (CPU/GPU) the model is running on."""
        return self.device


# Global model loader instance
_model_loader: Optional[ModelLoader] = None


def get_model_loader() -> ModelLoader:
    """Get or create the global model loader instance."""
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader

