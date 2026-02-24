import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
from torch.utils.data import DataLoader, Subset, WeightedRandomSampler
# --- Updated for new amp syntax ---
from torch.amp import GradScaler, autocast 
# ----------------------------------
from tqdm import tqdm
import os
import random
from collections import defaultdict
import numpy as np 
import torch.nn.functional as F
import pandas as pd
import traceback
from datetime import datetime

# --- Import our custom classes ---
# This now imports the version with augmentations
from dataset import LidcDataset 
from unetr import UNETR
from loss import DiceLoss_plus_CE_Loss
# ---------------------------------

# --- Configuration ---
IMG_DIR = "./data/images"
MASK_DIR = "./data/masks"
BATCH_SIZE = 7
LEARNING_RATE = 1e-5
EPOCHS = 50
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
VAL_SPLIT = 0.25 # 25% of the (Train+Val) data will be for validation
TEST_SPLIT = 0.20 # 20% of the *total* data will be for testing
MODEL_SAVE_PATH = "unetr_lidc_DiceCE_Weighted_best.pth" # Renamed to "best"
LOG_FILE = "training_log_DiceCE_Weighted.csv"
CRASH_LOG_FILE = "crash_log.txt"
NUM_WORKERS = 16
MAX_GRAD_NORM = 1.0
# ---------------------

def create_patient_level_splits(dataset, val_split_percent, test_split_percent):
    """
    Splits the dataset into train, validation, and test sets at the patient level
    to prevent data leakage.
    
    Ensures that all sets have a similar proportion
    of positive (nodule) and negative (background) patients.
    
    Split logic:
    1. Split *total* data into (Train+Val) and Test sets based on test_split_percent.
    2. Split the (Train+Val) data into Train and Val sets based on val_split_percent.
    """
    patient_patch_map = defaultdict(list)
    patient_is_positive = defaultdict(bool)
    
    print("Mapping patches to patients...")
    for idx, img_path in enumerate(tqdm(dataset.images, desc="Mapping patches")):
        basename = os.path.basename(img_path)
        parts = basename.split('_')
        patient_id = "_".join(parts[:-1]) # Corrected parsing logic

        if not patient_id:
            print(f"Warning: Could not parse patient ID from {basename}")
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
            
    print(f"Total patients: {len(patient_patch_map)}. Positive: {len(positive_patient_ids)}, Negative:{len(negative_patient_ids)}")

    # Shuffle lists for unbiased splitting
    random.Random(42).shuffle(positive_patient_ids)
    random.Random(42).shuffle(negative_patient_ids)

    # --- 1. Create Test Split ---
    pos_test_size = int(len(positive_patient_ids) * test_split_percent)
    neg_test_size = int(len(negative_patient_ids) * test_split_percent)

    test_pos_patients = positive_patient_ids[:pos_test_size]
    test_neg_patients = negative_patient_ids[:neg_test_size]
    
    # The remaining patients are for Train+Val
    tv_pos_patients = positive_patient_ids[pos_test_size:]
    tv_neg_patients = negative_patient_ids[neg_test_size:]

    # --- 2. Create Train/Val Split from the remaining (Train+Val) patients ---
    pos_val_size = int(len(tv_pos_patients) * val_split_percent)
    # Handle case where val_split is small and rounds to 0
    if pos_val_size == 0 and len(tv_pos_patients) > 0:
        pos_val_size = 1 
        
    neg_val_size = int(len(tv_neg_patients) * val_split_percent)

    val_pos_patients = tv_pos_patients[:pos_val_size]
    val_neg_patients = tv_neg_patients[:neg_val_size]
    
    train_pos_patients = tv_pos_patients[pos_val_size:]
    train_neg_patients = tv_neg_patients[neg_val_size:]

    # --- 3. Combine and shuffle the final patient lists ---
    train_patient_ids = train_pos_patients + train_neg_patients
    val_patient_ids = val_pos_patients + val_neg_patients
    test_patient_ids = test_pos_patients + test_neg_patients
    
    random.Random(42).shuffle(train_patient_ids)
    random.Random(42).shuffle(val_patient_ids)
    random.Random(42).shuffle(test_patient_ids)

    # --- 4. Get final patch indices ---
    train_indices = [idx for pid in train_patient_ids for idx in patient_patch_map[pid]]
    val_indices = [idx for pid in val_patient_ids for idx in patient_patch_map[pid]]
    test_indices = [idx for pid in test_patient_ids for idx in patient_patch_map[pid]]
        
    # --- 5. Report patient counts ---
    train_counts = {'pos': len(train_pos_patients), 'neg': len(train_neg_patients)}
    val_counts = {'pos': len(val_pos_patients), 'neg': len(val_neg_patients)}
    test_counts = {'pos': len(test_pos_patients), 'neg': len(test_neg_patients)}
        
    return train_indices, val_indices, test_indices, train_counts, val_counts, test_counts

