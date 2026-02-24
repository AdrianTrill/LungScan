"""
UNETR-PP H100 training script (archived experiment version).

This file is added for reproducibility / documentation and corresponds to the
training pipeline described in the experiment reports under `experiment-full-dataset/`.

Notes:
- This script depends on a local module `architecture` providing:
  - UNETR_PP_H100
  - RobustSegmentationLoss
- Intended for multi-GPU DDP runs (NCCL).
"""

import os


# [CRITICAL FIX] Environment Variables for Stability
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["CV_NUM_THREADS"] = "0"
# [FIXED] Updated deprecated env var
os.environ["TORCH_NCCL_ASYNC_ERROR_HANDLING"] = "1"

import argparse
import time
import datetime
import csv
import json
import random
import glob
import warnings
import math
import copy
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.distributed as dist
import torch.multiprocessing
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader, DistributedSampler, Dataset
from torch.amp import GradScaler
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

# --- MONAI ---
from monai.transforms import (
    Compose,
    RandCropByPosNegLabeld,
    RandSpatialCropd,
    RandRotate90d,
    RandFlipd,
    RandAffined,
    EnsureTyped,
    RandShiftIntensityd,
    RandZoomd,
    RandGaussianNoised,
    RandGaussianSmoothd,
    AsDiscrete,
    ScaleIntensityRanged,
    SpatialPadd,
    MapTransform,
    Lambdad,
)
from monai.metrics import DiceMetric, ConfusionMatrixMetric
from monai.data import decollate_batch, MetaTensor
from torch.optim.lr_scheduler import LinearLR, CosineAnnealingLR, SequentialLR
from monai.inferers import sliding_window_inference

# --- LOCAL IMPORTS ---
from architecture import UNETR_PP_H100, RobustSegmentationLoss

# Suppress benign warnings
warnings.filterwarnings("ignore", module="monai.transforms.utils", message="Num foregrounds 0")
warnings.filterwarnings("ignore", message="Using a non-tuple sequence")
warnings.filterwarnings("ignore", message="The given NumPy array is not writable")

cache_dir = os.path.join(os.getcwd(), ".cache")
os.makedirs(cache_dir, exist_ok=True)

os.environ["HOME"] = os.getcwd()  # Fake the home directory
os.environ["TORCHINDUCTOR_CACHE_DIR"] = os.path.join(cache_dir, "torch")
os.environ["TRITON_CACHE_DIR"] = os.path.join(cache_dir, "triton")
os.environ["PYTORCH_KERNEL_CACHE_PATH"] = os.path.join(cache_dir, "kernels")

# Fix for High-VRAM DDP setups
try:
    torch.multiprocessing.set_sharing_strategy("file_system")
except RuntimeError:
    pass

# -------------------------------------------------------------------------
# 1. HELPER FUNCTIONS
# -------------------------------------------------------------------------


def robust_make_writable(data):
    """Ensures data loaded via mmap is writable for transforms."""
    if isinstance(data, (torch.Tensor, MetaTensor)):
        return data.clone().detach()
    elif isinstance(data, np.ndarray):
        return np.ascontiguousarray(data)
    else:
        return np.array(data).copy()


def apply_transforms_batched(batch_dict, transform_func):
    """
    [CRITICAL FIX] Applies MONAI dictionary transforms to a Batch.
    MONAI transforms expect (C, D, H, W).
    We must iterate the batch (B, C, D, H, W) to apply unique random
    augmentations to each sample.
    """
    images = batch_dict["image"]
    labels = batch_dict["label"]
    B = images.shape[0]

    out_imgs, out_lbls = [], []

    # Loop over batch items.
    # Note: The actual heavy math (affine/rotate) runs on GPU (CUDA kernels).
    # This loop overhead is negligible compared to the H100 compute speed.
    for i in range(B):
        # Create single item dict (C, D, H, W)
        data_item = {"image": images[i], "label": labels[i]}

        # Apply Transform (Returns dict)
        data_out = transform_func(data_item)

        out_imgs.append(data_out["image"])
        out_lbls.append(data_out["label"])

    # Stack back into a Batch (B, C, D, H, W)
    return {"image": torch.stack(out_imgs), "label": torch.stack(out_lbls)}


