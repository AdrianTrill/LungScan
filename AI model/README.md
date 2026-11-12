# LungScan research: 3D nodule segmentation and biomarkers

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red.svg)](https://pytorch.org/)
[![MONAI](https://img.shields.io/badge/MONAI-VISTA--3D-0d9488.svg)](https://monai.io/)

The research behind LungScan: 3D segmentation of lung nodules and tumors in CT volumes, and the prediction of tumor biomarkers from imaging. The web application at the root of the repository reads 2D slices with a separate classifier, and does not run these models.

## 🎯 Results

The [SENSERA report](paper/sensera_report.pdf) ([LaTeX source](paper/manuscript_source/sensera_report.tex)) summarizes the work. Its results, as reported:

**Segmentation.** VISTA-3D, a foundation model pretrained on about 11,000 CT scans, proposes candidates; a "Shadow Mining" 3D ResNet-18, trained with focal loss and Mixup on hard false positives mined by five cross-validated VISTA-3D models, rejects false positives.

| Metric | VISTA-3D alone | VISTA-3D + ResNet-18 |
|--------|---------------:|---------------------:|
| Tumor Dice (volumetric) | 0.6260 | **0.7342** |
| Recall (sensitivity) | **0.9447** | 0.9213 |
| Precision | 0.2745 | **0.6483** |
| False positives per scan | 2.76 | **0.58** |
| Lesion-wise Dice (true positives) | 0.7858 | **0.8102** |

**Biomarkers.** A late fusion of DenseNet121 features and PyRadiomics features with XGBoost, on TCGA-LUAD and NSCLC Radiogenomics (AUC):

| Target | Deep learning | Radiomics (XGBoost) | Late fusion |
|--------|--------------:|--------------------:|------------:|
| EGFR mutation | 0.73 | 0.82 | **0.87** |
| KRAS mutation | 0.71 | 0.81 | **0.86** |

On a private cohort of 92 patients with IHC validation, the report gives AUCs of 0.80 for TTF-1 and 0.76 for CK7. The evaluation outputs behind these tables are not in this repository; the HPC logs of the VISTA-3D training runs are in [archive/logs](archive/logs/).

### Earlier experiments (reported, not reproducible from this repository)

The research notes in [docs/](docs/) describe earlier runs of four architectures on LIDC-IDRI. Their checkpoints, configs, and logs are not in this repository, so these figures cannot be checked here:

| Model | Dice (reported) | Training time (2× H100) | Key feature |
|-------|----------------:|------------------------|-------------|
| SwinUNETR | 0.82 | 8-12h | SSL pretraining (5,050 CT scans) |
| SegResNet | 0.80 | ~8h | Speed-optimized, virtual epochs |
| UNETR++ | 0.78 | 24-36h | Transformer baseline |
| nnUNet | 0.76 | ~48h | Auto-configured baseline |

## 🏗️ Repository Structure

This folder holds the research side of LungScan. The web application (FastAPI backend, Next.js frontend, and their scripts) lives at the root of the repository.

```
AI model/
├── README.md                    # This file
├── requirements.txt             # Research dependencies (MONAI, pylidc, timm, ...)
├── preprocessing_requirements.txt
├── set_paths.sh                 # nnU-Net environment variables for the HPC runs
│
├── paper/                       # Publication materials
│   ├── sensera_report.pdf       # SENSERA report: segmentation and biomarker results
│   ├── manuscript_source/       # LaTeX source of the report
│   ├── MIRPR_VISTA_3D_Documentation.pdf
│   ├── lab3_MIRPR.pdf
│   └── literature_reviews/      # Paper reviews by the team
│
├── docs/                        # Methodology, experiments, dataset, setup, reproduction
│
├── apps/
│   └── MIRPR-full-pipeline/     # Radiomics + XGBoost / DenseNet biomarker pipeline
│
├── research/
│   ├── experiments/unetrpp/     # UNETR++ runs: full-dataset and legacy overfit experiments
│   ├── training/                # Training and resume scripts (VISTA-3D, H100 jobs)
│   ├── evaluation/              # Dice, lesion-level, and probability evaluation
│   ├── notebooks/               # Dataset generation and training notebooks
│   ├── models/                  # Model architectures
│   ├── results/                 # Qualitative predictions and training plots
│   └── diagnostic/              # Debugging and visualization utilities
│
├── utils/                       # LIDC-IDRI preparation, datasets, nnU-Net conversion
│
└── archive/
    ├── early_reports/           # Early experiment write-ups
    └── logs/                    # HPC job logs (stdout/stderr) of the VISTA-3D runs
```

## 🚀 Quick Start

### 1. Installation

```bash
# From the repository root
cd "AI model"

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
3. Preprocess with the scripts in [utils/](utils/), for example `utils/prepare_dataset.py`

See [docs/DATASET.md](docs/DATASET.md) for details.

### 3. Run the Production App

The app is at the repository root:

```bash
cd ..
./scripts/setup.sh
./scripts/dev.sh
```

Access:
- **Frontend**: http://localhost:3000
- **Backend API**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs

### 4. Reproduce Research Results

Training entry points are in [research/training/](research/training/) and the evaluation scripts in [research/evaluation/](research/evaluation/). Checkpoints are not included in this repository.

See [docs/REPRODUCTION.md](docs/REPRODUCTION.md) for full reproduction guide.

## 🔬 Methods

### Techniques used in the experiments

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

## 📝 License

This project is licensed under the MIT License - see [LICENSE](../LICENSE) for details.

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
- **Paper Materials**: [paper/](paper/)

---

Last Updated: January 2026
