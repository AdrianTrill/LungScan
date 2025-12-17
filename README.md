# LungScan Assist

A production-ready web application for AI-powered lung nodule detection and analysis. This MVP allows doctors to upload CT scan images, get AI-generated nodule detections with malignancy scores, visualize nodules on scans, and export reports.

## 🏗️ Architecture

This is a **monorepo** containing:

- **Backend**: FastAPI (Python 3.11+) with integrated AI model from Hugging Face
- **Frontend**: Next.js 14 (App Router) + TypeScript + Tailwind CSS

## 🚀 Quick Start

### One-Command Setup and Run

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

## 📋 Manual Setup

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

## 📁 Project Structure

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
│       │   ├── config.py
│       │   ├── schemas.py
│       │   └── utils.py
│       ├── api/
│       │   └── routes/
│       │       ├── health.py
│       │       ├── upload.py
│       │       ├── analyze.py
│       │       ├── cases.py
│       │       └── report.py
│       ├── services/
│       │   ├── storage.py
│       │   ├── analysis_mock.py
│       │   └── report.py
│       └── tests/
│           └── test_health.py
└── frontend/
    ├── .env.example
    ├── package.json
    ├── next.config.ts
    ├── tailwind.config.ts
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx           # Cases list
        │   └── cases/
        │       └── [id]/
        │           └── page.tsx    # Case detail
        ├── components/
        │   ├── ui/                # UI primitives
        │   ├── cases/            # Case components
        │   ├── upload/           # File upload
        │   ├── viewer/           # Scan viewer
        │   └── report/           # Report editor
        ├── lib/
        │   ├── api.ts            # API client
        │   └── types.ts          # TypeScript types
        ├── styles/
        │   └── globals.css
        └── tests/
            └── CaseCard.test.tsx
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

# Lint with Ruff
ruff check app/

# Format with Black
black app/
```

### Frontend Linting/Formatting

```bash
cd frontend

# Lint
npm run lint

# Format
npm run format
```

## 🎯 Features (MVP)

✅ **File Upload**: Accept CT scan images (JPEG, PNG, DICOM)  
✅ **AI Analysis**: Real lung cancer detection using ResNet-50 model from Hugging Face  
✅ **Interactive Viewer**: Visualize scans with nodule overlays  
✅ **Report Generation**: Export text reports with notes  
✅ **Case Management**: List, view, and delete cases (in-memory storage)

## 🔄 Development Workflow

1. **Upload a scan** → Creates a case and automatically runs AI analysis
2. **View results** → See AI-detected nodules with malignancy scores on the scan image
3. **Add notes** → Write clinical observations
4. **Export report** → Download a formatted text report with AI findings

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

## 🚧 Future Enhancements

- Persistent storage (database instead of in-memory)
- User authentication and authorization
- PDF report generation
- Multi-frame DICOM support
- Advanced visualization tools
- Export to DICOM-SR format

## 📄 License

This project is part of a medical imaging research initiative.

## 🤝 Contributing

This is an MVP prototype. For production deployment:
1. Implement persistent database storage
3. Add authentication/authorization
4. Set up proper error handling and logging
5. Configure production-ready deployment (Docker, cloud, etc.)

---

**Note**: This MVP uses a real AI model (ResNet-50 based lung cancer detection model from Hugging Face) for nodule detection and classification. See `MODEL_DEPLOYMENT.md` for details on model integration and usage.