class SafeRandCropByPosNegLabeld(MapTransform):
    def __init__(
        self,
        keys,
        label_key,
        spatial_size,
        pos=1,
        neg=1,
        num_samples=1,
        image_key="image",
    ):
        super().__init__(keys)
        self.label_key = label_key
        self.cropper = RandCropByPosNegLabeld(
            keys=keys,
            label_key=label_key,
            spatial_size=spatial_size,
            pos=pos,
            neg=neg,
            num_samples=num_samples,
            image_key=image_key,
            image_threshold=0,
            allow_smaller=False,
        )
        self.fallback = RandSpatialCropd(keys=keys, roi_size=spatial_size, random_size=False)

    def __call__(self, data):
        try:
            return self.cropper(data)
        except Exception:
            return self.fallback(data)


class LidcDataset(Dataset):
    def __init__(
        self,
        img_dir,
        mask_dir,
        transforms=None,
        is_train=True,
        val_split=0.1,
        repeats=1,
    ):
        self.img_dir = img_dir
        self.mask_dir = mask_dir
        self.transforms = transforms
        self.repeats = repeats

        # 1. Get all files
        all_images = sorted(glob.glob(os.path.join(img_dir, "*.npy")))
        if len(all_images) == 0:
            raise IOError(f"No files found in {img_dir}")

        # 2. Extract Unique Patient IDs
        patient_files_map = {}
        for img_path in all_images:
            filename = os.path.basename(img_path)
            if "_" in filename:
                patient_id = "_".join(filename.split("_")[:-1])
            else:
                patient_id = os.path.splitext(filename)[0]

            if patient_id not in patient_files_map:
                patient_files_map[patient_id] = []
            patient_files_map[patient_id].append(img_path)

        unique_patients = sorted(list(patient_files_map.keys()))
        num_patients = len(unique_patients)

        # 3. Create the Split (Deterministic)
        val_count = int(num_patients * val_split)
        train_count = num_patients - val_count

        rng = np.random.RandomState(42)
        rng.shuffle(unique_patients)

        if is_train:
            target_patients = unique_patients[:train_count]
        else:
            target_patients = unique_patients[train_count:]

        # 4. Build File List
        self.images = []
        self.masks = []

        for pid in target_patients:
            img_paths = patient_files_map[pid]
            for img_p in img_paths:
                filename = os.path.basename(img_p)
                mask_p = os.path.join(mask_dir, filename)
                if os.path.exists(mask_p):
                    self.images.append(img_p)
                    self.masks.append(mask_p)

        combined = list(zip(self.images, self.masks))
        rng.shuffle(combined)
        self.images, self.masks = zip(*combined)

        self.images = list(self.images)
        self.masks = list(self.masks)

    def __len__(self):
        return len(self.images) * self.repeats

    def __getitem__(self, idx):
        actual_idx = idx % len(self.images)
        img_path = self.images[actual_idx]
        mask_path = self.masks[actual_idx]
        try:
            img = np.load(img_path, mmap_mode="r")
            mask = np.load(mask_path, mmap_mode="r")

            # Filter noise < 5 voxels
            if mask.sum() > 0 and mask.sum() < 5:
                mask = np.zeros_like(mask)
            if img.ndim == 3:
                img = img[np.newaxis, ...]
            elif img.ndim > 4:
                img = np.squeeze(img)
            if img.ndim == 3:
                img = img[np.newaxis, ...]

            if mask.ndim == 3:
                mask = mask[np.newaxis, ...]
            elif mask.ndim > 4:
                mask = np.squeeze(mask)
            if mask.ndim == 3:
                mask = mask[np.newaxis, ...]

        except Exception as e:
            print(f"Error loading {img_path}: {e}")
            img = np.zeros((1, 128, 128, 128), dtype=np.float32)
            mask = np.zeros((1, 128, 128, 128), dtype=np.uint8)
        data = {"image": img, "label": mask}
        if self.transforms:
            try:
                data = self.transforms(data)
                if isinstance(data, list):
                    data = data[0]
            except Exception as e:
                print(f"Transform Error on {img_path}: {e}")
                data = {
                    "image": torch.zeros((1, 128, 128, 128)),
                    "label": torch.zeros((1, 128, 128, 128)),
                }
        return data


