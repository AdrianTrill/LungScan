## Experiment Full Dataset — Documents and History

This folder is the running log of experiment decisions, fixes, and training configurations.

---

## Document Index

- **[`experiment-summary.md`](./experiment-summary.md)**
  - Main consolidated report: UNETR-PP optimization (token reduction + stability), class-imbalance strategy, SwinUNETR H100 fine-tuning, and the speed-focused SegResNet experiment targeting SOTA in 8 hours.

- **[`lidc-idri-experiment-log.md`](./lidc-idri-experiment-log.md)**
  - Chronological LIDC-IDRI experiment log capturing training pivots (loss/architecture/data sampling) plus current qualitative examples (see `assets/`).

- **[`unetrpp_h100_train.py`](./unetrpp_h100_train.py)**
  - Archived UNETR-PP H100 training script (DDP + BF16 + EMA + CPU/GPU transform split).

- **[`unetrpp_h100_train_notes.md`](./unetrpp_h100_train_notes.md)**
  - Short engineering notes explaining key stability fixes (env vars, caches), per-item GPU transforms, and validation setup.

- **[`nndetection-environment-data-migration.md`](./nndetection-environment-data-migration.md)**
  - Environment + data migration report: `nnDetection` build failures on modern local toolchains and the resolution via the repo Dockerfile, A100 migration, and LUNA16 dataset adoption.

---

## Logs

- **Real log**: `training_log_overfitting.csv`
- **Derived demo/target curve**: **[`training_log_overfitting_with_target.csv`](./training_log_overfitting_with_target.csv)**
  - The original metrics remain in `training_log_overfitting.csv`.

---

## Timeline (High-Level History)

- **UNETR-PP phase (LIDC-IDRI)**:
  - Identified transformer token-count OOM bottleneck.
  - Implemented stride-4 patch embedding to reduce tokens and unlock throughput.
  - Stabilized training with AdamW + warmup/cosine scheduling and class-imbalance–aware strategies.
  - Captured additional run-by-run decisions and outcomes in `lidc-idri-experiment-log.md`.

- **SwinUNETR fine-tuning phase (H100)**:
  - Shifted to fine-tuning SSL-pretrained SwinUNETR to reduce convergence time.
  - Applied bfloat16 autocast + `torch.compile` + data pipeline tuning.
  - Fixed runtime issues (UID lookup, MONAI API mismatch, transform spatial-dims bug).

- **Speed/SOTA sprint (H100, 8-hour budget)**:
  - Switched to a slim SegResNetDS configuration and reduced input size.
  - Adopted virtual epochs + OneCycleLR (“super-convergence”) to accelerate learning.
  - Hardened the run against RAM pressure, NaN/DDP deadlocks, and restart loss via full checkpoint resumption.

- **nnDetection migration (LUNA16 + Dockerfile + A100)**:
  - Local build failures due to dependency drift in legacy `nnDetection` (v0.1).
  - Standardized the environment using the repo Dockerfile and migrated experiments to LUNA16 for reproducible baselines.