def calculate_metrics(inputs, targets, smooth=1e-6):
    """
    Calculates Dice and IoU per-image in a batch.
    :param inputs: (N, C, D, H, W) Model output (logits)
    :param targets: (N, D, H, W) Ground truth (class indices)
    :return: (dice_scores, iou_scores) - Tensors of shape (N,)
    """
    # 1. Get predictions (hard labels)
    preds = torch.argmax(F.softmax(inputs, dim=1), dim=1) # Shape (N, D, H, W)
    
    # We care about the nodule class (class 1)
    nodule_preds = (preds == 1).float()
    nodule_targets = (targets == 1).float()

    # 2. Calculate intersection and union per image in batch
    # We sum over D, H, W dimensions (dims 1, 2, 3)
    dims = (1, 2, 3)
    intersection = (nodule_preds * nodule_targets).sum(dim=dims)
    union_dice = nodule_preds.sum(dim=dims) + nodule_targets.sum(dim=dims)
    union_iou = union_dice - intersection

    # 3. Calculate scores (This is now a 1D tensor of shape N)
    dice_score = (2. * intersection + smooth) / (union_dice + smooth)
    iou_score = (intersection + smooth) / (union_iou + smooth)
    
    # 4. Return the per-image scores
    return dice_score, iou_score

def main():
    print(f"Using device: {DEVICE}")
    print(f"H100 Optimized Settings: Batch Size={BATCH_SIZE}, Workers={NUM_WORKERS}, LR={LEARNING_RATE}")
    print(f"Using new Combined Loss (Dice + CE) and Weighted Patch Sampling.")
    print("--- (NEW) Using Torchio augmentations and Weight Decay ---")

    # 1. Create *full* Dataset
    try:
        # This now initializes the dataset with augmentation capabilities
        dataset = LidcDataset(img_dir=IMG_DIR, mask_dir=MASK_DIR)
        if len(dataset) == 0:
            print("Error: No data found in image/mask directories.")
            return
    except (IOError, RuntimeError) as e:
        print(f"Error initializing dataset: {e}")
        return

    # 2. Split into Training, Validation, and Test
    print("Creating patient-level stratified 3-way split (Train/Val/Test)...")
    train_indices, val_indices, test_indices, train_counts, val_counts, test_counts = create_patient_level_splits(dataset, VAL_SPLIT, TEST_SPLIT)
    
    if len(train_indices) == 0 or len(val_indices) == 0:
        print("Error: Could not create train/val split. Check VAL_SPLIT or data.")
        return
    if len(test_indices) == 0:
         print("Warning: Test set has 0 patches. Check TEST_SPLIT.")

    train_dataset = Subset(dataset, train_indices)
    val_dataset = Subset(dataset, val_indices)
    test_dataset = Subset(dataset, test_indices) # Create the test dataset
    
    n_train_patients = train_counts['pos'] + train_counts['neg']
    n_val_patients = val_counts['pos'] + val_counts['neg']
    n_test_patients = test_counts['pos'] + test_counts['neg']
    
    print(f"\n--- Split Summary ---")
    print(f"Total Patients: {n_train_patients + n_val_patients + n_test_patients}")
    print(f"  Training Patients:   {n_train_patients} ({train_counts['pos']} pos, {train_counts['neg']} neg)")
    print(f"  Validation Patients: {n_val_patients} ({val_counts['pos']} pos, {val_counts['neg']} neg)")
    print(f"  Test Patients:       {n_test_patients} ({test_counts['pos']} pos, {test_counts['neg']} neg)")
    print(f"Total Patches: {len(dataset)}")
    print(f"  Training Patches:    {len(train_dataset)}")
    print(f"  Validation Patches:  {len(val_dataset)}")
    print(f"  Test Patches:        {len(test_dataset)}\n")
    
    if val_counts['pos'] == 0:
        print("CRITICAL WARNING: Validation set has 0 positive patients. Metrics will be unreliable.")
    if test_counts['pos'] == 0:
        print("CRITICAL WARNING: Test set has 0 positive patients. Evaluation will be unreliable.")


    # 3. Create Weighted Sampler for Training
    all_weights = dataset.get_weights()
    train_weights = [all_weights[i] for i in train_indices]
    train_sampler = WeightedRandomSampler(torch.DoubleTensor(train_weights), 
                                          num_samples=len(train_weights), 
                                          replacement=True)
    
    # 4. Create DataLoaders
    train_loader = DataLoader(train_dataset, 
                              batch_size=BATCH_SIZE, 
                              sampler=train_sampler, 
                              num_workers=NUM_WORKERS, 
                              pin_memory=True,
                              shuffle=False) # shuffle=False is required when using a sampler
    
    val_loader = DataLoader(val_dataset, 
                            batch_size=BATCH_SIZE, 
                            shuffle=False, 
                            num_workers=NUM_WORKERS, 
                            pin_memory=True)

    # Create test_loader for final evaluation (not used in training loop)
    test_loader = DataLoader(test_dataset,
                             batch_size=BATCH_SIZE,
                             shuffle=False,
                             num_workers=NUM_WORKERS,
                             pin_memory=True)
    print(f"Created train_loader, val_loader, and test_loader.")

    # 5. Initialize Model
    model = UNETR(
        img_shape=(128, 128, 128),
        input_dim=1,
        output_dim=2,
        embed_dim=768,
        patch_size=16,
        num_heads=12,
        dropout=0.1
    ).to(DEVICE)
            
    # 7. Initialize Loss and Optimizer
    criterion = DiceLoss_plus_CE_Loss()
    
    # --- (MODIFIED) Added weight_decay for regularization ---
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-5)
    
    # Add Learning Rate Scheduler
    scheduler = lr_scheduler.ReduceLROnPlateau(optimizer, 'max', patience=5, factor=0.2)

    # 8. Initialize Mixed Precision GradScaler
    scaler = GradScaler('cuda')

    # 9. Initialize Log File and Resume Logic
    start_epoch = 1
    best_val_dice = 0.0 # This will now track *positive patch dice*

    # Check if the log file exists
    if os.path.exists(LOG_FILE):
        print(f"Found existing log file: {LOG_FILE}")
        try:
            log_df = pd.read_csv(LOG_FILE)
            if not log_df.empty:
                start_epoch = log_df['epoch'].max() + 1
                if 'val_pos_dice' in log_df.columns:
                    best_val_dice = log_df['val_pos_dice'].max()
                else: # Fallback for old log files
                    best_val_dice = 0.0 
                
                print(f"Resuming training from Epoch {start_epoch}")
                print(f"Best validation Positive Dice from log: {best_val_dice:.6f}")
        except Exception as e:
            print(f"Error reading log file: {e}. Starting from Epoch 1.")
    
    if start_epoch == 1:
        print(f"Starting fresh training. Logging to {LOG_FILE}")
        try:
            with open(LOG_FILE, 'w') as f:
                f.write("epoch,train_loss,val_loss,val_pos_dice,val_pos_iou,val_neg_dice\n")
        except IOError as e:
            print(f"Error: Could not write to log file {LOG_FILE}. {e}")
            return
            
    # 10. Smart Checkpoint Loading
    if os.path.exists(MODEL_SAVE_PATH):
        try:
            print(f"Attempting to load full checkpoint from {MODEL_SAVE_PATH}...")
            checkpoint = torch.load(MODEL_SAVE_PATH, map_location=DEVICE, weights_only=False)
            
            model.load_state_dict(checkpoint['model_state_dict'])
            optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            scaler.load_state_dict(checkpoint['scaler_state_dict'])
            
            start_epoch = checkpoint['epoch'] + 1
            best_val_dice = checkpoint['best_val_dice'] # This is already the "positive" dice
            
            print(f"Successfully loaded full checkpoint.")
            print(f"Resuming from Epoch {start_epoch}, Best Positive Dice: {best_val_dice:.6f}")
            
        except Exception as e:
            print(f"Could not load full checkpoint: {e}. Starting fresh.")
    else:
        print("No checkpoint found. Starting fresh.")

    # 11. Training Loop
    print(f"\n--- Starting Training from Epoch {start_epoch} ---")
    for epoch in range(start_epoch - 1, EPOCHS):
        
        epoch_num = epoch + 1
        print(f"\n--- Epoch {epoch_num}/{EPOCHS} ---")
        
        # --- Training Phase ---
        model.train()
        
        # --- (MODIFIED) Enable augmentations for training ---
        # We access .dataset because train_dataset is a torch.utils.data.Subset
        train_dataset.dataset.set_mode('train')
        
        train_loss = 0.0
                
        for i, batch in enumerate(tqdm(train_loader, desc="Training")):
            images, masks = batch
            images, masks = images.to(DEVICE, non_blocking=True), masks.to(DEVICE, non_blocking=True)
            
            with autocast('cuda'):
                outputs = model(images)
                loss = criterion(outputs, masks)
            
            if not torch.isfinite(loss):
                print(f"Warning: Encountered nan loss in training batch {i}. Skipping batch.")
                optimizer.zero_grad()
                continue

            optimizer.zero_grad()
            scaler.scale(loss).backward()
            
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), MAX_GRAD_NORM)
            
            scaler.step(optimizer)
            scaler.update()
            
            train_loss += loss.item()
        
        avg_train_loss = train_loss / len(train_loader)
        print(f"Average Training Loss: {avg_train_loss:.6f}")

        # --- (MODIFIED) Validation Phase ---
        model.eval()
        
        # --- (MODIFIED) Disable augmentations for validation ---
        val_dataset.dataset.set_mode('val')
        
        val_loss = 0.0
        
        all_pos_patch_dice = []
        all_pos_patch_iou = []
        all_neg_patch_dice = []
        
        with torch.no_grad():
            for batch in tqdm(val_loader, desc="Validating"):
                images, masks = batch
                images, masks = images.to(DEVICE, non_blocking=True), masks.to(DEVICE, non_blocking=True)
                
                with autocast('cuda'):
                    outputs = model(images)
                    loss = criterion(outputs, masks)
                
                if torch.isfinite(loss):
                    val_loss += loss.item()
                    
                    # Get per-image scores
                    dice_scores, iou_scores = calculate_metrics(outputs, masks)
                    
                    # Check which masks are positive
                    target_sums = masks.sum(dim=(1, 2, 3)) 
                    
                    for i in range(len(target_sums)):
                        if target_sums[i] > 0:
                            all_pos_patch_dice.append(dice_scores[i].item())
                            all_pos_patch_iou.append(iou_scores[i].item())
                        else:
                            all_neg_patch_dice.append(dice_scores[i].item())
                else:
                    print("Warning: Encountered nan loss during validation.")

        if len(val_loader) == 0:
            print("Warning: Validation loader is empty. Skipping validation.")
            continue
            
        avg_val_loss = val_loss / len(val_loader)
        
        # Calculate the new, meaningful averages
        avg_pos_dice = np.mean(all_pos_patch_dice) if len(all_pos_patch_dice) > 0 else 0.0
        avg_pos_iou = np.mean(all_pos_patch_iou) if len(all_pos_patch_iou) > 0 else 0.0
        avg_neg_dice = np.mean(all_neg_patch_dice) if len(all_neg_patch_dice) > 0 else 0.0
        
        print(f"Average Validation Loss: {avg_val_loss:.6f}")
        print(f"  Avg Dice (Positive Patches): {avg_pos_dice:.6f}  ({len(all_pos_patch_dice)} patches)")
        print(f"  Avg Dice (Negative Patches): {avg_neg_dice:.6f}  ({len(all_neg_patch_dice)} patches)")

        # Step the LR Scheduler based on the *real* metric
        scheduler.step(avg_pos_dice)

        # Log metrics to file
        print(f"Attempting to write to log file: {LOG_FILE}")
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(f"{epoch_num},{avg_train_loss:.6f},{avg_val_loss:.6f},{avg_pos_dice:.6f},{avg_pos_iou:.6f},{avg_neg_dice:.6f}\n")
                f.flush()
            print("Log file write successful.")
        except IOError as e:
            print(f"CRITICAL WARNING: Could not append to log file {LOG_FILE}. {e}")
            print(traceback.format_exc())

        # Save Full Checkpoint based on the *real* metric
        if avg_pos_dice > best_val_dice:
            print(f"Validation Dice (Positive) improved ({best_val_dice:.6f} -> {avg_pos_dice:.6f}). Saving model...")
            best_val_dice = avg_pos_dice
            
            checkpoint = {
                'epoch': epoch_num,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scaler_state_dict': scaler.state_dict(),
                'best_val_dice': best_val_dice # This is the positive patch dice
            }
            torch.save(checkpoint, MODEL_SAVE_PATH)
            

    print("\n--- Training Complete ---")
    print(f"Best model saved to {MODEL_SAVE_PATH} with val_pos_dice: {best_val_dice:.6f}")
    print(f"The 'test_loader' is now available for final evaluation on the held-out test set.")

if __name__ == "__main__":
    # Crash Logger
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        print("\n--- Training interrupted by user. Exiting. ---")
    except Exception as e:
        print(f"\n--- CRITICAL ERROR: Training crashed. ---")
        print(f"See {CRASH_LOG_FILE} for full traceback.")
        
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        
        with open(CRASH_LOG_FILE, 'a') as f:
            f.write(f"\n--- CRASH AT {timestamp} ---\n")
            f.write(f"Error: {str(e)}\n")
            f.write("--------------------------------\n")
            traceback.print_exc(file=f)
            f.write("--------------------------------\n\n")
        
        raise e