## LIDC-IDRI Lung Nodule Segmentation — Experiment Log

This document tracks the progression of training strategies, failures, and the engineering decisions that led to a working model for **3D lung nodule segmentation** using **UNETR++**.

---

## 1. Initial Baseline (Pure Transformer)

- **Architecture**: Standard UNETR++ (pure Transformer encoder)
- **Data**: Offline patches (static crops)
- **Loss**: `DiceCELoss`
- **Result**: Failed (Dice plateau ~0.15)

### Analysis

- The pure Transformer struggled with **cold start**: learning edges reliably without large-scale data is difficult.
- Static patches caused **overfitting**: train loss dropped while validation Dice stayed stagnant.
  - The model appeared to memorize patch coordinates rather than learning anatomy.

---

## 2. The “Elegant” Fix (Hybrid + Focal Loss)

- **Architecture**: Hybrid UNETR++ (ResNet3D stem + Transformer deeper layers) to improve edge detection
- **Data**: Dynamic online sampling (full volumes + random crops) to prevent memorization
- **Loss**: `DiceFocalLoss` (γ = 4.0)
- **Result**: Failed (Dice 0.0000)

### Analysis

- γ = 4.0 was too aggressive.
- It suppressed gradients from medium-confidence predictions so heavily that the model converged to predicting **background everywhere**.
- Validation loss stuck at ~0.998 (“background trap”).

---

## 3. The “Standard” Fix (Focal Loss γ = 2.0)

- **Configuration**: `DiceFocalLoss` with γ = 2.0
- **Result**: Failed (Dice 0.0000)

### Analysis

Even with standard focal loss, the class imbalance (~2000:1 background:nodule) overwhelmed the gradients: the nodule signal was mathematically drowned out by the background volume.

---

## 4. The “Nuclear” Option (Current LIDC Run)

- **Architecture**: Hybrid UNETR++ (same as above)
- **Loss**: Weighted cross-entropy (positive weight = 100.0) + Dice
- **Logic**: Force the model to value nodules 100× more than background
- **Result**: **Success** (early breakout; model no longer stuck at all-zeros)

### Current status (as reported)

| Metric (early training) | Value   |
|-------------------------|---------|
| Dice (signal)           | 0.0001  |
| False positives (FP)    | 0.01    |

### Interpretation

- The high penalty broke the “zero prediction paralysis.”
- The model is currently **hallucinating** (higher FP), which is useful early on because it creates a gradient signal to shape the segmentation.

### Next-step strategy

Run until Dice > 0.10, then switch back to focal loss for precision refinement.

---

## 5. Parallel Experiment: Foundation Pretraining (Started)

- **Dataset**: TotalSegmentator (~1,228 CT scans, 104 anatomical classes)
- **Architecture**: Hybrid UNETR++ (same configuration)
- **Goal**: Produce a reusable “medical backbone” checkpoint (e.g., `pretrained_total_seg.pth`) to initialize LIDC training instead of random weights

### Rationale

- **Scale**: ~1.5× larger than LIDC, with dense labels across the body.
- **Context learning**: If the model learns ribs, airway trees, and vessels (common distractors in LIDC), it should better reject them when detecting nodules.

### Status

In progress.

---

## 6. Current Qualitative Results (Examples)

The following are qualitative slices from the visualizer showing input CT, ground-truth mask, and the model prediction. The reported Dice values are those shown in the visualization title for each example.

### Example A — Patient sample 28, slice 125 (Dice 0.5138)

![Patient sample 28 slice 125 — Dice 0.5138](./assets/lidc-qualitative-sample28-slice125-dice0.5138.png)

### Example B — Patient sample 78, slice 55 (Dice 0.6053)

![Patient sample 78 slice 55 — Dice 0.6053](./assets/lidc-qualitative-sample78-slice55-dice0.6053.png)

### Example C — Patient sample 17, slice 100 (Dice 0.2226)

![Patient sample 17 slice 100 — Dice 0.2226](./assets/lidc-qualitative-sample17-slice100-dice0.2226.png)


