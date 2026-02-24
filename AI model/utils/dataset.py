import torch
import numpy as np
from monai.transforms import (
    Compose,
    LoadImaged,
    EnsureChannelFirstd,
    Orientationd,
    Spacingd,
    ScaleIntensityRanged,
    RandCropByPosNegLabeld,
    RandAffined,
    RandGaussianNoised,
    RandFlipd,
    RandRotate90d,
    EnsureTyped
)
from monai.apps.vista3d.transforms import Relabeld
import config as cfg

def get_transforms(mode="train"):
    transforms = [
        LoadImaged(keys=["image", "label"]),
        EnsureChannelFirstd(keys=["image", "label"]),
        Orientationd(keys=["image", "label"], axcodes="RAS"),
        # Official VISTA spacing
        Spacingd(
            keys=["image", "label"], 
            pixdim=cfg.TARGET_SPACING, 
            mode=("bilinear", "nearest")
        ),
        # Official VISTA Intensity Range (Foundation Model Alignment)
        ScaleIntensityRanged(
            keys=["image"],
            a_min=cfg.INTENSITY_RANGE[0],
            a_max=cfg.INTENSITY_RANGE[1],
            b_min=0.0,
            b_max=1.0,
            clip=True,
        ),
        # Map LIDC(1) -> VISTA(23)
        Relabeld(keys="label", label_mappings=cfg.LABEL_MAPPINGS, dtype=torch.uint8),
    ]

    if mode == "train":
        transforms += [
            # Dynamic Cropping for Small Nodules
            RandCropByPosNegLabeld(
                keys=["image", "label"],
                label_key="label",
                spatial_size=cfg.ROI_SIZE,
                pos=2,
                neg=1,
                num_samples=4,
                image_key="image",
                image_threshold=0,
            ),
            RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=0),
            RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=1),
            RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=2),
            RandRotate90d(keys=["image", "label"], prob=0.5, max_k=3),
            RandGaussianNoised(keys=["image"], prob=0.1, mean=0.0, std=0.1),
            RandAffined(
                keys=['image', 'label'],
                mode=('bilinear', 'nearest'),
                prob=0.3,
                spatial_size=cfg.ROI_SIZE,
                rotate_range=(0, 0, np.pi/15),
                scale_range=(0.1, 0.1, 0.1)
            )
        ]

    return Compose(transforms + [EnsureTyped(keys=["image", "label"])])