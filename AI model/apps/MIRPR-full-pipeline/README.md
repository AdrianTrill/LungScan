# MIRPR Full Pipeline

Complete machine learning pipeline for radiomics-based analysis and inference on medical imaging data.

## 📋 Overview

This pipeline implements a full end-to-end workflow for:
- **Data Acquisition**: Download CT scans from TCIA/GDC
- **Preprocessing**: Convert and prepare DICOM data
- **Feature Extraction**: PyRadiomics feature computation
- **Model Training**: XGBoost and DenseNet classifiers
- **Inference**: Batch prediction on new cases
- **Analysis**: Statistical analysis and feature selection

## 🏗️ Pipeline Structure

```
MIRPR-full-pipeline/
├── scripts/
│   ├── data/              # Data acquisition and preparation
│   ├── analysis/          # Feature extraction and radiomics
│   │   ├── run_pyradiomics_batch.py
│   │   ├── build_unified_radiomics_table.py
│   │   ├── feature_selection.py
│   │   └── normalize_radiomics_jsons.py
│   ├── training/          # Model training
│   │   ├── train_xgboost.py
│   │   ├── train_densenet_roi.py
│   │   └── start_xgb_training_bg.sh
│   └── inference/         # Model execution
│       ├── run_inference_on_series.py
│       ├── infer_xgb_ensemble.py
│       ├── run_all_inference_bg.sh
│       └── run_all_inference_parallel.py
├── bin/
│   └── gdc-client          # GDC data transfer tool
├── radiomics_params*.yaml  # PyRadiomics configurations
├── inference.py            # Main inference script
├── requirements.txt        # Python dependencies
└── requirements-ml.txt     # ML-specific dependencies
```

## 📚 Documentation

- **[CONTEXT.md](./CONTEXT.md)** - Project background and goals
- **[DATASETS.md](./DATASETS.md)** - Dataset descriptions and access
- **[ML_PIPELINE.md](./ML_PIPELINE.md)** - Detailed pipeline documentation
- **[implementation plan.md](./implementation%20plan.md)** - Development roadmap

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd apps/MIRPR-full-pipeline

# Basic requirements
pip install -r requirements.txt

# ML requirements (includes radiomics)
pip install -r requirements-ml.txt
```

### 2. Data Acquisition

```bash
# Download data from GDC
./bin/gdc-client download -m manifest.txt

# Or use the data acquisition scripts
cd scripts/data
python download_tcia_data.py
```

### 3. Feature Extraction

```bash
cd scripts/analysis

# Run PyRadiomics on a single case
python run_pyradiomics_one.py --input path/to/ct.nii.gz --mask path/to/mask.nii.gz

# Batch processing
python run_pyradiomics_batch.py --data-dir ../../data --config ../../radiomics_params_medium.yaml

# Build unified feature table
python build_unified_radiomics_table.py --input-dir ../../data/radiomics --output features.csv
```

### 4. Train Models

```bash
cd scripts/training

# Train XGBoost classifier
python train_xgboost.py --features ../../features.csv --labels ../../labels.csv

# Train DenseNet on ROIs
python train_densenet_roi.py --data-dir ../../data/rois
```

### 5. Run Inference

```bash
cd scripts/inference

# Single series inference
python run_inference_on_series.py --series-id ABC123 --model ../../models/xgb_best.pkl

# Batch inference (parallel)
python run_all_inference_parallel.py --data-dir ../../data/test --model ../../models/ensemble.pkl

# Background batch processing
bash run_all_inference_bg.sh
```

## 🔬 PyRadiomics Configuration

Multiple radiomics parameter files are provided for different use cases:

| Config File | Description | Use Case |
|-------------|-------------|----------|
| `radiomics_params.yaml` | Basic config | Quick testing |
| `radiomics_params_fast.yaml` | Minimal features | Rapid prototyping |
| `radiomics_params_medium.yaml` | Balanced | Standard analysis |
| `radiomics_params_full_no_resample.yaml` | Comprehensive | Publication quality |
| `radiomics_params_medium_no_shape.yaml` | Texture-focused | Specific studies |

Example usage:
```bash
python run_pyradiomics_batch.py --config radiomics_params_medium.yaml
```

## 📊 Workflow Examples

### Complete End-to-End Pipeline

```bash
# 1. Download data
cd scripts/data
python download_dataset.py

