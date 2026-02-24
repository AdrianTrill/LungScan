import torch.nn as nn
from monai.losses import DiceFocalLoss, TverskyLoss

class RobustSegmentationLoss(nn.Module):
    def __init__(self):
        super().__init__()
        
        # 1. Tversky: The Main Driver
        # alpha=0.3, beta=0.7 -> Penalizes False Negatives more (High Recall)
        self.tversky = TverskyLoss(
            include_background=False, # Only calculate for Nodule class
            to_onehot_y=True,         # Handles targets conversion automatically
            softmax=True,
            alpha=0.3,
            beta=0.7
        )
        
        # 2. Focal: The Stabilizer
        # Helps learn "hard" examples. 
        # Monai's implementation handles the alpha/gamma correctly.
        self.focal = DiceFocalLoss(
            include_background=False,
            to_onehot_y=True,
            softmax=True,
            lambda_dice=0.0,   # We only want the Focal part from this class
            lambda_focal=1.0
        )

    def forward(self, inputs, targets):
        # inputs: (B, 2, D, H, W)
        # targets: (B, 1, D, H, W) or (B, D, H, W)
        
        # Tversky handles the "Shape" and "Recall"
        loss_t = self.tversky(inputs, targets)
        
        # Focal handles the "Pixel Classification" difficulty
        loss_f = self.focal(inputs, targets)
        
        # Weighted Sum
        # We usually weigh Tversky higher in segmentation tasks
        return 0.5 * loss_t + 0.5 * loss_f