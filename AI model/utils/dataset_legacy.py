import os

import glob

import numpy as np

import torch

from torch.utils.data import Dataset

import torchio as tio

from tqdm import tqdm # <-- FIX: Added the missing import



class LidcDataset(Dataset):

    """

    Custom PyTorch Dataset for loading LIDC-IDRI patches.

    This class now correctly binarizes masks to {0, 1} and

    applies 3D augmentations using torchio.

    """

    def __init__(self, img_dir, mask_dir):

        self.images = sorted(glob.glob(os.path.join(img_dir, "*.npy")))

        self.masks = sorted(glob.glob(os.path.join(mask_dir, "*.npy")))

        

        if len(self.images) == 0:

            raise IOError(f"No image patches found in {img_dir}.")

        if len(self.images) != len(self.masks):

            raise IOError("Mismatch between number of images and masks.")

            

        # --- Sanity Check (as you suggested) ---

        try:

            sample_mask = np.load(self.masks[0])

            print(f"Dataset sanity check: Unique values in first mask: {np.unique(sample_mask)}")

        except Exception as e:

            print(f"Could not perform sanity check: {e}")

        # ----------------------------------------

            

        self.positive_indices = []

        self.weights = []

        

        print("Scanning dataset for positive patches and weights...")

        for mask_path in tqdm(self.masks, desc="Scanning masks"):

            mask = np.load(mask_path)

            # FIX: Check for *any* positive value

            if np.any(mask > 0): 

                self.positive_indices.append(True)

            else:

                self.positive_indices.append(False)

                

        num_pos = sum(self.positive_indices)

        num_neg = len(self.positive_indices) - num_pos

        

        if num_pos == 0:

            raise RuntimeError("No positive patches found. Cannot train.")

            

        # Calculate weight for positive class

        # (total_samples / num_classes) / num_samples_per_class

        # This formula gives more weight to the rare class

        

        # Simpler way: weight = num_neg / num_pos

        pos_weight = num_neg / num_pos

        

        self.weights = [pos_weight if self.positive_indices[i] else 1.0 for i in range(len(self.images))]

        print(f"Found {len(self.images)} patches ({num_pos} pos, {num_neg} neg). Pos weight: {pos_weight:.2f}")



        # --- Augmentation Pipeline ---

        # This transform is applied ONLY in 'train' mode

        self.transform = tio.Compose([

            tio.RandomFlip(axes=('LR',)), # Flip left-right

            tio.RandomAffine(

                scales=(0.9, 1.2),

                degrees=10,

                isotropic=False,

                default_pad_value=0 # Use 0 for background padding

            ),

            tio.RandomGamma(log_gamma=(-0.3, 0.3)),

            tio.RandomNoise(std=0.01)

        ])

        

        self.mode = 'val' # Default to validation mode



    def set_mode(self, mode):

        """Set to 'train' to enable augmentations, 'val' to disable."""

        self.mode = mode



    def get_weights(self):

        return self.weights



    def __len__(self):

        return len(self.images)



    def __getitem__(self, idx):

        # 1. Load numpy arrays

        img_np = np.load(self.images[idx]) 

        # Load mask as int64 to be safe, will be binarized

        mask_np = np.load(self.masks[idx]).astype(np.int64) 



        # --- FIX: Binarize mask to {0, 1} ---

        # Treat any non-zero value as foreground (nodule)

        mask_np = (mask_np > 0).astype(np.int64)

        # -----------------------------------



        # --- Optional CT Normalization (as you suggested) ---

        # This should be applied before any noise augmentations

        img_np = np.clip(img_np, -1000, 400) # Window

        img_np = (img_np - np.mean(img_np)) / (np.std(img_np) + 1e-6) # Z-score

        # -----------------------------------



        # --- FIX: Ensure 4D (C,D,H,W) and convert to tensors ---

        if img_np.ndim == 3: # (D, H, W) -> (1, D, H, W)

            img_np = np.expand_dims(img_np, 0)

        if mask_np.ndim == 3: # (D, H, W) -> (1, D, H, W)

            mask_np = np.expand_dims(mask_np, 0)



        # Convert to Tensors *before* creating TorchIO subject

        img_tensor = torch.from_numpy(img_np).float()

        mask_tensor = torch.from_numpy(mask_np).long() # Use Long for LabelMap

        # -----------------------------------

        

        # 2. Create TorchIO Subject

        subject = tio.Subject(

            image=tio.ScalarImage(tensor=img_tensor),

            mask=tio.LabelMap(tensor=mask_tensor) # Use LabelMap for nearest-neighbor

        )

        

        # 3. Apply augmentations ONLY if in 'train' mode

        if self.mode == 'train':

            transformed = self.transform(subject)

        else:

            transformed = subject

            

        # 4. Prepare output

        img_out = transformed.image.data

        

        # --- FIX: Squeeze mask for CrossEntropyLoss ---

        # Output shape (D, H, W) and dtype long (int64)

        mask_out = transformed.mask.data.squeeze(0).long()

        # ----------------------------------

        

        return img_out, mask_out