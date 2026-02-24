# Setup Guide

## Prerequisites

- **Operating System**: Linux (tested on Ubuntu 20.04+) or macOS
- **GPU**: NVIDIA GPU with CUDA support (H100 recommended, A100/V100 compatible)
- **CUDA**: Version 11.8 or higher
- **Python**: 3.9 or 3.10
- **RAM**: 32GB minimum, 64GB recommended
- **Storage**: 500GB+ for datasets and checkpoints

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/LauraDiosan-CS/projects-in-silico-diagnostics.git
cd projects-in-silico-diagnostics
```

### 2. Set Up Python Environment

#### Option A: Conda (Recommended)

```bash
# Create conda environment
conda create -n lungscan python=3.10
conda activate lungscan

# Install PyTorch with CUDA support
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia

# Install other dependencies
pip install -r requirements.txt
pip install -r preprocessing_requirements.txt
```

#### Option B: venv

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
pip install -r preprocessing_requirements.txt
```

### 3. Verify Installation

```bash
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA Available: {torch.cuda.is_available()}')"
```

## Data Setup

### Download LIDC-IDRI Dataset

1. **Register** at [TCIA - LIDC-IDRI](https://wiki.cancerimagingarchive.net/display/Public/LIDC-IDRI)
2. **Download** the dataset (124 GB)
3. **Extract** to `data/raw/LIDC-IDRI/`

### Preprocess Data

```bash
# Run preprocessing pipeline
python utils/prepare_dataset.py --input data/raw/LIDC-IDRI --output data/processed

# Verify splits
python utils/inspect_data.py --data-dir data/processed
```

## Download Pretrained Models

```bash
# Download model checkpoints (instructions in checkpoints/README.md)
bash scripts/download_pretrained_models.sh
```

## Running the Production App

### Backend + Frontend

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Setup environment
./scripts/setup.sh

# Run development servers
./scripts/dev.sh
```

- **Frontend**: http://localhost:3000
- **Backend API**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs

## Running Experiments

See [REPRODUCTION.md](./REPRODUCTION.md) for detailed experiment reproduction steps.

## Troubleshooting

### CUDA Out of Memory

- Reduce batch size in config files
- Enable gradient checkpointing
- Use smaller input patch sizes

### Data Loading Slow

- Increase `NUM_WORKERS` in training scripts
- Use SSD for data storage
- Enable data caching

### Import Errors

```bash
# Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
# Or on Windows:
set PYTHONPATH=%PYTHONPATH%;%CD%
```

## Development Environment

For development with testing and linting:

```bash
pip install -r requirements-dev.txt  # If you create this
pytest tests/
```

## Docker (Alternative)

```bash
# Build image
docker build -t lungscan .

# Run container
docker run --gpus all -p 3000:3000 -p 8000:8000 lungscan
```

## Support

For issues, please:
1. Check [docs/](.) for relevant documentation
2. Review [GitHub Issues](https://github.com/LauraDiosan-CS/projects-in-silico-diagnostics/issues)
3. Contact the development team
