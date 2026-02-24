import torch
import numpy as np
import matplotlib.pyplot as plt
import os
import config as cfg
from dataset import get_dataloaders

def inspect():
    print("--- 🔍 Starting Pre-Flight Data Check ---")
    
    # 1. Get Train Loader
    # We use the train loader because it has the random crops/transforms
    train_loader, _ = get_dataloaders()
    
    # 2. Fetch one batch
    print(f"Fetching one batch (Batch Size: {cfg.BATCH_SIZE})...")
    batch_data = next(iter(train_loader))
    
    images = batch_data["image"]
    labels = batch_data["label"]
    
    print(f"Batch Image Shape: {images.shape}")
    print(f"Batch Label Shape: {labels.shape}")
    
    # 3. Check Values
    unique_vals = torch.unique(labels)
    print(f"Unique Label Values in Batch: {unique_vals.tolist()}")
    
    if cfg.TARGET_VISTA_CLASS not in unique_vals:
        print("\n⚠️ WARNING: No nodules found in this random batch.") 
        print("   (This is normal if neg=0.5, try running again)")
    else:
        print(f"\n✅ SUCCESS: Found Target Class {cfg.TARGET_VISTA_CLASS} in batch!")

    # 4. Visualize Slices
    # We will loop through the batch and find the slice with the largest nodule area
    
    # Visualize up to 4 samples
    num_samples = min(4, images.shape[0])
    
    fig, axes = plt.subplots(num_samples, 3, figsize=(15, 5 * num_samples))
    if num_samples == 1: axes = [axes] # Handle single sample case
    
    for i in range(num_samples):
        img = images[i, 0] # Remove channel dim
        lbl = labels[i, 0]
        
        # Find the Z-slice with the most "23" pixels
        z_indices = torch.where(lbl == cfg.TARGET_VISTA_CLASS)[2]
        
        if len(z_indices) > 0:
            # Pick the center of the nodule
            z_slice = int(z_indices.float().mean())
            tag = f"Nodule (z={z_slice})"
        else:
            # Fallback to center slice
            z_slice = img.shape[2] // 2
            tag = "Background"

        # Plot Image
        ax_img = axes[i][0] if num_samples > 1 else axes[0]
        ax_img.imshow(img[:, :, z_slice].cpu().numpy(), cmap="gray")
        ax_img.set_title(f"Sample {i} - CT Image\n{tag}")
        ax_img.axis("off")
        
        # Plot Label
        ax_lbl = axes[i][1] if num_samples > 1 else axes[1]
        ax_lbl.imshow(lbl[:, :, z_slice].cpu().numpy(), cmap="jet", interpolation="nearest")
        ax_lbl.set_title(f"Sample {i} - Label {cfg.TARGET_VISTA_CLASS}")
        ax_lbl.axis("off")
        
        # Plot Overlay
        ax_ovl = axes[i][2] if num_samples > 1 else axes[2]
        ax_ovl.imshow(img[:, :, z_slice].cpu().numpy(), cmap="gray")
        # Mask overlay with transparency
        mask_np = lbl[:, :, z_slice].cpu().numpy()
        masked = np.ma.masked_where(mask_np == 0, mask_np)
        ax_ovl.imshow(masked, cmap="spring", alpha=0.6)
        ax_ovl.set_title(f"Overlay")
        ax_ovl.axis("off")

    plt.tight_layout()
    # Save instead of show (assuming headless server)
    save_path = os.path.join(cfg.PROJECT_ROOT, "debug_vis.png")
    plt.savefig(save_path)
    print(f"\n📸 Visualization saved to: {save_path}")
    print("Check this image to confirm nodules are aligned!")

if __name__ == "__main__":
    inspect()