# 2. Extract radiomics features
cd ../analysis
python run_pyradiomics_batch.py --config ../../radiomics_params_medium.yaml
python build_unified_radiomics_table.py

# 3. Feature selection and normalization
python normalize_radiomics_jsons.py
python feature_selection.py --input features.csv --output selected_features.csv

# 4. Train model
cd ../training
python train_xgboost.py --features ../analysis/selected_features.csv

# 5. Run inference
cd ../inference
python infer_xgb_ensemble.py --model ../training/model.pkl --test-data ../../data/test
```

## 🛠️ Scripts Overview

### Analysis Scripts

- **`run_pyradiomics_one.py`** - Extract radiomics from single image/mask pair
- **`run_pyradiomics_batch.py`** - Batch feature extraction
- **`build_unified_radiomics_table.py`** - Merge features into single CSV
- **`normalize_radiomics_jsons.py`** - Standardize feature values
- **`feature_selection.py`** - Select relevant features
- **`label_stats.py`** - Compute dataset statistics

### Training Scripts

- **`train_xgboost.py`** - Train XGBoost classifier on radiomics features
- **`train_densenet_roi.py`** - Train deep learning model on image ROIs
- **`start_xgb_training_bg.sh`** - Launch training in background

### Inference Scripts

- **`run_inference_on_series.py`** - Predict on single CT series
- **`infer_xgb_ensemble.py`** - Ensemble model inference
- **`run_all_inference_parallel.py`** - Parallel batch inference
- **`run_all_inference_bg.sh`** - Background batch processing

## 📈 Performance

The pipeline is optimized for:
- **Parallel processing**: Multi-threaded feature extraction
- **Batch operations**: Efficient bulk processing
- **Resource management**: Configurable memory usage

Typical performance on modern hardware:
- Feature extraction: ~30-60 seconds per case (medium config)
- XGBoost training: Minutes to hours depending on dataset size
- Inference: ~1-5 seconds per case

## 🔗 Integration

This pipeline integrates with:
- **Backend API**: `apps/backend/` for web-based inference
- **Frontend**: `apps/frontend/` for visualization
- **Research**: `research/` for experimental models

## 📝 Data Format

### Input
- **CT Scans**: NIfTI format (`.nii.gz`)
- **Masks**: NIfTI format, binary or multi-label
- **Metadata**: CSV or JSON

### Output
- **Features**: CSV with radiomics features
- **Predictions**: JSON with class probabilities
- **Analysis**: Statistical reports and visualizations

## 🤝 Usage in Main Project

This pipeline is used by:
1. **Research experiments** - Feature-based ML baselines
2. **Production backend** - Radiomics extraction service
3. **Analysis notebooks** - Statistical analysis

## 📄 Citation

If you use this pipeline:

```bibtex
@software{mirpr_pipeline_2026,
  title={MIRPR Full Pipeline: Radiomics and ML for Medical Imaging},
  author={Bocra, Razvan and Boroica, Marius and Deaconu, Mihai and Hordoan, Roberto},
  year={2026},
  url={https://github.com/LauraDiosan-CS/projects-in-silico-diagnostics}
}
```

## 📚 Additional Resources

- **PyRadiomics**: https://pyradiomics.readthedocs.io/
- **XGBoost**: https://xgboost.readthedocs.io/
- **GDC Data Portal**: https://portal.gdc.cancer.gov/

## ⚙️ Configuration

Key configuration files:
- `radiomics_params*.yaml` - Feature extraction parameters
- `AnonymizedPatientsTable.xlsx` - Patient metadata
- Training configs embedded in training scripts

See individual scripts for detailed configuration options.

---

**Part of**: [LungScan Assist](../../README.md)  
**Related**: [Backend](../backend/), [Frontend](../frontend/)
