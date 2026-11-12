"""Application configuration, read from environment variables and backend/.env."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, protected_namespaces=("settings_",)
    )

    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    data_dir: Path = Field(BACKEND_DIR / "data", validation_alias="LUNGSCAN_DATA_DIR")
    upload_dir: Path = Field(BACKEND_DIR / "uploads", validation_alias="LUNGSCAN_UPLOAD_DIR")
    samples_dir: Path = Field(
        REPO_DIR / "model" / "samples", validation_alias="LUNGSCAN_SAMPLES_DIR"
    )
    seed_samples: bool = Field(True, validation_alias="LUNGSCAN_SEED_SAMPLES")

    model_path: Path = Field(
        REPO_DIR / "model" / "lungscan.onnx", validation_alias="LUNGSCAN_MODEL_PATH"
    )
    model_url: str = Field(
        "https://adriantrill.github.io/LungScan/models/lungscan.onnx",
        validation_alias="LUNGSCAN_MODEL_URL",
    )


settings = Settings()
