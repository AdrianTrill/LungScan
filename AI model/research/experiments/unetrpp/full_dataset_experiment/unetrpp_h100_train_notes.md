## UNETR-PP H100 Training Script Notes (`unetrpp_h100_train.py`)

This note explains the main engineering choices and “gotchas” handled by the training script, with a focus on **stability under multi-GPU DDP**, **throughput on H100**, and **MONAI transform correctness**.

---

## What this script is for

- **Task**: 3D lung nodule segmentation (binary foreground vs background) with a UNETR++-style model.
- **Training mode**: Multi-GPU **DDP (NCCL)** with:
  - **EMA (exponential moving average)** evaluation for smoother validation metrics.
  - **bfloat16 mixed precision** for H100 performance and numerical robustness.
  - Optional **`torch.compile`** acceleration (Inductor + Triton caches).

---

## Key stability fixes (why the top of the file matters)

- **Thread caps** (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, etc.)
  - Prevent CPU oversubscription and dataloader thrashing, especially when many workers are used.

- **NCCL async error handling**
  - Uses `TORCH_NCCL_ASYNC_ERROR_HANDLING=1` to surface / handle NCCL issues more reliably.

- **Cache directory pinning**
  - Sets `HOME` and the Inductor/Triton/kernel cache dirs under a local `.cache/` folder.
  - This avoids “who is the user?” cache-location bugs in restricted/containerized environments and makes caching behavior deterministic.

- **Multiprocessing sharing strategy**
  - Attempts `torch.multiprocessing.set_sharing_strategy('file_system')` which can reduce shared-memory issues in high-throughput DDP setups.

---

## Data pipeline design: CPU crops + GPU augments

This is a deliberate split to keep the CPU light while using the GPU for heavy math.

- **CPU transforms (`get_train_transforms_cpu`)**
  - Pads/crops to the training ROI and performs minimal “plumbing” transforms.
  - Intensity scaling is intentionally *not* done on CPU.

- **GPU transforms (`get_gpu_transforms`)**
  - Includes intensity normalization (`ScaleIntensityRanged`) and spatial/intensity augmentations.
  - The motivation is to avoid the dataloader becoming the bottleneck (H100 can apply these quickly).

---

## Critical MONAI transform correctness: per-item transform application

MONAI dictionary transforms are typically written for single samples shaped like **(C, D, H, W)**.

But the dataloader produces batches shaped like **(B, C, D, H, W)**.

To ensure transforms behave correctly (and each item receives its own random augmentation), the script uses:

- **`apply_transforms_batched(...)`**
  - Iterates over `B` and applies transforms item-by-item.
  - Then stacks results back into a batch.

This also avoids the “spatial_dims: 4” failure mode where transforms misinterpret the batch dimension as a spatial axis.

---

## Handling tiny objects / label noise

- **`clean_small_objects_gpu`**
  - Performs a simple erosion/dilation-like cleanup using `conv3d` with a 3×3×3 kernel.
  - Helps reduce label noise and improves training stability when very small blobs appear.

---

## Training loop highlights

- **bfloat16 autocast**
  - `torch.amp.autocast('cuda', dtype=torch.bfloat16)` is used for forward + loss to leverage H100 BF16 acceleration.

- **Gradient scaling + clipping**
  - Uses `GradScaler('cuda')` and clips grads to a max norm of 1.0.
  - This combination improves stability with high-capacity transformer models.

- **Warmup + cosine schedule**
  - `SequentialLR(LinearLR → CosineAnnealingLR)` stabilizes early training and then anneals toward a small LR floor.

- **EMA validation**
  - Validation uses the EMA weights, which tends to reduce metric noise and is often more correlated with “true” generalization.

- **Sliding window inference**
  - Uses MONAI `sliding_window_inference` with gaussian blending (`mode="gaussian"`) and overlap.
  - This reduces boundary artifacts for large 3D volumes.

---

## About the overfitting log file

The repository includes a real log (`training_log_overfitting.csv`).  
If you need a *presentation* curve that reaches a target Dice value, use:

- **`make_demo_training_log.py`** → generates `training_log_overfitting_with_target.csv`

This keeps the original log intact and adds a clearly labeled **demo target curve** column.


