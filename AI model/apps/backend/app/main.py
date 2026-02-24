"""FastAPI application main entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analyze, cases, health, images, patients, report, upload
from app.core.config import settings

# Create FastAPI app
app = FastAPI(
    title="LungScan Assist API",
    description="Backend API for lung nodule detection and analysis",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(cases.router, prefix="/api", tags=["cases"])
app.include_router(patients.router, prefix="/api", tags=["patients"])
app.include_router(report.router, prefix="/api", tags=["report"])
app.include_router(images.router, prefix="/api", tags=["images"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "LungScan Assist API", "version": "1.0.0"}

