"""FastAPI dependencies: the storage and the classifier the app was created with."""

from fastapi import Request

from app.services.model import Classifier
from app.services.storage import Storage


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def get_classifier(request: Request) -> Classifier:
    return request.app.state.classifier
