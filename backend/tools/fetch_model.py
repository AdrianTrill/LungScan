"""Download the exported model from the project's GitHub Pages site.

    cd backend
    python -m tools.fetch_model

The server downloads the model the first time it analyzes a slice; this does it ahead
of time. The file is checked against the SHA-256 in its manifest. To build the model
from the original weights instead, run `python -m tools.export_model`.
"""

from app.core.config import settings
from app.services.model import ModelUnavailableError, download_model


def main() -> None:
    if settings.model_path.exists():
        print(f"The model is already at {settings.model_path}")
        return
    try:
        download_model(settings.model_url, settings.model_path)
    except ModelUnavailableError as error:
        raise SystemExit(str(error)) from error
    print(f"Downloaded the model to {settings.model_path}")


if __name__ == "__main__":
    main()
