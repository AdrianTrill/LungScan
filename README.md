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

## 🏗️ Architecture

This is a **monorepo** containing:

- **Backend**: FastAPI (Python 3.11+) with integrated AI model from Hugging Face
- **Frontend**: Next.js 14 (App Router) + TypeScript + Tailwind CSS
- **AI model/** : Research code, training, evaluation, and documentation (see [AI model/README.md](AI%20model/README.md))

## 🏗️ Repository Structure

```
LungScan/
├── README.md                 # This file
├── scripts/                  # App setup and run
│   ├── setup.sh
│   ├── dev.sh
│   ├── dev_backend.sh
│   └── dev_frontend.sh
├── backend/                  # FastAPI backend (production app)
│   └── app/
├── frontend/                 # Next.js 14 frontend
│   └── src/
└── AI model/                 # Research & experiments
    ├── README.md             # Full research documentation
    ├── docs/                 # Methodology, experiments, setup
    ├── data/                 # Splits and data organization
    ├── research/             # Training, evaluation, models
    ├── paper/                # Publication materials
    ├── utils/                # Shared utilities
    └── scripts/              # Research scripts
```

## 🚀 Quick Start

### 1. Run Production App

```bash
# Make scripts executable (first time only)
chmod +x scripts/*.sh

# Setup everything
./scripts/setup.sh

# Run both servers (in separate terminals)
./scripts/dev_backend.sh    # Terminal 1: Backend
./scripts/dev_frontend.sh   # Terminal 2: Frontend

# Or run both together
./scripts/dev.sh            # Runs both in parallel
```

The application will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://127.0.0.1:8000
- **API Documentation**: http://127.0.0.1:8000/docs

### 2. Reproduce Research Results

For training, evaluation, and full research setup, see the [AI model README](AI%20model/README.md) and [AI model/docs/](AI%20model/docs/).

```bash
cd "AI model"
# See AI model/README.md for conda env, data download, and training commands
```

## 📊 Results Summary

### Main Performance Metrics

| Metric | UNETR++ | SwinUNETR | SegResNet | nnUNet |
|--------|---------|-----------|-----------|--------|
| **Positive Dice** | 0.78 | **0.82** | 0.80 | 0.76 |
| **Negative Dice** | 0.98 | 0.99 | 0.98 | 0.98 |
| **Training Time** | 24-36h | **8-12h** | **~8h** | ~48h |
| **Parameters** | 65M | 62M | 25M | Varies |

*All experiments on 2× NVIDIA H100 GPUs*

## 📋 Manual Setup (Production App)

### Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Copy environment variables
cp .env.example .env

# Run server
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# (Optional) Copy environment variables
cp .env.example .env.local

# Run development server
npm run dev
```

## 📁 Project Structure (App)

```
lungscan-assist/
├── README.md
├── scripts/
│   ├── setup.sh          # One-command setup
│   ├── dev.sh            # Run both servers together
│   ├── dev_backend.sh    # Backend only
│   └── dev_frontend.sh   # Frontend only
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── app/
│       ├── main.py       # FastAPI app entry point
│       ├── core/
│       ├── api/routes/
│       ├── services/
│       └── tests/
└── frontend/
    ├── package.json
    ├── next.config.ts
    └── src/
        ├── app/
        ├── components/
        ├── lib/
        └── styles/
```

## 🔌 API Endpoints

### Health Check
- `GET /api/health` - Returns `{status: "ok"}`

### Upload
- `POST /api/upload` - Upload a CT scan file (multipart/form-data)
  - Returns: `UploadResult` with `case_id` and metadata

### Analysis
- `POST /api/analyze/{case_id}` - Run AI analysis on a case
  - Returns: `AnalyzeResult` with detected nodules and malignancy scores

### Cases
- `GET /api/cases` - List all cases
- `GET /api/cases/{case_id}` - Get case details with analysis results
- `DELETE /api/cases/{case_id}` - Delete a case

### Reports
- `POST /api/report/{case_id}` - Generate and download a text report
  - Body: `{notes: string}`
  - Returns: Text file download

## 🧪 Testing

### Backend Tests

```bash
cd backend
source .venv/bin/activate
pytest app/tests/
```

### Frontend Tests

```bash
cd frontend
npm test
```

## 🔧 Code Quality

### Backend Linting/Formatting

```bash
cd backend
source .venv/bin/activate
ruff check app/
black app/
```

### Frontend Linting/Formatting

```bash
cd frontend
npm run lint
npm run format
```

## 🎯 Features (MVP)

✅ **File Upload**: Accept CT scan images (JPEG, PNG, DICOM)  
✅ **AI Analysis**: Real lung cancer detection using ResNet-50 model from Hugging Face  
✅ **Interactive Viewer**: Visualize scans with nodule overlays  
✅ **Report Generation**: Export text reports with notes  
✅ **Case Management**: List, view, and delete cases (in-memory storage)

## 📚 Documentation

- 📖 [AI model/docs/SETUP.md](AI%20model/docs/SETUP.md) - Installation and environment setup (research)
- 🔬 [AI model/docs/METHODOLOGY.md](AI%20model/docs/METHODOLOGY.md) - Theoretical background
- 📊 [AI model/docs/EXPERIMENTS.md](AI%20model/docs/EXPERIMENTS.md) - Detailed experimental results
- 💾 [AI model/docs/DATASET.md](AI%20model/docs/DATASET.md) - LIDC-IDRI dataset information
- 🔁 [AI model/docs/REPRODUCTION.md](AI%20model/docs/REPRODUCTION.md) - Reproduce all results

## 📝 Environment Variables

### Backend (.env)

```env
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:3000
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 🙏 Acknowledgments

- **LIDC-IDRI Dataset**: [Armato et al., 2011](https://aapm.onlinelibrary.wiley.com/doi/full/10.1118/1.3528204)
- **MONAI Framework**: Medical Open Network for AI
- **PyTorch**: Deep learning framework
- **H100 GPU Access**: High-performance computing resources

## 🔗 Links

- **Dataset**: [LIDC-IDRI on TCIA](https://wiki.cancerimagingarchive.net/display/Public/LIDC-IDRI)
- **AI model README**: [AI model/README.md](AI%20model/README.md) - Full research documentation
- **Paper Materials**: [AI model/paper/](AI%20model/paper/)

## 📄 License

This project is part of a medical imaging research initiative. MIT License.

## 🤝 Contributing

This is an MVP prototype. For production deployment:
1. Implement persistent database storage
2. Add authentication/authorization
3. Set up proper error handling and logging
4. Configure production-ready deployment (Docker, cloud, etc.)

---

**Status**: 🚧 Active Development | ✅ Ready for Publication

**Note**: This MVP uses a real AI model (ResNet-50 based lung cancer detection model from Hugging Face) for nodule detection. The [AI model/](AI%20model/) directory contains the full research code (SwinUNETR, SegResNet, etc.) and reproduction instructions.

Last Updated: February 2026
