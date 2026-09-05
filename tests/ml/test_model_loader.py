from pathlib import Path

import pytest

from backend.app.core.config import Settings
from backend.app.ml.model_loader import ModelArtifactError, ModelLoader


def test_schemas_load_and_joblib_absence_is_explicit():
    loader = ModelLoader()
    recon = loader.get_reconciliation_schema()
    exc = loader.get_exception_schema()
    assert recon["feature_count"] == 35 or len(recon["features"]) == 35
    assert len(exc["features"]) == 19
    assert recon.get("threshold") == 0.275
    status = loader.artifact_status()
    assert status["reconciliation_schema"] is True
    assert status["exception_schema"] is True
    if not status["reconciliation_model"]:
        with pytest.raises(ModelArtifactError) as err:
            loader.load_reconciliation_model()
        assert "not found" in str(err.value).lower() or "best_reconciliation_model" in str(err.value)
    if not status["exception_model"]:
        with pytest.raises(ModelArtifactError) as err:
            loader.load_exception_classifier()
        assert "not found" in str(err.value).lower() or "best_exception" in str(err.value)


def test_model_paths_are_relative_to_project(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ML_MODELS_DIR", str(tmp_path / "tools" / "ML_Models"))
    from backend.app.core.config import Settings as SettingsCls

    settings = SettingsCls()
    assert settings.reconciliation_model_path.is_absolute()
    assert "Reconciliation Model" in str(settings.reconciliation_model_dir)
    assert settings.reconciliation_model_path.name == "best_reconciliation_model.joblib"
