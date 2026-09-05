"""Reconciliation matching model inference. Candidate-set scoring only."""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.app.ml.model_loader import LoadedModel, ModelLoader, get_model_loader


def _positive_class_index(estimator: Any) -> int:
    classes = getattr(estimator, "classes_", None)
    if classes is None and hasattr(estimator, "named_steps"):
        final = list(estimator.named_steps.values())[-1]
        classes = getattr(final, "classes_", None)
    if classes is None:
        return 1
    classes = list(classes)
    if 1 in classes:
        return classes.index(1)
    if "1" in classes:
        return classes.index("1")
    if True in classes:
        return classes.index(True)
    return len(classes) - 1


class ReconciliationModel:
    def __init__(self, loaded: LoadedModel) -> None:
        self.loaded = loaded

    @classmethod
    def from_loader(cls, loader: ModelLoader | None = None) -> "ReconciliationModel":
        loader = loader or get_model_loader()
        return cls(loader.load_reconciliation_model())

    def score_rows(self, feature_rows: list[dict]) -> list[float]:
        if not feature_rows:
            return []
        frame = pd.DataFrame(feature_rows)
        missing = [col for col in self.loaded.features if col not in frame.columns]
        if missing:
            raise ValueError(
                f"Feature rows missing schema columns: {missing}. "
                "Build features from feature_schema.json, do not pass raw DB columns."
            )
        ordered = frame[self.loaded.features]
        estimator = self.loaded.estimator
        if hasattr(estimator, "predict_proba"):
            proba = estimator.predict_proba(ordered)
            idx = _positive_class_index(estimator)
            return [float(row[idx]) for row in proba]
        scores = estimator.predict(ordered)
        return [float(value) for value in scores]
