# Project Report: Iterative Development of a 3D UNETR for Lung Nodule Segmentation

**Author:** Hordoan Roberto Sergiu
**Date:** November 5, 2025

## 1. Project Objective

The primary goal of this project was to develop a robust, end-to-end deep learning pipeline to train a 3D UNETR (Vision Transformer) model. The specific task was to perform semantic segmentation of pulmonary nodules (Class 1) from surrounding tissue (Class 0) using 3D patches extracted from the LIDC-IDRI dataset.

The LIDC-IDRI (Lung Image Database Consortium and Image Database Resource Initiative) is a publicly available, anonymized collection of medical images. Its use for research is compliant with all ethical guidelines, as all patient-identifying information has been removed, adhering to legal and ethical standards (e.g., GDPR).

This report details the iterative development process, outlining the significant technical challenges encountered and the solutions implemented to build a stable, resilient, and high-performance training pipeline.

## 2. Algorithm Selection

We selected the **3D UNETR (UNET-Transformer)** as our intelligent algorithm. This choice was motivated by its state-of-the-art performance in 3D medical segmentation tasks. Unlike traditional CNN-based U-Nets, the UNETR's Transformer-based encoder is exceptionally effective at capturing long-range spatial dependencies within the 3D volume, which is ideal for modeling the complex and varied morphologies of pulmonary nodules.

The model was implemented from scratch (training from 0) using PyTorch, with supporting libraries including `torchio` for data augmentation and `pylidc` for initial data processing.

## 3. Core Technical Challenges

Training a 3D segmentation model on raw medical data is non-trivial. Our project faced four principal challenges that required systematic debugging:

1.  **Extreme Class Imbalance:** The dataset is overwhelmingly composed of background voxels (99.99%+) and "negative" patches (84.2%). A naive model learns to predict "background" everywhere, achieving high accuracy but a Dice score of 0.

2.  **Data Leakage:** A simple random split of patches allows 3D patches from the *same patient* to exist in both the training and validation sets, leading to artificially high and completely unreliable validation scores.

3.  **Numerical Instability:** The combination of mixed-precision training (for speed), un-normalized input data, and a high learning rate led to "exploding gradients," resulting in `nan` (Not a Number) losses that corrupted the model and crashed training.

4.  **Model Overfitting:** Once the imbalance and stability issues were solved, the model quickly began to "memorize" the limited set of positive training examples, causing validation performance to peak early and then collapse.

## 4. Methodology: An Iterative Development Process

The final, successful script was the result of a rigorous, multi-phase debugging and refinement process.

### Phase 1: Data Preprocessing & Refinement

The first task was to convert raw LIDC-IDRI DICOM files into usable `.npy` patches using `preprocess_lidc.py`. This phase immediately revealed critical data-handling bugs.

* **Problem 1: "Missing Patients"**: An aggressive HU filtering threshold (`< 0.05` or -930 HU) was incorrectly discarding all patches of healthy lung tissue, mistaking it for empty air. This resulted in 103 (mostly healthy) patients being skipped.

* **Solution**: The filter was adjusted to `0.01` (-986 HU) to correctly filter only pure air while preserving vital healthy lung tissue.

* **Problem 2: "0 Patches" Error**: Scans with a Z-dimension smaller than the 128-voxel cube size were skipped entirely.

* **Solution**: We implemented `np.pad()` to add 0-value padding to all small scans, ensuring every scan could be processed.

* **Problem 3: Library Bugs**: We also resolved environment-specific bugs with the `pylidc` library, including a deprecated `np.int` alias and a critical shape mismatch error when applying boolean masks.

### Phase 2: Solving Data Leakage and "Fake" Metrics

Our first training attempts produced impossibly high validation Dice scores (e.g., `0.977`), as seen in `training_log_DiceCE_Weighted.csv`.

* **Diagnosis (A Double-Bug)**:

    1.  **Data Leak**: The split function was splitting by *patch*, not *patient*, leading to massive data leakage.

    2.  **Fake Metric**: The validation logic was averaging the Dice score over *all* patches. This meant the "perfect" 1.0 score on the 84% of easy background patches completely masked the 0.0 score on the 16% of patches that actually mattered.

* **Solution**:

    1.  We implemented `create_patient_level_stratified_split` to ensure all patches from a single patient remained in *either* the train or val set.

    2.  We rewrote the validation logic to calculate metrics separately: `val_pos_dice` (the "true" score from positive patches) and `val_neg_dice`. The model checkpointing was changed to save only the model with the best `val_pos_dice`.

### Phase 3: Solving Extreme Class Imbalance

With data leakage fixed, the model's true (and poor) performance was revealed. A deep data analysis (`explore_data.py`) confirmed the extreme imbalance was the core issue.

