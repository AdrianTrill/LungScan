# Reproducing Paper Results

This guide provides step-by-step instructions to reproduce all experiments and results presented in the paper.

## 📋 Prerequisites

1. Complete the [SETUP.md](./SETUP.md) instructions
2. Download and preprocess the LIDC-IDRI dataset
3. Ensure you have access to NVIDIA H100 or A100 GPUs (2 GPUs recommended)

## 🎯 Quick Reproduction

To reproduce all main results:

```bash
# Run all experiments
bash scripts/run_all_experiments.sh

# Generate paper figures
python research/notebooks/generate_paper_figures.py
```

## 📊 Individual Experiments

### Experiment 1: UNETR++ Baseline

**Goal**: Train UNETR++ from scratch on LIDC-IDRI

```bash
cd research/training
python train_unetr_pp.py --config ../configs/unetr_pp_baseline.yaml
```

**Expected Results**:
- Training time: ~24-36 hours on 2x H100
- Final Positive Dice: ~0.75-0.80
- Final Negative Dice: ~0.98+

**Checkpoints**: Saved to `research/experiments/unetr_pp/checkpoints/`

---

### Experiment 2: SwinUNETR with SSL Pretraining

**Goal**: Fine-tune SwinUNETR using self-supervised pretrained weights

```bash
cd research/training
python train_swin_unetr.py --config ../configs/swin_unetr_ssl.yaml
```

**Expected Results**:
- Training time: ~8-12 hours on 2x H100 (90% faster than from scratch)
- Final Positive Dice: ~0.80-0.83
- Convergence: Stable from epoch 10

**Key Features**:
- Uses bfloat16 precision
- torch.compile optimization
- SSL weights from 5,050 CT scans

---

### Experiment 3: Speed-Optimized SegResNet (8-Hour Goal)

**Goal**: Achieve near-SOTA performance in 8 hours

```bash
cd research/training
python train_segresnet_speed.py --config ../configs/segresnet_speed.yaml
```

**Expected Results**:
- Training time: ~8 hours on 2x H100
- Final Positive Dice: ~0.78-0.82
- Iterations/sec: ~3-4 it/s

**Optimizations**:
- Virtual epochs (6K samples/epoch)
- OneCycleLR scheduler
- GPU-native augmentations
- 96×96×96 patches

---

### Experiment 4: nnUNet Comparison

**Goal**: Benchmark against nnUNet baseline

```bash
cd apps/MIRPR-full-pipeline/scripts/training
python run_nnunet_experiment.py
```

**Expected Results**:
- Training automatically configured by nnUNet
- Comparable or slightly lower Dice than custom models
- Longer training time

---

## 📈 Generating Paper Figures

After training all models:

```bash
# Launch Jupyter
jupyter notebook

# Open and run:
# - research/notebooks/01_dataset_exploration.ipynb
# - research/notebooks/02_baseline_analysis.ipynb
# - research/notebooks/03_model_comparison.ipynb
# - research/notebooks/04_error_analysis.ipynb
```

Or use the automated script:

```bash
python scripts/generate_all_figures.py --output paper/figures/
```

**Generated Figures**:
- `architecture_comparison.png` - Model architectures
- `training_curves.png` - Loss and Dice over epochs
- `results_table.png` - Performance comparison
- `inference_examples.png` - Qualitative results
- `error_analysis.png` - Failure case analysis

---

## 🔍 Experiment Details

### Configuration Files

All hyperparameters are specified in YAML configs:

```
research/
├── configs/
│   ├── unetr_pp_baseline.yaml
│   ├── swin_unetr_ssl.yaml
│   ├── segresnet_speed.yaml
│   └── nnunet_full.yaml
```

### Data Splits

The exact train/val/test splits used in the paper are in:
```
data/splits/patient_level_splits.json
```

**Split Statistics**:
- Training: ~800 patients
- Validation: ~150 patients  
- Test: ~100 patients

### Random Seeds

All experiments use fixed seeds for reproducibility:
```python
SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)
```

---

## ✅ Validation

### Verify Results

```bash
# Evaluate all checkpoints
python research/evaluation/benchmark.py \
    --checkpoints checkpoints/unetr_pp_best.pth checkpoints/swin_unetr_ssl.pth \
    --data-dir data/processed \
    --output results_validation.json

# Compare with paper results
python scripts/compare_results.py --paper-results paper/tables/main_results.csv
```

### Expected Metrics

| Model | Pos Dice | Neg Dice | Training Time (H100×2) |
|-------|----------|----------|------------------------|
| UNETR++ | 0.78 ± 0.02 | 0.98 ± 0.01 | 24-36h |
| SwinUNETR | 0.82 ± 0.01 | 0.99 ± 0.01 | 8-12h |
| SegResNet (Speed) | 0.80 ± 0.02 | 0.98 ± 0.01 | ~8h |
| nnUNet | 0.76 ± 0.03 | 0.98 ± 0.01 | ~48h |

---

## 🐛 Troubleshooting

### Out of Memory

If you encounter OOM errors:

```yaml
# In your config file, reduce:
batch_size: 4  # from 6 or 8
patch_size: [80, 80, 80]  # from [96, 96, 96]
```

### Different Hardware

For V100 or A100 GPUs:
- Expect 1.5-2× longer training times
- May need to reduce batch size
- Disable torch.compile if not supported

### Results Not Matching

Small variations (<2% Dice) are normal due to:
- Different GPU architectures
- PyTorch version differences
- Numerical precision variations

For exact reproduction, use:
- PyTorch 2.0+
- CUDA 11.8
- Same GPU type (H100)

---

## 📊 Ablation Studies

To reproduce ablation experiments (Appendix):

```bash
# Loss function ablation
python research/training/ablation_loss.py

# Architecture ablation  
python research/training/ablation_architecture.py

# Data augmentation ablation
python research/training/ablation_augmentation.py
```

---

## 💾 Model Checkpoints

Pretrained checkpoints are available:

```bash
# Download from repository (see checkpoints/README.md)
wget https://example.com/checkpoints/unetr_pp_best.pth
wget https://example.com/checkpoints/swin_unetr_ssl.pth
wget https://example.com/checkpoints/segresnet_speed.pth
```

To use for inference without retraining:

```python
from research.models import SwinUNETR
model = SwinUNETR.load_from_checkpoint('checkpoints/swin_unetr_ssl.pth')
```

---

## 📧 Support

For reproduction issues:
- Check GitHub Issues
- Contact: [Team Email]
- Provide: config file, error logs, GPU specs

## 🎓 Citation

If you use our code or reproduce our results:

```bibtex
@software{lungscan_assist_2026,
  title={LungScan Assist: AI-Powered Lung Nodule Detection},
  author={Bocra, Razvan and Boroica, Marius and Deaconu, Mihai and Hordoan, Roberto},
  year={2026},
  url={https://github.com/LauraDiosan-CS/projects-in-silico-diagnostics}
}
```
