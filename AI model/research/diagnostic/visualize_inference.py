import os
import glob
import torch
import numpy as np
import matplotlib.pyplot as plt
import nibabel as nib
from monai.networks.nets import vista3d132
from monai.inferers import sliding_window_inference
from monai.transforms import (
    Compose, LoadImage, EnsureChannelFirst, Orientation, 
    Spacing, ScaleIntensityRange, Activations, AsDiscrete
)

# --- CONFIGURATION ---
PROJECT_ROOT = "/home/dem7clj/repos/mirpr"
DATA_ROOT = "/shares/CC_v_Val_FV_Gen3_all/VIDT_DL/data/cnn_training/projects/smart_data_selection/town_signs/preprocessed_output_sota/"
WEIGHTS_PATH = os.path.join(PROJECT_ROOT, "runs/vista3d_lidc_finetune/best_model_2.pth")

# VISTA Parameters
TARGET_CLASS = 23  # Lung Tumor
ROI_SIZE = (96, 96, 96)
TARGET_SPACING = (1.5, 1.5, 1.5)
INTENSITY_RANGE = (-1000, 1000)

def find_positive_sample(data_root):
    """Finds the first file in the directory that actually has a nodule."""
    print(f"Searching for a sample with nodules in {data_root}...")
    label_files = sorted(glob.glob(os.path.join(data_root, "labels", "*.nii.gz")))
    
    for lbl_path in label_files:
        # Quick check without full transform
        lbl_vol = nib.load(lbl_path).get_fdata()
        if np.sum(lbl_vol) > 0:
            # Construct corresponding image path
            img_filename = os.path.basename(lbl_path).replace("_label.nii.gz", "_image.nii.gz")
            img_path = os.path.join(data_root, "images", img_filename)
            
            if os.path.exists(img_path):
                print(f"Found positive sample: {img_filename}")
                return img_path, lbl_path
                
    raise FileNotFoundError("No samples with positive labels found!")

def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    
    # 1. Get Data
    img_path, lbl_path = find_positive_sample(DATA_ROOT)

    # 2. Define Transforms (Must match training preprocessing)
    preprocess = Compose([
        LoadImage(image_only=True),
        EnsureChannelFirst(),
        Orientation(axcodes="RAS"),
        Spacing(pixdim=TARGET_SPACING, mode="bilinear"),
        ScaleIntensityRange(
            a_min=INTENSITY_RANGE[0], a_max=INTENSITY_RANGE[1], 
            b_min=0.0, b_max=1.0, clip=True
        ),
    ])
    
    # Label transform (Nearest neighbor for masks)
    preprocess_lbl = Compose([
        LoadImage(image_only=True),
        EnsureChannelFirst(),
        Orientation(axcodes="RAS"),
        Spacing(pixdim=TARGET_SPACING, mode="nearest"),
    ])

    print("Preprocessing image...")
    img_tensor = preprocess(img_path).unsqueeze(0).to(device) # Add batch dim
    lbl_tensor = preprocess_lbl(lbl_path).unsqueeze(0).to(device)

    # 3. Load Model
    print(f"Loading weights from {WEIGHTS_PATH}...")
    model = vista3d132(encoder_embed_dim=48, in_channels=1).to(device)
    model.load_state_dict(torch.load(WEIGHTS_PATH, map_location=device, weights_only=True))
    model.eval()

    # 4. Inference
    print("Running Inference...")
    prompt_class = torch.tensor([TARGET_CLASS], device=device)
    
    with torch.no_grad():
        with torch.amp.autocast('cuda'):
            logits = sliding_window_inference(
                inputs=img_tensor, 
                roi_size=ROI_SIZE, 
                sw_batch_size=4, 
                predictor=model, 
                overlap=0.5, 
                transpose=True, # Critical for VISTA
                class_vector=prompt_class
            )
            
            # Apply Sigmoid
            probs = torch.sigmoid(logits)
            # Threshold at 0.5
            preds = (probs > 0.5).float()

    # 5. Visualization Preparation
    # Convert to numpy for plotting
    img_np = img_tensor[0, 0].cpu().numpy()
    gt_np = lbl_tensor[0, 0].cpu().numpy()
    pred_np = preds[0, 0].cpu().numpy() # Index 0 because we only asked for 1 class

    # Find the slice with the largest tumor area in Ground Truth
    # Sum across X and Y to find the Z-slice with most pixels
    slice_sums = np.sum(gt_np, axis=(0, 1))
    if slice_sums.max() == 0:
        print("Warning: GT became empty after resampling. Showing center slice.")
        best_slice_idx = gt_np.shape[2] // 2
    else:
        best_slice_idx = np.argmax(slice_sums)
        print(f"Visualizing Slice Z={best_slice_idx} (Largest GT area)")

    # 6. Plotting
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Original Image
    axes[0].imshow(img_np[:, :, best_slice_idx], cmap="gray")
    axes[0].set_title("Input CT (Preprocessed)")
    axes[0].axis('off')

    # Ground Truth
    axes[1].imshow(img_np[:, :, best_slice_idx], cmap="gray")
    axes[1].imshow(gt_np[:, :, best_slice_idx], cmap="jet", alpha=0.5) # Overlay
    axes[1].set_title("Ground Truth Overlay")
    axes[1].axis('off')

    # Prediction
    axes[2].imshow(img_np[:, :, best_slice_idx], cmap="gray")
    axes[2].imshow(pred_np[:, :, best_slice_idx], cmap="jet", alpha=0.5) # Overlay
    axes[2].set_title(f"VISTA Prediction (Class {TARGET_CLASS})")
    axes[2].axis('off')

    plt.tight_layout()
    output_png = "vista_inference_sample_our_checkpoint.png"
    plt.savefig(output_png)
    print(f"\n visualization saved to: {os.path.abspath(output_png)}")

if __name__ == "__main__":
    main()