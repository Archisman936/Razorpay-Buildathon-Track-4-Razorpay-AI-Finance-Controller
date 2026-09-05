"""Load trained joblib artifacts once. Do not retrain."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class ModelArtifactError(RuntimeError):
    """Raised when a required model file or schema is missing or invalid."""


@dataclass
class LoadedModel:
    name: str
    estimator: Any
    schema: dict
    features: list[str]
    metadata: dict = field(default_factory=dict)
    path: Path | None = None

    @property
    def threshold(self) -> float | None:
        value = self.schema.get("threshold")
        return float(value) if value is not None else None


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise ModelArtifactError(
            f"{label} not found at '{path}'. "
            "Place the trained .joblib next to feature_schema.json, "
            "or set RECONCILIATION_MODEL_DIR / EXCEPTION_MODEL_DIR."
        )
    if not path.is_file():
        raise ModelArtifactError(f"{label} path is not a file: {path}")


def load_json(path: Path) -> dict:
    _require_file(path, path.name)
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ModelArtifactError(f"Expected JSON object in {path}")
    return data


def _load_joblib(path: Path, label: str) -> Any:
    _require_file(path, label)
    try:
        import joblib
    except ImportError as exc:
        raise ModelArtifactError(
            "joblib is required to load ML artifacts. Install backend requirements."
        ) from exc
    try:
        return joblib.load(path)
    except Exception as exc:
        raise ModelArtifactError(f"Failed to load {label} from {path}: {exc}") from exc


def unwrap_estimator(raw: Any, label: str) -> tuple[Any, dict]:
    """Accept a sklearn estimator or a training bundle dict with a 'model' key."""
    if hasattr(raw, "predict") or hasattr(raw, "predict_proba"):
        return raw, {}
    if isinstance(raw, dict) and raw.get("model") is not None:
        estimator = raw["model"]
        if not (hasattr(estimator, "predict") or hasattr(estimator, "predict_proba")):
            raise ModelArtifactError(
                f"{label} bundle key 'model' is not an estimator: {type(estimator)}"
            )
        meta = {
            key: value
            for key, value in raw.items()
            if key != "model"
        }
        return estimator, meta
    raise ModelArtifactError(
        f"{label} is not a scikit-learn estimator or a dict with a 'model' key "
        f"(got {type(raw)})"
    )


class ModelLoader:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._reconciliation: LoadedModel | None = None
        self._exception: LoadedModel | None = None

    def load_reconciliation_model(self) -> LoadedModel:
        if self._reconciliation is None:
            schema = load_json(self.settings.reconciliation_schema_path)
            features = list(schema.get("features") or [])
            if not features:
                raise ModelArtifactError(
                    f"No features listed in {self.settings.reconciliation_schema_path}"
                )
            raw = _load_joblib(
                self.settings.reconciliation_model_path,
                "reconciliation model",
            )
            estimator, bundle_meta = unwrap_estimator(raw, "reconciliation model")
            if schema.get("threshold") is None and bundle_meta.get("threshold") is not None:
                schema["threshold"] = bundle_meta["threshold"]
            bundle_features = bundle_meta.get("feature_names")
            if bundle_features and list(bundle_features) != features:
                logger.warning(
                    "joblib feature_names differ from feature_schema.json; using schema. "
                    "bundle=%s schema=%s",
                    bundle_features,
                    features,
                )
            self._reconciliation = LoadedModel(
                name="reconciliation",
                estimator=estimator,
                schema=schema,
                features=features,
                metadata={
                    "model": schema.get("model"),
                    "threshold": schema.get("threshold"),
                    "feature_count": schema.get("feature_count", len(features)),
                    "bundle": {
                        key: bundle_meta[key]
                        for key in ("model_name", "pipeline_role", "threshold")
                        if key in bundle_meta
                    },
                },
                path=self.settings.reconciliation_model_path,
            )
            logger.info(
                "loaded reconciliation model features=%s threshold=%s path=%s",
                len(features),
                schema.get("threshold"),
                self.settings.reconciliation_model_path,
            )
        return self._reconciliation

    def load_exception_classifier(self) -> LoadedModel:
        if self._exception is None:
            schema = load_json(self.settings.exception_schema_path)
            features = list(schema.get("features") or [])
            if not features:
                raise ModelArtifactError(
                    f"No features listed in {self.settings.exception_schema_path}"
                )
            raw = _load_joblib(
                self.settings.exception_model_path,
                "exception classifier",
            )
            estimator, _bundle_meta = unwrap_estimator(raw, "exception classifier")
            self._exception = LoadedModel(
                name="exception_classifier",
                estimator=estimator,
                schema=schema,
                features=features,
                metadata={
                    "classes": schema.get("classes"),
                    "best_model": schema.get("best_model"),
                },
                path=self.settings.exception_model_path,
            )
            logger.info(
                "loaded exception classifier features=%s classes=%s path=%s",
                len(features),
                schema.get("classes"),
                self.settings.exception_model_path,
            )
        return self._exception

    def get_reconciliation_schema(self) -> dict:
        if self._reconciliation:
            return self._reconciliation.schema
        return load_json(self.settings.reconciliation_schema_path)

    def get_exception_schema(self) -> dict:
        if self._exception:
            return self._exception.schema
        return load_json(self.settings.exception_schema_path)

    def artifact_status(self) -> dict:
        recon_model = self.settings.reconciliation_model_path
        recon_schema = self.settings.reconciliation_schema_path
        exc_model = self.settings.exception_model_path
        exc_schema = self.settings.exception_schema_path
        return {
            "reconciliation_schema": recon_schema.exists(),
            "reconciliation_model": recon_model.exists(),
            "exception_schema": exc_schema.exists(),
            "exception_model": exc_model.exists(),
            "reconciliation_model_path": str(recon_model),
            "exception_model_path": str(exc_model),
        }


@lru_cache(maxsize=1)
def get_model_loader() -> ModelLoader:
    return ModelLoader()
