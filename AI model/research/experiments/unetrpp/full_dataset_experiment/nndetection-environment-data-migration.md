## Technical Issue Report: nnDetection Environment and Data Migration

This report documents the environment failures encountered while attempting to run `nnDetection` (v0.1) on a modern local setup, and the steps taken to restore a **reproducible baseline** by switching to the project’s **Dockerfile-based environment** and migrating experiments to **LUNA16**.

---

## 1. Problem Summary

Initial attempts to build `nnDetection` (v0.1) from source inside a local Conda environment failed due to **severe dependency drift**.

- **Context**: The codebase is legacy (circa 2021) and expects older system toolchains and headers.
- **Failure mode**: Incompatibilities with modern Python (3.9+) and GCC environments.
- **Symptoms**:
  - Missing system header: `crypt.h`
  - CUDA header path mismatch / misplaced include paths (e.g., `cuda_runtime.h`)

These issues indicate the local host environment is no longer aligned with the assumptions of the original build system.

---

## 2. Resolution Strategy

To remove host variability and restore reproducibility, we adopted a three-part strategy.

### A. Containerization via the Repository Dockerfile

Instead of patching the local environment, we built and ran `nnDetection` using the **official Dockerfile shipped with the repository**.

- **Why**: Ensures an environment consistent with the authors’ intended stack (e.g., Python 3.8 and compatible CUDA/compiler versions).
- **Outcome**: Eliminates “dependency hell” on the host machine and makes the experiment setup portable and repeatable.

### B. Hardware Migration to A100

We migrated the workload to an **A100 GPU instance**.

- **Why**: Provides strong compatibility with the containerized stack and supplies the memory bandwidth / Ampere features needed for efficient 3D medical detection training.

### C. Dataset Migration to LUNA16

We officially moved experiments to the **LUNA16 (LUng Nodule Analysis 2016)** dataset.

- **Why**:
  - LUNA16 is a standard, well-documented benchmark.
  - It is supported natively by `nnDetection`, reducing preprocessing ambiguity.
  - Enables validation against known baselines and published expectations.

---

## 3. Conclusion

By building the environment from the **provided Dockerfile**, running on **A100 hardware**, and targeting the **LUNA16 dataset**, we resolved installation blockers and established a stable, reproducible baseline for future development and experimentation.