# -------------------------------------------------------------------------
# 2. TRANSFORM PIPELINES (CPU vs GPU)
# -------------------------------------------------------------------------


def get_train_transforms_cpu():
    """
    EXTREME LIGHTWEIGHT: CPU only crops.
    It touches as few pixels as possible.
    """
    return Compose(
        [
            # Pad and Crop (Geometry only)
            SpatialPadd(
                keys=["image", "label"],
                spatial_size=(128, 128, 128),
                method="symmetric",
                mode="constant",
            ),
            SafeRandCropByPosNegLabeld(
                keys=["image", "label"],
                label_key="label",
                spatial_size=(128, 128, 128),
                pos=2,
                neg=1,
                num_samples=1,
                image_key="image",
            ),
            # Meta/Type housekeeping
            Lambdad(keys=["image", "label"], func=robust_make_writable),
            EnsureTyped(keys=["image", "label"], track_meta=False),
            # REMOVED: ScaleIntensityRanged (Moved to GPU)
        ]
    )


def get_gpu_transforms():
    """
    HEAVYWEIGHT: Scaling + Augmentations.
    """
    return Compose(
        [
            # [MOVED HERE] H100 normalizes pixels instantly
            ScaleIntensityRanged(
                keys=["image"],
                a_min=-1000,
                a_max=500,
                b_min=-1.0,
                b_max=1.0,
                clip=True,
            ),
            # Existing Augmentations...
            RandAffined(
                keys=["image", "label"],
                prob=0.15,
                rotate_range=(np.pi / 12, np.pi / 12, np.pi / 12),
                scale_range=(0.1, 0.1, 0.1),
                padding_mode="border",
                mode=["bilinear", "nearest"],
            ),
            RandRotate90d(keys=["image", "label"], prob=0.5, spatial_axes=(0, 2)),
            RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=0),
            RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=1),
            RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=2),
            RandZoomd(
                keys=["image", "label"],
                min_zoom=0.85,
                max_zoom=1.15,
                mode=["trilinear", "nearest"],
                prob=0.3,
                padding_mode="edge",
            ),
            RandShiftIntensityd(keys=["image"], offsets=0.1, prob=0.5),
            RandGaussianNoised(keys=["image"], prob=0.15, mean=0.0, std=0.1),
            RandGaussianSmoothd(
                keys=["image"],
                sigma_x=(0.5, 1.0),
                sigma_y=(0.5, 1.0),
                sigma_z=(0.5, 1.0),
                prob=0.15,
            ),
        ]
    )


def get_val_transforms():
    return Compose(
        [
            SpatialPadd(
                keys=["image", "label"],
                spatial_size=(128, 128, 128),
                method="symmetric",
                mode="constant",
            ),
            Lambdad(keys=["image", "label"], func=robust_make_writable),
            EnsureTyped(keys=["image", "label"], track_meta=False),
            ScaleIntensityRanged(
                keys=["image"],
                a_min=-1000,
                a_max=500,
                b_min=-1.0,
                b_max=1.0,
                clip=True,
            ),
        ]
    )


# -------------------------------------------------------------------------
# 3. UTILS & EMA
# -------------------------------------------------------------------------


class ModelEMA:
    def __init__(self, model, decay=0.999):
        self.module = copy.deepcopy(model.module if isinstance(model, DDP) else model)
        self.module.eval()
        self.decay = decay

    def update(self, model):
        with torch.no_grad():
            msd = model.module.state_dict() if isinstance(model, DDP) else model.state_dict()
            for k, v in self.module.state_dict().items():
                if k in msd:
                    v.copy_(self.decay * v + (1.0 - self.decay) * msd[k])


