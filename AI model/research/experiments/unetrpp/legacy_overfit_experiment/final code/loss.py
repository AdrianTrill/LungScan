import torch

import torch.nn as nn

import torch.nn.functional as F



class DiceLoss(nn.Module):

    """

    Implements the Dice Loss for 3D segmentation.

    This loss is designed to handle extreme class imbalance.

    """

    def __init__(self, smooth=1e-6):

        super(DiceLoss, self).__init__()

        self.smooth = smooth



    def forward(self, inputs, targets):

        """

        :param inputs: (N, C, D, H, W) Model output (logits)

        :param targets: (N, D, H, W) Ground truth (class indices)

        """

        # 1. Apply Softmax to model output to get probabilities

        # We have C=2 classes (0=BG, 1=Nodule)

        probs = F.softmax(inputs, dim=1)

        

        # 2. Get the probability map for the "nodule" class (class 1)

        nodule_probs = probs[:, 1, ...]

        

        # 3. One-hot encode the target mask

        # Our target is (N, D, H, W) with 0s and 1s.

        # We only care about the nodule class.

        # We need to make sure targets are float

        nodule_targets = (targets == 1).float()

        

        # 4. Calculate Dice

        intersection = (nodule_probs * nodule_targets).sum()

        union = nodule_probs.sum() + nodule_targets.sum()

        

        dice_score = (2. * intersection + self.smooth) / (union + self.smooth)

        

        # Loss is 1 - Dice Score

        return 1. - dice_score



class DiceLoss_plus_CE_Loss(nn.Module):

    """

    Combined loss function: 0.5 * DiceLoss + 0.5 * CrossEntropyLoss

    This is the state-of-the-art for imbalanced segmentation.

    """

    def __init__(self, ce_weight=0.5, dice_weight=0.5):

        super(DiceLoss_plus_CE_Loss, self).__init__()

        self.ce_loss = nn.CrossEntropyLoss()

        self.dice_loss = DiceLoss()

        self.ce_weight = ce_weight

        self.dice_weight = dice_weight



    def forward(self, inputs, targets):

        """

        :param inputs: (N, C, D, H, W) Model output (logits)

        :param targets: (N, D, H, W) Ground truth (class indices)

        """

        # Cross-Entropy Loss

        ce = self.ce_loss(inputs, targets)

        

        # Dice Loss

        dice = self.dice_loss(inputs, targets)

        

        # Combined Loss

        return (self.ce_weight * ce) + (self.dice_weight * dice)