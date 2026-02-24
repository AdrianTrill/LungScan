# Theoretical Report: Lung Nodule Segmentation Project

## 1. Project Overview
This project focuses on developing a production-ready system for AI-powered lung nodule detection and analysis. The core task is 3D semantic segmentation of pulmonary nodules from CT scans using the LIDC-IDRI dataset.

## 2. Methodology & Algorithm Selection
We employed state-of-the-art 3D architectures, specifically:
- **3D UNETR++**: A Vision Transformer-based architecture designed for medical image segmentation, capturing long-range spatial dependencies.
- **SwinUNETR**: A hierarchical Vision Transformer fine-tuned using self-supervised weights from 5,050 CT scans.
- **SegResNetDS**: A high-efficiency CNN-based architecture used for speed-focused optimization.

## 3. Key Challenges and Solutions

### 3.1. Extreme Class Imbalance
Pulmonary nodules occupy a tiny fraction of the lung volume (~0.0057% of voxels).
- **Solution**: Implemented `WeightedRandomSampler` to balance positive and negative patches in each batch. Used a combined `DiceLoss_plus_CE_Loss` with class weights (e.g., 1:750) to penalize misclassifications of nodules.

### 3.2. Data Leakage
Standard random splits allowed patches from the same patient to appear in both training and validation sets.
- **Solution**: Developed `create_patient_level_stratified_split` to ensure patient-level separation.

### 3.3. Numerical Instability ("NaN Crisis")
Mixed-precision training combined with un-normalized data caused gradient overflows.
- **Solution**: Enabled full Z-score normalization, implemented gradient clipping (`clip_grad_norm_`), and ensured stable loss computation by casting outputs to float32.

### 3.4. Architectural Bottlenecks
Initial Transformer implementations suffered from excessive token counts (2M+ tokens for 128³ volumes), leading to OOM.
- **Solution**: Implemented **Stride-4 Patch Embedding**, reducing token count by ~500x. Enabled **gradient checkpointing** and **torch.compile** to maximize throughput on NVIDIA H100 GPUs.

## 4. Experimental Results & Optimization

### 4.1. UNETR++ Optimization
Through iterative refinement, we achieved stable training by switching to **AdamW** with warmup and cosine annealing schedules. The model successfully transitioned from an "all-zero" prediction regime to fine-grained boundary refinement.

### 4.2. SwinUNETR Fine-Tuning
By leveraging SSL-pretrained weights, we drastically reduced convergence time (estimated ~90% reduction). Stability fixes included resolving MONAI API mismatches and handling container-specific environment variables for `torch.compile`.

### 4.3. Speed-Focused Sprint (The 8-Hour Goal)
Using a slim SegResNet configuration and "virtual epochs," we optimized the pipeline to target near-SOTA performance (~0.80-0.83 Dice) within an 8-hour training window on 2x H100 GPUs. Key optimizations included GPU-native augmentations and full checkpoint resumption.

## 5. Summary of Development Phases
1. **Data Preprocessing**: Handling small scans via padding and adjusting HU filtering to preserve healthy lung tissue.
2. **Metric Refinement**: Separating `val_pos_dice` and `val_neg_dice` to accurately track performance on nodules.
3. **Generalization**: Integrating `torchio` for robust 3D augmentations and adding `weight_decay` to prevent overfitting.

## 6. Conclusion
The project has successfully moved from initial architectural hurdles to a stable, high-performance pipeline. The current system is optimized for H100 hardware, resilient to common medical imaging training pitfalls, and ready for full-scale dataset training.