def setup_ddp():
    if "RANK" in os.environ and "WORLD_SIZE" in os.environ:
        dist.init_process_group(backend="nccl", timeout=datetime.timedelta(minutes=60))
        torch.cuda.set_device(int(os.environ["LOCAL_RANK"]))
    else:
        print("Debug Mode: Single GPU")
        os.environ["RANK"] = "0"
        os.environ["WORLD_SIZE"] = "1"
        os.environ["MASTER_ADDR"] = "localhost"
        os.environ["MASTER_PORT"] = "12355"
        dist.init_process_group(backend="nccl")
        torch.cuda.set_device(0)


def cleanup_ddp():
    dist.destroy_process_group()


def clean_small_objects_gpu(mask_tensor, min_size=8):
    if mask_tensor.ndim == 4:
        mask_tensor = mask_tensor.unsqueeze(1)

    kernel_size = 3
    kernel = torch.ones(
        (1, 1, kernel_size, kernel_size, kernel_size),
        device=mask_tensor.device,
        dtype=torch.float32,
    )
    padding = (kernel_size - 1) // 2
    mask_float = mask_tensor.float()

    eroded = (F.conv3d(mask_float, kernel, padding=padding) >= 5).float()
    dilated = (F.conv3d(eroded, kernel, padding=padding) > 0).float()
    return dilated.long()


def worker_init_fn(worker_id):
    worker_seed = torch.initial_seed() % 2**32
    np.random.seed(worker_seed)
    random.seed(worker_seed)
    try:
        import cv2

        cv2.setNumThreads(0)
    except ImportError:
        pass


