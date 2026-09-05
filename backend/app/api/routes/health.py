from fastapi import APIRouter, Depends

from backend.app.api.dependencies import get_app_settings, get_loader
from backend.app.core.config import Settings
from backend.app.database.connection import ping_database
from backend.app.ml.model_loader import ModelLoader
from backend.app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


def _build_health_response(settings: Settings, loader: ModelLoader) -> dict:
    db = ping_database(settings)
    models = loader.artifact_status()
    ready = db.get("ok") and models.get("reconciliation_schema") and models.get("exception_schema")
    return {
        "status": "ok" if ready else "degraded",
        "database": db,
        "models": models,
    }


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_app_settings),
    loader: ModelLoader = Depends(get_loader),
) -> dict:
    return _build_health_response(settings, loader)


@router.get("/api/v1/health", response_model=HealthResponse)
def api_health(
    settings: Settings = Depends(get_app_settings),
    loader: ModelLoader = Depends(get_loader),
) -> dict:
    return _build_health_response(settings, loader)
