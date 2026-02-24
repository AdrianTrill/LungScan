import os
import glob
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Subset
import matplotlib.pyplot as plt
import random
from tqdm import tqdm
from collections import defaultdict

# --- Local Imports ---
# These must be in the same directory
from unetr import UNETR
from dataset import LidcDataset
from torch.amp import autocast 

# --- Configuration ---
MODEL_PATH = "unetr_lidc_DiceCE_Weighted_best.pth"
IMG_DIR = "./data/images"
MASK_DIR = "./data/masks"
PLOT_DIR = "./inference_plots"
NUM_EXAMPLES = 5
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# This must match your train.py setting to find the same validation set
VAL_SPLIT = 0.25
# ---------------------


# --- Copied from train.py ---
# We need this function to identical to find our validation set
def create_patient_level_stratified_split(dataset, val_split):
    """
    Splits the dataset into train and validation sets at the patient level
    to prevent data leakage.
    Ensures that both train and val sets have a similar proportion
    of positive (nodule) and negative (background) patients.
    """
    patient_patch_map = defaultdict(list)
    patient_is_positive = defaultdict(bool)
    
    # print("Mapping patches to patients...") # Silenced for visualization
    for idx, img_path in enumerate(dataset.images):
        basename = os.path.basename(img_path)
        parts = basename.split('_')
        patient_id = "_".join(parts[:-1]) 

        if not patient_id:
            continue
            
        patient_patch_map[patient_id].append(idx)
        
        if dataset.positive_indices[idx]:
            patient_is_positive[patient_id] = True
            
    positive_patient_ids = []
    negative_patient_ids = []
    for patient_id in patient_patch_map.keys():
        if patient_is_positive[patient_id]:
            positive_patient_ids.append(patient_id)
        else:
            negative_patient_ids.append(patient_id)
            
    # print(f"Total patients: {len(patient_patch_map)}. Positive: {len(positive_patient_ids)}, Negative:{len(negative_patient_ids)}")

    random.Random(42).shuffle(positive_patient_ids)
    random.Random(42).shuffle(negative_patient_ids)

    pos_val_size = int(len(positive_patient_ids) * val_split)
    if pos_val_size == 0 and len(positive_patient_ids) > 0:
        pos_val_size = 1
    
    neg_val_size = int(len(negative_patient_ids) * val_split)
    if neg_val_size == 0 and len(negative_patient_ids) > 0:
        neg_val_size = 1

    pos_train_size = len(positive_patient_ids) - pos_val_size
    neg_train_size = len(negative_patient_ids) - neg_val_size

    train_patient_ids = positive_patient_ids[:pos_train_size] + negative_patient_ids[:neg_train_size]
    val_patient_ids = positive_patient_ids[pos_train_size:] + negative_patient_ids[neg_val_size:]
    
    random.Random(42).shuffle(train_patient_ids)
    random.Random(42).shuffle(val_patient_ids)

    train_indices = [idx for pid in train_patient_ids for idx in patient_patch_map[pid]]
    val_indices = [idx for pid in val_patient_ids for idx in patient_patch_map[pid]]
        
    train_counts = {'pos': pos_train_size, 'neg': neg_train_size}
    val_counts = {'pos': pos_val_size, 'neg': neg_val_size}
        
    return train_indices, val_indices, train_counts, val_counts
# --- End of copied function ---


