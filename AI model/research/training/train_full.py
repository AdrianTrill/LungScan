import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import OneCycleLR
from torch.utils.data import DataLoader, Subset, WeightedRandomSampler
from torch.amp import GradScaler, autocast 
from tqdm import tqdm
import os
import random
from collections import defaultdict
import numpy as np 
import torch.nn.functional as F
import pandas as pd
import traceback
import torch.multiprocessing as mp
import torch.distributed as dist
from datetime import timedelta
from torch.nn.parallel import DistributedDataParallel as DDP

# --- MONAI IMPORTS ---
from monai.transforms import (
    Compose, RandCropByPosNegLabeld, RandRotate90d, 
    RandFlipd, SpatialPadd
)

# --- LOCAL IMPORTS ---
from dataset import LidcDataset
from model import UNETR_PP
from loss import RobustSegmentationLoss

# --- CONFIGURATION ---
IMG_DIR = "../data/images"
MASK_DIR = "../data/masks"

# SAFETY SETTINGS
# UNETR++ is heavier than SegResNet. 
# On H100 (80GB), Batch Size 8 (128^3) is safe. 18 will likely OOM.
BATCH_SIZE = 8       
NUM_WORKERS = 8       
PREFETCH_FACTOR = 2

# OPTIMIZATION
MAX_LR = 1e-3         
WEIGHT_DECAY = 1e-5   
EPOCHS = 50           
VAL_SPLIT = 0.20 
MODEL_SAVE_PATH = "unetr_pp_best.pth" 
LOG_FILE = "training_log_H100.csv" 
MAX_GRAD_NORM = 1.0
WORLD_SIZE = 2        

def setup(rank, world_size):
    os.environ['MASTER_ADDR'] = 'localhost'
    os.environ['MASTER_PORT'] = '12355'
    
    # Timeout 30 mins
    dist.init_process_group(
        "nccl", 
        rank=rank, 
        world_size=world_size, 
        timeout=timedelta(minutes=30)
    )
    torch.cuda.set_device(rank)
    # H100 optimization
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

def cleanup():
    dist.destroy_process_group()

def create_patient_level_stratified_split(dataset, val_split):
    """
    Ensures patches from the same patient don't leak between train/val.
    Assumes filenames are 'PatientID_PatchID.npy'.
    """
    patient_patch_map = defaultdict(list)
    patient_is_positive = defaultdict(bool)
    
    # Only rank 0 needs to show the progress bar ideally, but for mapping we do it quick
    iterator = dataset.images
    if dist.get_rank() == 0:
        iterator = tqdm(dataset.images, desc="Stratifying Patients")

    for idx, img_path in enumerate(iterator):
        basename = os.path.basename(img_path)
        # Parsing Patient ID (adjust split logic if filename differs)
        parts = basename.split('_')
        patient_id = "_".join(parts[:-1]) 
        
        if not patient_id: continue
        patient_patch_map[patient_id].append(idx)
        
        # Check cache for positivity
        if dataset.positive_indices[idx]:
            patient_is_positive[patient_id] = True
            
    positive_patient_ids = [pid for pid, is_pos in patient_is_positive.items() if is_pos]
    negative_patient_ids = [pid for pid, is_pos in patient_is_positive.items() if not is_pos]
    
    # Shuffle with fixed seed for consistency across DDP ranks
    random.Random(42).shuffle(positive_patient_ids)
    random.Random(42).shuffle(negative_patient_ids)

    pos_val_size = int(len(positive_patient_ids) * val_split)
    pos_val_size = max(1, pos_val_size) if positive_patient_ids else 0
    neg_val_size = int(len(negative_patient_ids) * val_split)
    neg_val_size = max(1, neg_val_size) if negative_patient_ids else 0

    pos_train_size = len(positive_patient_ids) - pos_val_size
    neg_train_size = len(negative_patient_ids) - neg_val_size

    train_patient_ids = positive_patient_ids[:pos_train_size] + negative_patient_ids[:neg_train_size]
    val_patient_ids = positive_patient_ids[pos_train_size:] + negative_patient_ids[neg_val_size:]
    
    # Shuffle again
    random.Random(42).shuffle(train_patient_ids)
    random.Random(42).shuffle(val_patient_ids)

    train_indices = [idx for pid in train_patient_ids for idx in patient_patch_map[pid]]
    val_indices = [idx for pid in val_patient_ids for idx in patient_patch_map[pid]]
    
    train_counts = {'pos': pos_train_size, 'neg': neg_train_size}
    val_counts = {'pos': pos_val_size, 'neg': neg_val_size}
    
    return train_indices, val_indices, train_counts, val_counts

