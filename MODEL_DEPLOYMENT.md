# Model Deployment and Access Guide

## 🏗️ Deployment Architecture

The lung cancer detection model is deployed as part of a **FastAPI backend service** that serves predictions through REST API endpoints. The model is integrated into a full-stack web application.

### Architecture Overview

```
┌─────────────────┐
│   Frontend      │  Next.js Web App (http://localhost:3000)
│   (Next.js)     │  - Upload CT scans
└────────┬────────┘  - View analysis results
         │            - Interactive visualizations
         │ HTTP API
         ▼
┌─────────────────┐
│   Backend       │  FastAPI Server (http://127.0.0.1:8000)
│   (FastAPI)     │  - Receives image uploads
└────────┬────────┘  - Loads AI model
         │            - Runs inference
         │            - Returns predictions
         │
         ▼
┌─────────────────┐
│   AI Model      │  ResNet-50 Model
│   (PyTorch)     │  - Loaded from Hugging Face
└─────────────────┘  - Runs on CPU/GPU
```

## 📦 Model Deployment Process

### 1. **Model Loading (Lazy Loading)**

The model is loaded **on-demand** when first needed:

- **Location**: `backend/app/services/model_loader.py`
- **Source**: Hugging Face Hub (`dorsar/lung-cancer-detection`)
- **First Load**: Downloads model weights (~100MB) and caches locally
- **Subsequent Loads**: Uses cached model from `~/.cache/huggingface/lungscan/`

```python
# Model is loaded lazily when analyze_image() is called
model_loader = get_model_loader()
model = model_loader.load_model()  # Downloads if not cached
```

### 2. **Model Integration**

The model is integrated into the FastAPI backend through:

- **Service Layer**: `backend/app/services/analysis.py`
  - Handles image preprocessing
  - Runs model inference
  - Post-processes results into nodules

- **API Endpoint**: `backend/app/api/routes/analyze.py`
  - Exposes REST API endpoint
  - Handles HTTP requests/responses

## 🌐 How to Access the Model

### Option 1: Web Application (Recommended for Users)

**Start the Application:**

```bash
# Terminal 1: Start Backend
cd /Users/adriantrill/Desktop/github/LungScan
./scripts/dev_backend.sh

# Terminal 2: Start Frontend  
./scripts/dev_frontend.sh
```

**Access Points:**
- **Web UI**: http://localhost:3000
- **API Docs**: http://127.0.0.1:8000/docs

**Usage Flow:**
1. Open http://localhost:3000 in your browser
2. Upload a CT scan image
3. Click "Analyze" button
4. View AI predictions with visualizations

### Option 2: REST API (For Developers/Integration)

**API Endpoints:**

#### 1. **Upload CT Scan**
```bash
POST http://127.0.0.1:8000/api/upload
Content-Type: multipart/form-data

Form Data:
- scan: (file) CT scan image
- patient_id: (optional) Patient ID
```

**Response:**
```json
{
  "case_id": "abc-123-def",
  "filename": "ct_scan.png",
  "uploaded_at": "2024-01-15T10:30:00Z"
}
```

#### 2. **Run AI Analysis**
```bash
POST http://127.0.0.1:8000/api/analyze/{case_id}
```

**Example:**
```bash
curl -X POST http://127.0.0.1:8000/api/analyze/abc-123-def
```

**Response:**
```json
{
  "case_id": "abc-123-def",
  "nodules": [
    {
      "id": "nodule-001",
      "x": 320,
      "y": 240,
      "radius": 25,
      "malignancy_score": 0.75,
      "explanation": "AI detected adenocarcinoma with 85% confidence..."
    }
  ],
  "summary": "Analysis complete: 1 suspicious region(s) detected..."
}
```

#### 3. **Get Case Details**
```bash
GET http://127.0.0.1:8000/api/cases/{case_id}
```

#### 4. **List All Cases**
```bash
GET http://127.0.0.1:8000/api/cases
```

### Option 3: Interactive API Documentation

**Swagger UI**: http://127.0.0.1:8000/docs

