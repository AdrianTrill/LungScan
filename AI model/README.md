# LungScan Assist: AI-Powered Lung Nodule Detection and Analysis

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red.svg)](https://pytorch.org/)

A research project for **3D lung nodule segmentation** from CT scans using state-of-the-art deep learning architectures. This repository contains both a **production-ready web application** and **comprehensive research experiments** for academic publication.

## 🎯 Project Overview

This monorepo implements multiple approaches to 3D semantic segmentation of pulmonary nodules from the LIDC-IDRI dataset, achieving up to **0.82 Dice score** with only **8-12 hours of training** on H100 GPUs through advanced optimization techniques.

### Key Achievements

- 🚀 **90% Training Time Reduction**: Via self-supervised pretraining (SwinUNETR)
- ⚡ **8-Hour Speed Record**: Near-SOTA performance with optimized SegResNet
- 🎯 **SOTA-Level Accuracy**: 0.82 Dice score on LIDC-IDRI
- 💪 **Production Ready**: Full web application with FastAPI + Next.js 14
- 📊 **Reproducible**: Complete configs, splits, and pretrained checkpoints

### Methods Implemented

| Model | Dice Score | Training Time (H100×2) | Key Feature |
|-------|------------|------------------------|-------------|
| **SwinUNETR** | **0.82** | 8-12h | SSL pretraining (5,050 CT scans) |
| **SegResNet** | 0.80 | ~8h | Speed-optimized, virtual epochs |
| **UNETR++** | 0.78 | 24-36h | Transformer baseline |
| **nnUNet** | 0.76 | ~48h | Auto-configured baseline |

## 🏗️ Repository Structure

```
projects-in-silico-diagnostics/
│
├── 📄 README.md                 # This file
├── 📄 LICENSE                   # MIT License
├── 📄 CITATION.cff              # Citation metadata
│
├── 📁 paper/                    # 📝 Publication materials
│   ├── README.md
│   ├── figures/                 # High-res figures
│   ├── tables/                  # Result tables
│   ├── literature_reviews/      # Paper reviews by team
│   └── *.pdf                    # Documentation
│
├── 📁 docs/                     # 📚 Comprehensive documentation
│   ├── README.md                # Documentation index
│   ├── METHODOLOGY.md           # Theoretical background
│   ├── EXPERIMENTS.md           # Detailed experimental results
│   ├── DATASET.md               # Dataset description
│   ├── SETUP.md                 # Installation guide
│   └── REPRODUCTION.md          # Reproduce paper results
│
├── 📁 data/                     # 💾 Data organization
│   ├── README.md
│   ├── splits/                  # Train/val/test splits
│   │   └── patient_level_splits.json
│   ├── raw/                     # LIDC-IDRI raw data (gitignored)
│   └── processed/               # Preprocessed data (gitignored)
│
├── 📁 checkpoints/              # 🎯 Pretrained models
│   ├── README.md                # Model zoo with download links
│   └── *.pth                    # Model checkpoints (to be added)
│
├── 📁 apps/                     # 🚀 Production application
│   ├── README.md
│   ├── backend/                 # FastAPI backend
│   ├── frontend/                # Next.js 14 frontend
│   └── MIRPR-full-pipeline/     # ML inference pipeline
│
├── 📁 research/                 # 🔬 Research & experiments
│   ├── experiments/             # Organized by model
│   │   ├── unetrpp/
│   │   ├── swinunetr/
│   │   └── segresnet/
│   ├── training/                # Training scripts
│   ├── evaluation/              # Benchmarking tools
│   ├── notebooks/               # Jupyter analysis
│   ├── models/                  # Model architectures
│   └── diagnostic/              # Debug utilities
│
├── 📁 utils/                    # 🛠️ Shared utilities
│   ├── data_utils.py
│   ├── dataset.py
│   └── ...
│
├── 📁 scripts/                  # ⚙️ Automation scripts
│   ├── setup.sh
│   ├── dev.sh
│   └── ...
│
├── 📁 tests/                    # ✅ Unit tests (to be expanded)
│
└── 📁 archive/                  # 🗄️ Legacy code
    ├── early_reports/
    └── logs/
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/LauraDiosan-CS/projects-in-silico-diagnostics.git
cd projects-in-silico-diagnostics

# Create environment
conda create -n lungscan python=3.10
conda activate lungscan

# Install dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```

See [docs/SETUP.md](docs/SETUP.md) for detailed instructions.

### 2. Download Data

1. Register at [TCIA - LIDC-IDRI](https://wiki.cancerimagingarchive.net/display/Public/LIDC-IDRI)
2. Download the dataset (124 GB)
3. Preprocess: `python utils/prepare_dataset.py --input data/raw/LIDC-IDRI --output data/processed`

See [data/README.md](data/README.md) for details.

### 3. Run Production App

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Setup and run
./scripts/setup.sh
./scripts/dev.sh
```

Access:
- **Frontend**: http://localhost:3000
- **Backend API**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs

### 4. Reproduce Research Results

```bash
# Train SwinUNETR (best model)
cd research/training
python train_swin_unetr.py --config ../configs/swin_unetr_ssl.yaml

# Or use pretrained checkpoints
bash scripts/download_pretrained_models.sh
```

See [docs/REPRODUCTION.md](docs/REPRODUCTION.md) for full reproduction guide.

## 📊 Results Summary

### Main Performance Metrics

| Metric | UNETR++ | SwinUNETR | SegResNet | nnUNet |
|--------|---------|-----------|-----------|--------|
| **Positive Dice** | 0.78 | **0.82** | 0.80 | 0.76 |
| **Negative Dice** | 0.98 | 0.99 | 0.98 | 0.98 |
| **Training Time** | 24-36h | **8-12h** | **~8h** | ~48h |
| **Parameters** | 65M | 62M | 25M | Varies |

*All experiments on 2× NVIDIA H100 GPUs*

### Key Innovations

1. **Extreme Class Imbalance Solution**
   - Weighted Random Sampling
   - Combined Dice + Weighted CE Loss (1:750 ratio)
   - Patient-level stratified splits

2. **Numerical Stability**
   - Z-score normalization
   - Gradient clipping
   - Mixed precision with bfloat16

3. **Speed Optimizations**
   - Stride-4 patch embedding (500× token reduction)
   - torch.compile + gradient checkpointing
   - GPU-native augmentations
   - Virtual epochs for faster convergence

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) and [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) for details.

## 📚 Documentation

- 📖 [SETUP.md](docs/SETUP.md) - Installation and environment setup
- 🔬 [METHODOLOGY.md](docs/METHODOLOGY.md) - Theoretical background
- 📊 [EXPERIMENTS.md](docs/EXPERIMENTS.md) - Detailed experimental results
- 💾 [DATASET.md](docs/DATASET.md) - LIDC-IDRI dataset information
- 🔁 [REPRODUCTION.md](docs/REPRODUCTION.md) - Reproduce all results

## 🤝 Team

- **Razvan Bocra** - Research & experimentation
- **Marius Boroica** - Research & analysis
- **Mihai Deaconu** - Research & development
- **Roberto Hordoan** - Research & application development

## 📄 Citation

If you use this code or our pretrained models:

```bibtex
@software{lungscan_assist_2026,
  title={LungScan Assist: AI-Powered Lung Nodule Detection and Analysis},
  author={Bocra, Razvan and Boroica, Marius and Deaconu, Mihai and Hordoan, Roberto},
  year={2026},
  url={https://github.com/LauraDiosan-CS/projects-in-silico-diagnostics},
  license={MIT}
}
```

See [CITATION.cff](CITATION.cff) for full citation metadata.

## 📝 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- **LIDC-IDRI Dataset**: [Armato et al., 2011](https://aapm.onlinelibrary.wiley.com/doi/full/10.1118/1.3528204)
- **MONAI Framework**: Medical Open Network for AI
- **PyTorch**: Deep learning framework
- **H100 GPU Access**: High-performance computing resources

## 📧 Contact

For questions or collaborations:
- Open an [issue](https://github.com/LauraDiosan-CS/projects-in-silico-diagnostics/issues)
- See [docs/](docs/) for detailed documentation

## 🔗 Links

- **Dataset**: [LIDC-IDRI on TCIA](https://wiki.cancerimagingarchive.net/display/Public/LIDC-IDRI)
- **Pretrained Models**: [checkpoints/README.md](checkpoints/README.md)
- **Paper Materials**: [paper/](paper/)

---

**Status**: 🚧 Active Development | ✅ Ready for Publication

Last Updated: January 2026
