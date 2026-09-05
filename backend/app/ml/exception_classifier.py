"""Exception classifier inference. Isolated from matching logic."""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.app.ml.model_loader import LoadedModel, ModelLoader, get_model_loader


class ExceptionClassifier:
    def __init__(self, loaded: LoadedModel) -> None:
        self.loaded = loaded

    @classmethod
    def from_loader(cls, loader: ModelLoader | None = None) -> "ExceptionClassifier":
        loader = loader or get_model_loader()
        return cls(loader.load_exception_classifier())

    def predict(self, feature_row: dict) -> dict:
        missing = [col for col in self.loaded.features if col not in feature_row]
        if missing:
            raise ValueError(
                f"Exception features missing schema columns: {missing}"
            )
        frame = pd.DataFrame([feature_row])[self.loaded.features]
        estimator = self.loaded.estimator
        raw_pred = estimator.predict(frame)[0]
        # Decode numeric class index -> label using schema index_to_class
        index_to_class = self.loaded.schema.get("index_to_class") or {}
        if index_to_class and str(raw_pred) in index_to_class:
            predicted_label = index_to_class[str(raw_pred)]
        else:
            predicted_label = str(raw_pred)
        probabilities: dict[str, float] = {}
        confidence = None
        if hasattr(estimator, "predict_proba"):
            proba = estimator.predict_proba(frame)[0]
            class_names = _class_names(estimator, self.loaded.schema)
            probabilities = {
                str(name): float(score)
                for name, score in zip(class_names, proba)
            }
            confidence = float(max(proba))
        return {
            "exception_type": predicted_label,
            "confidence": confidence,
            "probabilities": probabilities,
        }


def _class_names(estimator: Any, schema: dict) -> list[str]:
    mapping = schema.get("index_to_class") or {}
    classes = getattr(estimator, "classes_", None)
    if classes is None and hasattr(estimator, "named_steps"):
        final = list(estimator.named_steps.values())[-1]
        classes = getattr(final, "classes_", None)
    if classes is not None:
        names = []
        for item in classes:
            names.append(mapping.get(str(item), str(item)))
        return names
    return list(schema.get("classes") or [])
