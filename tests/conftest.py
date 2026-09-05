from pathlib import Path

import pytest

from backend.app.core.config import Settings
from backend.app.ml.model_loader import ModelLoader


ROOT = Path(__file__).resolve().parents[2]
ML = ROOT / "tools" / "ML_Models"


class SchemaOnlyLoader(ModelLoader):
    """Loads feature schemas without requiring .joblib files."""

    def __init__(self) -> None:
        settings = Settings()
        super().__init__(settings)

    def load_reconciliation_model(self):
        raise AssertionError("joblib should not load in this test")

    def load_exception_classifier(self):
        raise AssertionError("joblib should not load in this test")


@pytest.fixture
def schema_loader() -> SchemaOnlyLoader:
    return SchemaOnlyLoader()