def plot_single_prediction(model, img_path, mask_path, idx, plot_dir, device):
    """
    Loads a single patch, runs inference, and plots the result.
    """
    
    model.eval()
    
    try:
        # 1. Load data
        img_np = np.load(img_path)   # Shape (1, 128, 128, 128)
        mask_np = np.load(mask_path) # Shape (1, 128, 128, 128)
        
        # 2. Prepare tensor for model
        img_tensor = torch.from_numpy(img_np).float().to(device)
        if img_tensor.dim() == 3: # Just in case it was saved as (D,H,W)
            img_tensor = img_tensor.unsqueeze(0)
        if img_tensor.dim() == 4: # Standard (1, D, H, W), add batch dim
             img_tensor = img_tensor.unsqueeze(0) # (1, 1, 128, 128, 128)

        # 3. Run inference
        with torch.no_grad():
            with autocast('cuda'):
                outputs = model(img_tensor).float() # Cast to float32 for stable softmax
        
        # 4. Process output
        # Get probabilities, then find the class with the highest prob (argmax)
        preds = torch.argmax(F.softmax(outputs, dim=1), dim=1)
        
        # Squeeze batch/channel dims and move to CPU for plotting
        pred_np = preds.squeeze(0).squeeze(0).cpu().numpy() # Shape (128, 128, 128)
        
        # Squeeze original data for plotting
        img_np = img_np.squeeze()   # Shape (128, 128, 128)
        mask_np = mask_np.squeeze() # Shape (128, 128, 128)

        # 5. Find a good slice to plot (center of the nodule)
        coords = np.argwhere(mask_np > 0)
        if coords.shape[0] == 0:
            print(f"Skipping {img_path}: No nodule found in mask (should be positive).")
            return
            
        center_z = int(np.mean(coords[:, 0]))

        # Get the 2D slices
        img_slice = img_np[center_z, :, :]
        mask_slice = mask_np[center_z, :, :]
        pred_slice = pred_np[center_z, :, :]
        
        # 6. Plot
        fig, axes = plt.subplots(1, 3, figsize=(20, 7))
        fig.suptitle(f'Segmentation Example {idx+1} (Slice Z={center_z})\n{os.path.basename(img_path)}', fontsize=16)

        # Colormap for overlays
        overlay_cmap = 'jet'
        
        # a) Original Image
        axes[0].imshow(img_slice, cmap='gray')
        axes[0].set_title('Original CT Slice')
        axes[0].axis('off')

        # b) Ground Truth
        axes[1].imshow(img_slice, cmap='gray')
        axes[1].imshow(np.ma.masked_where(mask_slice == 0, mask_slice), cmap=overlay_cmap, alpha=0.5)
        axes[1].set_title('Ground Truth Mask')
        axes[1].axis('off')

        # c) Model Prediction
        axes[2].imshow(img_slice, cmap='gray')
        axes[2].imshow(np.ma.masked_where(pred_slice == 0, pred_slice), cmap=overlay_cmap, alpha=0.5)
        axes[2].set_title('Model Prediction')
        axes[2].axis('off')
        
        save_path = os.path.join(plot_dir, f'segmentation_example_{idx+1}.png')
        plt.savefig(save_path, bbox_inches='tight')
        plt.close(fig)

    except Exception as e:
        print(f"Error processing {img_path}: {e}")

def main():
    os.makedirs(PLOT_DIR, exist_ok=True)
    print(f"Saving {NUM_EXAMPLES} plots to {PLOT_DIR}...")
    
    # 1. Load Model
    print(f"Loading model from {MODEL_PATH}...")
    model = UNETR(
        img_shape=(128, 128, 128),
        input_dim=1,
        output_dim=2,
        embed_dim=768,
        patch_size=16,
        num_heads=12,
        dropout=0.1
    ).to(DEVICE)
    
    try:
        checkpoint = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False)
        model.load_state_dict(checkpoint['model_state_dict'])
    except Exception as e:
        print(f"Error loading model: {e}")
        print("Please ensure 'unetr_lidc_DiceCE_Weighted_best.pth' is in this directory.")
        return
        
    model.eval()

    # 2. Load Dataset and find Validation Set
    print("Loading dataset and finding validation patches...")
    try:
        dataset = LidcDataset(img_dir=IMG_DIR, mask_dir=MASK_DIR)
        train_indices, val_indices, _, _ = create_patient_level_stratified_split(dataset, VAL_SPLIT)
    except Exception as e:
        print(f"Error loading dataset: {e}")
        print("Please ensure the './data' folder is populated by preprocess.py")
        return

    # 3. Get *positive* patches from the validation set
    positive_val_indices = [i for i in val_indices if dataset.positive_indices[i]]
    
    if len(positive_val_indices) == 0:
        print("Error: No positive patches found in your validation set.")
        return
        
    print(f"Found {len(positive_val_indices)} positive patches in validation set.")
    
    # Shuffle and select examples
    random.shuffle(positive_val_indices)
    num_to_plot = min(NUM_EXAMPLES, len(positive_val_indices))
    
    example_indices = positive_val_indices[:num_to_plot]
    
    # 4. Loop, Predict, and Plot
    for i, idx in enumerate(tqdm(example_indices, desc="Generating plots")):
        img_path = dataset.images[idx]
        mask_path = dataset.masks[idx]
        plot_single_prediction(model, img_path, mask_path, i, PLOT_DIR, DEVICE)
        
    print(f"\n--- Visualization Complete ---")
    print(f"Saved {num_to_plot} plots to {PLOT_DIR}")

if __name__ == "__main__":
    main()