"""FastAPI application main entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analyze, cases, health, images, patients, report, upload
from app.core.config import settings
from app.services.model import Classifier
from app.services.storage import Storage

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def create_app(storage: Storage | None = None, classifier: Classifier | None = None) -> FastAPI:
    """Build the app. Tests pass their own storage and classifier."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.storage = storage or Storage(
            settings.data_dir,
            settings.upload_dir,
            settings.samples_dir,
            seed=settings.seed_samples,
        )
        app.state.classifier = classifier or Classifier(settings.model_path, settings.model_url)
        yield

    app = FastAPI(
        title="LungScan API",
        description="Backend API for lung CT slice analysis",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    for module in (health, upload, analyze, cases, patients, report, images):
        app.include_router(module.router, prefix="/api", tags=[module.__name__.rsplit(".", 1)[-1]])

    @app.get("/")
    async def root():
        return {"message": "LungScan API", "version": app.version, "docs": "/docs"}

    return app


app = create_app()