class CSVLogger:
    def __init__(self, filepath, fieldnames):
        self.filepath = filepath
        self.fieldnames = fieldnames
        if not os.path.exists(filepath) or os.stat(filepath).st_size == 0:
            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

    def log(self, data_dict):
        with open(self.filepath, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writerow(data_dict)


# -------------------------------------------------------------------------
# 4. MAIN LOOP
# -------------------------------------------------------------------------


def main():
    setup_ddp()
    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    device = torch.device(f"cuda:{local_rank}")

    # --- HYPERPARAMETERS ---
    BATCH_SIZE = 16
    ACCUM_STEPS = 1
    STEPS_PER_EPOCH = 250
    EPOCHS = 500
    LR = 1e-4
    VAL_INTERVAL = 5

    DATA_IMG_DIR = "./data-preprocessed/images"
    DATA_MASK_DIR = "./data-preprocessed/masks"
    SAVE_DIR = "./checkpoints"
    LOG_FILE = "./training_log.csv"
    LATEST_CHECKPOINT = os.path.join(SAVE_DIR, "latest.pth")
    TENSORBOARD_DIR = os.path.join(SAVE_DIR, "tensorboard")

    if rank == 0:
        os.makedirs(SAVE_DIR, exist_ok=True)
        os.makedirs(TENSORBOARD_DIR, exist_ok=True)
        logger = CSVLogger(
            LOG_FILE,
            fieldnames=[
                "epoch",
                "train_loss",
                "val_loss",
                "val_dice_neg",
                "val_dice_pos",
                "val_fp_rate",
                "lr",
                "time_sec",
            ],
        )
        writer = SummaryWriter(log_dir=TENSORBOARD_DIR)

    dist.barrier()

    # --- DATASET SIZING ---
    if rank == 0:
        temp_ds = LidcDataset(DATA_IMG_DIR, DATA_MASK_DIR, is_train=True, val_split=0.1)
        num_train_files = len(temp_ds.images)
        print(f"Total Train Files Found: {num_train_files}")
    else:
        num_train_files = 0

    size_tensor = torch.tensor([num_train_files], device=device)
    dist.broadcast(size_tensor, src=0)
    num_train_files = size_tensor.item()

    world_size = dist.get_world_size()
    files_per_gpu = num_train_files / world_size
    target_images_per_gpu = STEPS_PER_EPOCH * BATCH_SIZE
    repeats_needed = math.ceil(target_images_per_gpu / max(1, files_per_gpu))

    if rank == 0:
        print(f"Dataset Size: {num_train_files} | Target Steps: {STEPS_PER_EPOCH}")
        print(f"Repeating dataset {repeats_needed} times per epoch.")

    # 1. Initialize CPU Loader (Lightweight)
    cpu_transforms = get_train_transforms_cpu()

    train_ds = LidcDataset(
        DATA_IMG_DIR,
        DATA_MASK_DIR,
        transforms=cpu_transforms,
        is_train=True,
        val_split=0.1,
        repeats=repeats_needed,
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=BATCH_SIZE,
        sampler=DistributedSampler(train_ds, shuffle=True),
        # [TUNED]
        num_workers=8,  # Decreased from 16 to reduce CPU thrashing
        prefetch_factor=4,  # Increased from 2 to buffer more batches ahead
        pin_memory=True,
        persistent_workers=True,
        worker_init_fn=worker_init_fn,
    )

    val_ds = LidcDataset(
        DATA_IMG_DIR,
        DATA_MASK_DIR,
        transforms=get_val_transforms(),
        is_train=False,
        val_split=0.1,
    )

    val_loader = DataLoader(
        val_ds,
        batch_size=1,
        sampler=DistributedSampler(val_ds, shuffle=False),
        num_workers=2,
        pin_memory=True,
        persistent_workers=True,
        worker_init_fn=worker_init_fn,
    )

    # 2. Initialize GPU Pipeline (Heavyweight)
    gpu_transforms = get_gpu_transforms()

    # --- MODEL & OPTIMIZER ---
    model = UNETR_PP_H100(
        in_channels=1,
        out_channels=2,
        img_size=(128, 128, 128),
        base_filters=64,  # [SOTA] Increased capacity
        do_checkpoint=True,
    ).to(device)

    try:
        model = torch.compile(model)
        if rank == 0:
            print(">>> torch.compile(model) ENABLED <<<")
    except Exception as e:
        if rank == 0:
            print(f"torch.compile skipped: {e}")

    model = nn.SyncBatchNorm.convert_sync_batchnorm(model)
    model = DDP(model, device_ids=[local_rank], output_device=local_rank)

    ema_model = ModelEMA(model, decay=0.999)
    loss_func = RobustSegmentationLoss(deep_supervision_weights=[1.0, 0.2]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-2)

    warmup_epochs = 50
    scheduler = SequentialLR(
        optimizer,
        schedulers=[
            LinearLR(optimizer, start_factor=0.01, end_factor=1.0, total_iters=warmup_epochs),
            CosineAnnealingLR(optimizer, T_max=EPOCHS - warmup_epochs, eta_min=1e-6),
        ],
        milestones=[warmup_epochs],
    )

    scaler = GradScaler("cuda")

    dice_metric = DiceMetric(include_background=True, reduction="mean_batch", get_not_nans=False)
    fp_metric = ConfusionMatrixMetric(
        include_background=False,
        metric_name="fpr",
        reduction="mean_batch",
        get_not_nans=False,
    )
    post_pred = Compose([AsDiscrete(argmax=True, to_onehot=2)])
    post_label = Compose([AsDiscrete(to_onehot=2)])

    best_dice_pos = 0.0
    start_epoch = 1

    # --- RESUME ---
    if os.path.exists(LATEST_CHECKPOINT):
        map_location = {"cuda:%d" % 0: "cuda:%d" % local_rank}
        checkpoint = torch.load(LATEST_CHECKPOINT, map_location=map_location)
        model.module.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optim"])
        scaler.load_state_dict(checkpoint["scaler"])

        if "ema_state_dict" in checkpoint:
            ema_model.module.load_state_dict(checkpoint["ema_state_dict"])

        start_epoch = checkpoint["epoch"] + 1
        best_dice_pos = checkpoint.get("best_dice", 0.0)

        for param_group in optimizer.param_groups:
            param_group["lr"] = LR
        for _ in range(1, start_epoch):
            scheduler.step()
        if rank == 0:
            print(f">>> RESUMING from Epoch {start_epoch-1} (Best Dice: {best_dice_pos:.4f}) <<<")

    # --- LOOP ---
    for epoch in range(start_epoch, EPOCHS + 1):
        model.train()
        train_loader.sampler.set_epoch(epoch)
        epoch_loss = 0.0
        step = 0
        epoch_start = time.time()

        optimizer.zero_grad()
        if rank == 0:
            pbar = tqdm(total=STEPS_PER_EPOCH, desc=f"Epoch {epoch}/{EPOCHS}")

        for i, batch in enumerate(train_loader):
            if i >= STEPS_PER_EPOCH:
                break

            # 1. Move Clean/Cropped Data to GPU
            images = batch["image"].to(device, non_blocking=True)
            labels = batch["label"].to(device, non_blocking=True)

            # 2. [FIXED] Apply Heavy Augmentations individually per item in batch
            with torch.no_grad():
                batch_dict = {"image": images, "label": labels}
                batch_gpu = apply_transforms_batched(batch_dict, gpu_transforms)
                images, labels = batch_gpu["image"], batch_gpu["label"]

                # 3. Clean small objects
                labels = clean_small_objects_gpu(labels, min_size=8)

            with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                outputs = model(images)
                loss = loss_func(outputs, labels)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad()

            ema_model.update(model)

            loss_val = loss.item()
            epoch_loss += loss_val
            step += 1
            if rank == 0:
                pbar.update(1)
                pbar.set_postfix({"loss": f"{loss_val:.4e}"})

        if rank == 0:
            pbar.close()

        epoch_loss_tensor = torch.tensor(epoch_loss / step if step > 0 else 0, device=device)
        dist.all_reduce(epoch_loss_tensor, op=dist.ReduceOp.SUM)
        avg_train_loss = epoch_loss_tensor.item() / dist.get_world_size()

        # --- VALIDATION (USING EMA MODEL) ---
        val_dice_neg, val_dice_pos, val_fp_rate, avg_val_loss = -1.0, -1.0, -1.0, 0.0

        if epoch % VAL_INTERVAL == 0 or epoch == 1:
            ema_model.module.eval()
            if rank == 0:
                print("Validating (EMA)...")

            val_loss_accum = 0.0
            val_steps = 0
            local_val_count = 0
            vis_image, vis_label, vis_pred = None, None, None

            with torch.no_grad():
                for idx, val_batch in enumerate(val_loader):
                    val_images = val_batch["image"].to(device, non_blocking=True)
                    val_labels = val_batch["label"].to(device, non_blocking=True)

                    with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                        # [SOTA FIX] Gaussian Blending + 25% Overlap
                        val_outputs = sliding_window_inference(
                            inputs=val_images,
                            roi_size=(128, 128, 128),
                            sw_batch_size=8,
                            predictor=ema_model.module,
                            overlap=0.25,
                            mode="gaussian",
                        )
                        val_logits = val_outputs[0] if isinstance(val_outputs, list) else val_outputs

                        current_val_loss = loss_func(val_logits, val_labels)
                        val_loss_accum += current_val_loss.item()
                        val_steps += 1

                    val_outputs_list = decollate_batch(val_logits)
                    val_labels_list = decollate_batch(val_labels)
                    val_outputs_convert = [post_pred(i) for i in val_outputs_list]
                    val_labels_convert = [post_label(i) for i in val_labels_list]

                    if idx == 0 and rank == 0:
                        mid_idx = val_images.shape[4] // 2
                        vis_image = val_images[0, 0, :, :, mid_idx].cpu().float()
                        vis_label = val_labels_convert[0][1, :, :, mid_idx].cpu().float()
                        vis_pred = val_outputs_convert[0][1, :, :, mid_idx].cpu().float()

                    if val_labels_convert[0].sum() > 0:
                        dice_metric(y_pred=val_outputs_convert, y=val_labels_convert)
                        fp_metric(y_pred=val_outputs_convert, y=val_labels_convert)
                        local_val_count += 1

            local_dice_sum = dice_metric.aggregate() * local_val_count
            local_fp_sum = fp_metric.aggregate() * local_val_count

            stats_tensor = torch.zeros(4, device=device)
            if local_val_count > 0:
                stats_tensor[0], stats_tensor[1] = local_dice_sum[0], local_dice_sum[1]
                stats_tensor[2] = local_fp_sum[0]
            stats_tensor[3] = local_val_count

            dist.all_reduce(stats_tensor, op=dist.ReduceOp.SUM)
            global_count = stats_tensor[3].item()

            if global_count > 0:
                val_dice_neg = (stats_tensor[0] / global_count).item()
                val_dice_pos = (stats_tensor[1] / global_count).item()
                val_fp_rate = (stats_tensor[2] / global_count).item()
            else:
                val_dice_neg = val_dice_pos = val_fp_rate = -1.0

            dice_metric.reset()
            fp_metric.reset()

            val_loss_tensor = torch.tensor(val_loss_accum / val_steps if val_steps > 0 else 0, device=device)
            dist.all_reduce(val_loss_tensor, op=dist.ReduceOp.SUM)
            avg_val_loss = val_loss_tensor.item() / dist.get_world_size()

            if rank == 0 and vis_image is not None:
                vis_image = (vis_image + 1.0) / 2.0
                writer.add_image("Val/Image", vis_image.unsqueeze(0), epoch)
                writer.add_image("Val/Label", vis_label.unsqueeze(0), epoch)
                writer.add_image("Val/Pred", vis_pred.unsqueeze(0), epoch)

        scheduler.step()

        if rank == 0:
            current_lr = optimizer.param_groups[0]["lr"]
            epoch_time = time.time() - epoch_start

            msg = f"Ep {epoch} | T_Loss: {avg_train_loss:.4f} | V_Loss: {avg_val_loss:.4f} | FP: {val_fp_rate:.4f}"
            if val_dice_pos != -1:
                msg += f" | Dice (EMA): {val_dice_pos:.4f}"
            print(msg)

            writer.add_scalar("Loss/Train", avg_train_loss, epoch)
            writer.add_scalar("Loss/Val", avg_val_loss, epoch)
            writer.add_scalar("Metric/DicePos", val_dice_pos, epoch)
            writer.add_scalar("Metric/FPR", val_fp_rate, epoch)
            writer.add_scalar("Param/LR", current_lr, epoch)

            logger.log(
                {
                    "epoch": epoch,
                    "train_loss": f"{avg_train_loss:.6f}",
                    "val_loss": f"{avg_val_loss:.6f}",
                    "val_dice_neg": f"{val_dice_neg:.6f}",
                    "val_dice_pos": f"{val_dice_pos:.6f}",
                    "val_fp_rate": f"{val_fp_rate:.6f}",
                    "lr": f"{current_lr:.6f}",
                    "time_sec": f"{epoch_time:.2f}",
                }
            )

            checkpoint = {
                "epoch": epoch,
                "model": model.module.state_dict(),
                "ema_state_dict": ema_model.module.state_dict(),
                "optim": optimizer.state_dict(),
                "scaler": scaler.state_dict(),
                "best_dice": best_dice_pos,
            }
            torch.save(checkpoint, os.path.join(SAVE_DIR, "latest.pth"))

            if val_dice_pos > best_dice_pos:
                best_dice_pos = val_dice_pos
                torch.save(checkpoint, os.path.join(SAVE_DIR, "best.pth"))
                print(f">>> New Best Dice (EMA): {best_dice_pos:.4f} <<<")

    cleanup_ddp()


if __name__ == "__main__":
    main()


