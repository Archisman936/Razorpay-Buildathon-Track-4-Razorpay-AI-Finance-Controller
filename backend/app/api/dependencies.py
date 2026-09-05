"""FastAPI dependency wiring."""

from functools import lru_cache

from backend.app.core.config import Settings, get_settings
from backend.app.ml.model_loader import ModelLoader, get_model_loader
from backend.app.services.orchestration.pipeline import ReconciliationPipeline
from backend.app.services.reconciliation.reconciliation_service import ReconciliationService


@lru_cache(maxsize=1)
def get_pipeline() -> ReconciliationPipeline:
    settings = get_settings()
    loader = get_model_loader()
    service = ReconciliationService(settings=settings, loader=loader)
    return ReconciliationPipeline(service=service)


def get_app_settings() -> Settings:
    return get_settings()


def get_loader() -> ModelLoader:
    return get_model_loader()