- Interactive API explorer
- Test endpoints directly from browser
- See request/response schemas
- Try out the model without writing code

### Option 4: Python Client (Programmatic Access)

```python
import requests

# 1. Upload image
with open("ct_scan.png", "rb") as f:
    response = requests.post(
        "http://127.0.0.1:8000/api/upload",
        files={"scan": f},
        data={"patient_id": "patient-001"}
    )
case_id = response.json()["case_id"]

# 2. Run analysis
response = requests.post(f"http://127.0.0.1:8000/api/analyze/{case_id}")
result = response.json()

# 3. View results
print(f"Detected {len(result['nodules'])} nodules")
for nodule in result['nodules']:
    print(f"Nodule at ({nodule['x']}, {nodule['y']}): "
          f"malignancy score = {nodule['malignancy_score']:.2f}")
```

## 🔧 Model Configuration

### Model Details

- **Architecture**: ResNet-50 with custom classification head
- **Input Size**: 224×224 RGB images
- **Output**: 4-class classification (Normal, Adenocarcinoma, Large Cell Carcinoma, Squamous Cell Carcinoma)
- **Device**: Automatically uses GPU if available, otherwise CPU

### Configuration Files

- **Model Loader**: `backend/app/services/model_loader.py`
  - Model repository: `dorsar/lung-cancer-detection`
  - Cache location: `~/.cache/huggingface/lungscan/`

- **Backend Config**: `backend/app/core/config.py`
  - API host/port settings
  - CORS configuration

## 🚀 Deployment Steps

### Local Development

1. **Install Dependencies:**
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Start Backend:**
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

3. **Start Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Production Deployment

For production, you would:

1. **Use a production WSGI server:**
   ```bash
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

2. **Set up reverse proxy** (nginx/Apache)

3. **Use environment variables** for configuration

4. **Enable HTTPS** for secure connections

5. **Set up monitoring** and logging

## 📊 Model Performance

- **First Request**: ~5-10 seconds (model download + loading)
- **Subsequent Requests**: ~1-3 seconds per image
- **Throughput**: ~10-20 images/minute (CPU), ~50-100 images/minute (GPU)

## 🔍 Troubleshooting

### Model Not Loading

**Error**: `Model file not found`

**Solution**: 
- Check internet connection (first-time download)
- Verify Hugging Face access
- Check cache directory permissions: `~/.cache/huggingface/lungscan/`

### Slow Performance

**Causes**:
- Running on CPU instead of GPU
- Large image sizes
- First-time model loading

**Solutions**:
- Use GPU if available
- Resize images before upload
- Model is cached after first load

### API Not Responding

**Check**:
1. Backend is running: `curl http://127.0.0.1:8000/api/health`
2. Port 8000 is not in use
3. Check logs: `backend/app/logs/` (if configured)

## 📝 Example Workflow

### Complete Example: Using the Model

```bash
# 1. Start backend
cd /Users/adriantrill/Desktop/github/LungScan/backend
source .venv/bin/activate
uvicorn app.main:app --reload

# 2. In another terminal, upload an image
curl -X POST http://127.0.0.1:8000/api/upload \
  -F "scan=@backend/static/images/ct_scan_sample.png" \
  -F "patient_id=test-patient"

# Response: {"case_id": "abc-123", ...}

# 3. Run analysis
curl -X POST http://127.0.0.1:8000/api/analyze/abc-123

# Response: {"nodules": [...], "summary": "..."}
```

## 🔗 Related Files

- **Model Loader**: `backend/app/services/model_loader.py`
- **Analysis Service**: `backend/app/services/analysis.py`
- **API Route**: `backend/app/api/routes/analyze.py`
- **Main App**: `backend/app/main.py`
- **Frontend API Client**: `frontend/src/lib/api.ts`

## 📚 Additional Resources

- **API Documentation**: http://127.0.0.1:8000/docs (when backend is running)
- **Model Repository**: https://huggingface.co/dorsar/lung-cancer-detection
- **Notebook Demo**: `model_demonstration.ipynb`