def calculate_metrics(inputs, targets, smooth=1e-6):
    # Handle list output from Deep Supervision (take only the main head [0])
    if isinstance(inputs, list): inputs = inputs[0]
    
    preds = torch.argmax(F.softmax(inputs, dim=1), dim=1) 
    nodule_preds = (preds == 1).float()
    nodule_targets = (targets == 1).float()
    dims = (1, 2, 3) 
    intersection = (nodule_preds * nodule_targets).sum(dim=dims)
    union_dice = nodule_preds.sum(dim=dims) + nodule_targets.sum(dim=dims)
    dice_score = (2. * intersection + smooth) / (union_dice + smooth)
    return dice_score

def main(rank, world_size):
    setup(rank, world_size)
    device = torch.device(f"cuda:{rank}")

    if rank == 0:
        print(f"--- Starting Robust Training on {world_size} GPUs (H100 Optimized) ---")
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w') as f:
                f.write("epoch,train_loss,val_loss,val_dice,lr\n")

    # --- DATASET SETUP ---
    try:
        # Note: 'augment' arg removed; we use cache_file and min_nodule_size
        train_ds_full = LidcDataset(
            img_dir=IMG_DIR, 
            mask_dir=MASK_DIR, 
            min_nodule_size=50, 
            cache_file="dataset_cache.json"
        )
        val_ds_full = LidcDataset(
            img_dir=IMG_DIR, 
            mask_dir=MASK_DIR, 
            min_nodule_size=50, 
            cache_file="dataset_cache.json"
        )
    except Exception as e:
        if rank == 0: print(f"Error initializing dataset: {e}")
        cleanup()
        return

    # --- SPLIT ---
    train_indices, val_indices, _, _ = create_patient_level_stratified_split(train_ds_full, VAL_SPLIT)
    
    # DDP Sharding
    train_chunk = len(train_indices) // world_size
    train_start = rank * train_chunk
    train_end = train_start + train_chunk if rank != world_size - 1 else len(train_indices)
    local_indices = train_indices[train_start:train_end]
    
    # For validation we often skip sharding logic if dataset is small, 
    # but for safety we shard it here too.
    val_chunk = len(val_indices) // world_size
    val_start = rank * val_chunk
    val_end = val_start + val_chunk if rank != world_size - 1 else len(val_indices)
    local_val_indices = val_indices[val_start:val_end]

    local_train_ds = Subset(train_ds_full, local_indices)
    local_val_ds = Subset(val_ds_full, local_val_indices)

    # Weights for Sampler
    all_weights = train_ds_full.get_weights()
    local_weights = [all_weights[i] for i in local_indices]
    
    # Weighted Sampler for Class Imbalance
    SAMPLES_PER_EPOCH = 6000 // world_size # Adjust per GPU
    train_sampler = WeightedRandomSampler(
        torch.DoubleTensor(local_weights), num_samples=SAMPLES_PER_EPOCH, replacement=True
    )
    
    train_loader = DataLoader(
        local_train_ds, batch_size=BATCH_SIZE, sampler=train_sampler,
        num_workers=NUM_WORKERS, persistent_workers=True, 
        prefetch_factor=PREFETCH_FACTOR, pin_memory=True
    )
    val_loader = DataLoader(
        local_val_ds, batch_size=BATCH_SIZE, shuffle=False,
        num_workers=4, persistent_workers=False, pin_memory=True
    )

    # --- MODEL: UNETR++ ---
    model = UNETR_PP(
        in_channels=1,
        out_channels=2,
        img_size=(128, 128, 128), # Full patch size
        base_filters=32,
        deep_supervision=True
    ).to(device)
    
    # SyncBatchNorm for DDP
    model = torch.nn.SyncBatchNorm.convert_sync_batchnorm(model)
    model = DDP(model, device_ids=[rank])
             
    criterion = RobustSegmentationLoss().to(device)
    # Weights for Deep Supervision heads [Main, DS1, DS0]
    ds_loss_weights = torch.tensor([1.0, 0.8, 0.5], device=device)

    optimizer = optim.AdamW(model.parameters(), lr=MAX_LR, weight_decay=WEIGHT_DECAY)
    
    scheduler = OneCycleLR(
        optimizer,
        max_lr=MAX_LR,
        epochs=EPOCHS,
        steps_per_epoch=len(train_loader),
        pct_start=0.3, 
        div_factor=25,
        final_div_factor=1e4
    )
    
    # H100: GradScaler is technically optional for BF16 but good for safety
    scaler = GradScaler('cuda') 

    # --- GPU TRANSFORMS (SMART CROP) ---
    # Replacing the manual augmentation block with Monai's optimized pipeline
    gpu_transforms = Compose([
        # Ensure inputs are padded if smaller than crop size (safety)
        SpatialPadd(keys=["image", "label"], spatial_size=(128, 128, 128)),
        
        # Smart Crop: Always find the nodule (pos=1.0)
        RandCropByPosNegLabeld(
            keys=["image", "label"],
            label_key="label",
            spatial_size=(128, 128, 128), # Keep full resolution
            pos=1.0, 
            neg=0.0, 
            num_samples=1,
            image_key="image",
            image_threshold=0,
        ),
        RandRotate90d(keys=["image", "label"], prob=0.5, spatial_axes=(0, 1)),
        RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=0),
        RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=1),
        RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=2),
    ])

    # --- RESUME LOGIC ---
    start_epoch = 0
    best_val_dice = 0.0
    
    if os.path.exists(MODEL_SAVE_PATH):
        try:
            map_location = {'cuda:%d' % 0: 'cuda:%d' % rank}
            checkpoint = torch.load(MODEL_SAVE_PATH, map_location=map_location)
            model.module.load_state_dict(checkpoint['model_state_dict'])
            
            if 'optimizer_state_dict' in checkpoint:
                optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            if 'scheduler_state_dict' in checkpoint:
                scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
            if 'scaler_state_dict' in checkpoint:
                scaler.load_state_dict(checkpoint['scaler_state_dict'])
            if 'epoch' in checkpoint:
                start_epoch = checkpoint['epoch']
            if 'best_val_dice' in checkpoint:
                best_val_dice = checkpoint['best_val_dice']
                
            if rank == 0: print(f"Resuming from Epoch {start_epoch} with Best Dice {best_val_dice:.4f}")
        except Exception as e:
            if rank == 0: print(f"Warning: Could not load checkpoint fully ({e}). Starting from scratch.")

    for epoch in range(start_epoch, EPOCHS):
        model.train()
        train_loss = torch.tensor(0.0, device=device)
        
        if rank == 0: pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}")
        else: pbar = train_loader

        for batch in pbar:
            images, masks = batch
            images, masks = images.to(device, non_blocking=True), masks.to(device, non_blocking=True)
            
            # --- APPLY GPU TRANSFORMS ---
            # We must wrap in dict for Monai transforms
            data_dict = {"image": images, "label": masks}
            # Apply transforms (Smart Crop + Augmentations)
            data_dict = gpu_transforms(data_dict)
            
            # Unpack (Monai might return list of dicts if num_samples > 1, but here it's 1)
            if isinstance(data_dict, list):
                images = torch.stack([d["image"] for d in data_dict])
                masks = torch.stack([d["label"] for d in data_dict])
                # Fix dimensions: stack creates (B, 1, C, D, H, W) -> squeeze to (B, C, D, H, W)
                images = images.squeeze(1)
                masks = masks.squeeze(1)
            else:
                images, masks = data_dict["image"], data_dict["label"]

            optimizer.zero_grad()
            
            # H100: Use BFloat16
            with autocast('cuda', dtype=torch.bfloat16):
                outputs = model(images)
                
                # --- DEEP SUPERVISION LOSS ---
                # UNETR++ returns list: [logits, ds1, ds0]
                loss = 0.0
                graph_ref = None
                
                if isinstance(outputs, list):
                    # Main Head
                    loss += criterion(outputs[0], masks) * ds_loss_weights[0]
                    graph_ref = outputs[0]
                    
                    # Aux Heads (Already Upsampled by Model)
                    if len(outputs) > 1:
                        loss += criterion(outputs[1], masks) * ds_loss_weights[1]
                    if len(outputs) > 2:
                        loss += criterion(outputs[2], masks) * ds_loss_weights[2]
                else:
                    # Fallback if DS disabled
                    loss = criterion(outputs, masks)
                    graph_ref = outputs

            # --- FIXED NAN HANDLING ---
            if torch.isnan(loss):
                if rank == 0: print("Warning: NaN Loss detected. Zeroing with graph attachment.")
                # Attach 0.0 to the graph to prevent broken pipes in DDP
                loss = torch.nan_to_num(graph_ref).mean() * 0.0
            
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), MAX_GRAD_NORM)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            
            train_loss += loss.item()
            if rank == 0 and random.random() < 0.01:
                pbar.set_postfix({"Loss": f"{loss.item():.4f}", "LR": f"{scheduler.get_last_lr()[0]:.6f}"})
        
        dist.all_reduce(train_loss, op=dist.ReduceOp.SUM)
        avg_train_loss = train_loss.item() / (len(train_loader) * world_size)
        
        # --- VALIDATION ---
        model.eval()
        val_loss = torch.tensor(0.0, device=device)
        pos_dice_sum = torch.tensor(0.0, device=device)
        pos_count = torch.tensor(0.0, device=device)
        
        with torch.no_grad():
            for batch in val_loader:
                images, masks = batch
                images, masks = images.to(device, non_blocking=True), masks.to(device, non_blocking=True)
                
                with autocast('cuda', dtype=torch.bfloat16):
                    outputs = model(images)
                    
                    # Handle List Output for Validation
                    if isinstance(outputs, list):
                        main_out = outputs[0]
                        # For Val Loss, we typically only care about main head, or sum all
                        # Let's sum all for consistency
                        v_loss = criterion(main_out, masks) * ds_loss_weights[0]
                    else:
                        main_out = outputs
                        v_loss = criterion(main_out, masks)
                        
                    val_loss += v_loss.item()
                    
                dice = calculate_metrics(main_out, masks)
                
                # Only count Dice if there is actually a nodule in this patch
                target_sums = masks.sum(dim=(1, 2, 3))
                valid_mask = target_sums > 0
                if valid_mask.any():
                    pos_dice_sum += dice[valid_mask].sum()
                    pos_count += valid_mask.sum()

        dist.all_reduce(val_loss, op=dist.ReduceOp.SUM)
        dist.all_reduce(pos_dice_sum, op=dist.ReduceOp.SUM)
        dist.all_reduce(pos_count, op=dist.ReduceOp.SUM)
        
        avg_val_loss = val_loss.item() / (len(val_loader) * world_size)
        avg_pos_dice = (pos_dice_sum / pos_count).item() if pos_count > 0 else 0.0
        current_lr = scheduler.get_last_lr()[0]

        if rank == 0:
            print(f"Ep {epoch+1} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val Dice: {avg_pos_dice:.4f}")
            
            with open(LOG_FILE, 'a') as f:
                f.write(f"{epoch+1},{avg_train_loss:.6f},{avg_val_loss:.6f},{avg_pos_dice:.6f},{current_lr:.8f}\n")
            
            checkpoint = {
                'epoch': epoch + 1,
                'model_state_dict': model.module.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scheduler_state_dict': scheduler.state_dict(),
                'scaler_state_dict': scaler.state_dict(),
                'best_val_dice': max(best_val_dice, avg_pos_dice)
            }
            
            torch.save(checkpoint, MODEL_SAVE_PATH)
            
            if avg_pos_dice > best_val_dice:
                best_val_dice = avg_pos_dice

    cleanup()

if __name__ == "__main__":
    try:
        mp.spawn(main, args=(WORLD_SIZE,), nprocs=WORLD_SIZE, join=True)
    except Exception as e:
        traceback.print_exc()