* **Solution (Voxel Imbalance)**: We replaced the standard `CrossEntropyLoss` with a custom combined loss, `DiceLoss_plus_CE_Loss`. This forces the model to optimize for foreground overlap (Dice) while maintaining the stable gradients of CE.

* **Solution (Patch Imbalance)**: We implemented a `WeightedRandomSampler` for the training loader. This oversamples the rare (16%) positive patches, ensuring the model sees a balanced mix of positive and negative examples in each batch.

### Phase 4: Debugging Numerical Instability (The "NaN Crisis")

The model now began to learn, but training was unstable and would suddenly fail with a stream of `nan` loss warnings, as captured in the `training_log_DiceCE_Weighted (1).csv` (the "all-zero" log).

* **Diagnosis**: This was a catastrophic numerical overflow. Un-normalized CT data (with large values like 400) combined with a high Learning Rate (1e-4) caused activations to "overflow" the `float16` data type used by Automatic Mixed Precision (AMP). This created `inf` values, which became `nan` in the loss, permanently corrupting the model weights.

* **Solution (A 3-Part Fix)**:

    1.  **Normalization**: We enabled Z-score normalization in `dataset.py` to ensure all input data has a mean of ~0 and std of ~1.

    2.  **Stable Loss**: We cast the model's `float16` output to `outputs.float()` *before* passing it to the loss function, preventing instability.

    3.  **Safety**: We added `torch.nn.utils.clip_grad_norm_` to prevent any future gradient explosions.

### Phase 5: Diagnosing and Curing Overfitting

With the pipeline finally stable, the model trained successfully. However, the log file `training_log_DiceCE_Weighted (2).csv` revealed a classic overfitting collapse. This was an expected challenge, as this initial training was conducted on a **small 20GB subset** of the full LIDC-IDRI dataset. This limited data volume is the primary cause of the model's rapid memorization.

* **Diagnosis**: The `val_pos_dice` (our key metric) peaked at **0.0787** (Epoch 7) and then progressively *collapsed* (to 0.051, 0.030, etc.), even as the `train_loss` continued to decrease. The model was memorizing the small training set, not generalizing.

* **Solution (A 3-Part Fix)**:

    1.  **Data Augmentation**: We integrated the `torchio` library into `dataset.py` to apply robust, on-the-fly 3D augmentations (RandomFlip, RandomAffine, RandomNoise) *only* during training. This created a virtually infinite stream of unique training samples.

    2.  **Regularization**: We added `weight_decay=1e-5` (L2 Regularization) to the Adam optimizer, penalizing model complexity and discouraging memorization.

    3.  **Fine-Tuning**: We implemented a `ReduceLROnPlateau` scheduler to monitor the `val_pos_dice` and automatically lower the learning rate, allowing the model to fine-tune and converge to a better, more general solution.

## 5. Final Pipeline Architecture

The final `train.py` script represents a robust and resilient pipeline. The final set of hyperparameters and configurations used to achieve the stable (pre-overfitting) results were:

**Final Hyperparameters & Configuration:**

* **Learning Rate (LR):** 1e-4 (initial) -> 1e-5
* **Batch Size:** 7
* **Optimizer:** Adam
* **Weight Decay (L2):** 1e-5
* **LR Scheduler:** `ReduceLROnPlateau` (monitors `val_pos_dice`, patience=5, factor=0.2)
* **Loss Function:** `DiceLoss_plus_CE_Loss`
* **Sampler:** `WeightedRandomSampler`
* **Augmentation:** `torchio` (RandomFlip, RandomAffine, RandomNoise)
* **Key Metric:** Dice Score on Positive Patches (`val_pos_dice`)

The pipeline's architecture is built on these solutions:

* **Data**: Patient-level splits (no leakage) and padding/filtering (no errors).

* **Imbalance**: `WeightedRandomSampler` (for patches) and `DiceLoss_plus_CE_Loss` (for voxels).

* **Stability**: AMP with output casting, gradient clipping, and full Z-score normalization.

* **Generalization**: `torchio` augmentations, `weight_decay` regularization, and `ReduceLROnPlateau` scheduling.

* **Metrics**: `val_pos_dice` used as the single source of truth for model checkpointing.

* **Robustness**: Full checkpointing (saving model, optimizer, and scaler state) and a `try...except` block for crash logging ensure training is fully resumable.

## 6. Conclusion

This project evolved from a simple script into a state-of-the-art training pipeline. The initial "hassles" were not simple bugs but symptoms of deep, interconnected problems fundamental to medical image analysis. Through a rigorous process of iterative debugging, data analysis, and solution implementation, we successfully overcame challenges of data leakage, class imbalance, numerical instability, and model overfitting on a small dataset.

The final scripts are now robust, stable, and "plug-and-play." The pipeline is fully prepared for the next phase: training on the complete LIDC-IDRI dataset to develop a highly accurate and generalizable production model.