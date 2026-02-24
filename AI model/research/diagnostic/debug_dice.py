import torch
import os
import numpy as np
from monai.inferers import sliding_window_inference
from monai.metrics import compute_dice

import config as cfg
from dataset import get_dataloaders
from model import get_model

def quick_test():
    device = torch.device("cuda")
    print(f"--- Quick Debug: Hunting for a Nodule ---")
    
    # 1. Load Model
    model = get_model(load_weights=False)
    ckpt_path = os.path.join(cfg.CHECKPOINT_DIR, "best_metric_model.pth")
    if not os.path.exists(ckpt_path):
        print("!! Checkpoint not found.")
        return
    
    model.load_state_dict(torch.load(ckpt_path, weights_only=True))
    model.to(device)
    model.eval()
    
    # 2. Setup Data
    _, val_loader = get_dataloaders()
    
    print("\n[Search] Scanning validation set for a sample with a tumor...")
    
    found_positive = False
    
    with torch.no_grad():
        for i, val_data in enumerate(val_loader):
            val_labels = val_data["label"].to(device)
            
            # Check if this patch has a tumor (Class 23)
            tumor_voxels = (val_labels == cfg.TARGET_VISTA_CLASS).sum().item()
            
            if tumor_voxels > 0:
                print(f"\n>>> FOUND Positive Sample at Index {i}")
                print(f"    Ground Truth Tumor Voxels: {int(tumor_voxels)}")
                
                # Run Inference
                val_images = val_data["image"].to(device)
                
                val_outputs = sliding_window_inference(
                    val_images,
                    cfg.INPUT_SHAPE,
                    4, 
                    model,
                    transpose=True,
                    class_vector=torch.tensor(cfg.LABEL_SET[1:], device=device), # Prompt: Class 23
                    overlap=0.25
                )
                
                # --- FIX: SIGMOID THRESHOLDING ---
                # Model output is [B, 1, D, H, W] (Logits for Class 23)
                # We apply Sigmoid -> Probability -> Threshold > 0.5
                probs = torch.sigmoid(val_outputs)
                pred_binary = (probs > 0.5).float()
                
                # Calculate Dice
                gt_binary = (val_labels == cfg.TARGET_VISTA_CLASS).float()
                
                dice = compute_dice(
                    y_pred=pred_binary, 
                    y=gt_binary, 
                    include_background=False
                )
                
                pred_count = pred_binary.sum().item()
                
                print(f"    Predicted Tumor Voxels:    {int(pred_count)}")
                print(f"    DICE SCORE:                {dice.item():.4f}")
                
                if dice.item() < 0.05 and pred_count == 0:
                    print("\n[Diagnosis] Model missed the nodule completely (False Negative).")
                elif dice.item() < 0.05 and pred_count > 0:
                    print("\n[Diagnosis] Model predicted something, but it didn't overlap (False Positive / Misalignment).")
                else:
                    print("\n[Diagnosis] Model detected the nodule!")
                
                found_positive = True
                break # Stop after finding one
    
    if not found_positive:
        print("\n[Warning] Scanned entire validation set but found NO nodules. Check your dataset splitting or preprocessing!")

if __name__ == "__main__":
    quick_test()