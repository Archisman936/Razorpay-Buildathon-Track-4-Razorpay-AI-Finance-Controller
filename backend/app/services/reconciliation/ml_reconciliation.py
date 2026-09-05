"""Score candidate settlements and decide match vs ambiguity."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.core.config import Settings, get_settings
from backend.app.core.constants import STATUS_AMBIGUOUS, STATUS_ML_MATCHED, STATUS_UNMATCHED
from backend.app.ml.model_loader import ModelLoader, get_model_loader
from backend.app.ml.reconciliation_model import ReconciliationModel
from backend.app.services.reconciliation.feature_builder import build_candidate_feature_rows


@dataclass
class MlMatchResult:
    status: str
    matched_record_id: str | None
    match_probability: float | None
    runner_up_probability: float | None
    confidence_margin: float | None
    threshold: float
    candidate_records: list[dict] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    explanation_facts: dict = field(default_factory=dict)


class MlReconciliationService:
    def __init__(
        self,
        loader: ModelLoader | None = None,
        settings: Settings | None = None,
        model: ReconciliationModel | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.loader = loader or get_model_loader()
        self.model = model

    def _model(self) -> ReconciliationModel:
        if self.model is None:
            self.model = ReconciliationModel.from_loader(self.loader)
        return self.model

    def score_candidates(self, bank: dict, settlements: list[dict]) -> MlMatchResult:
        if not settlements:
            return MlMatchResult(
                status=STATUS_UNMATCHED,
                matched_record_id=None,
                match_probability=None,
                runner_up_probability=None,
                confidence_margin=None,
                threshold=self._threshold(),
                reason_codes=["NO_CANDIDATES"],
                explanation_facts={"candidate_count": 0},
            )

        rows = build_candidate_feature_rows(bank, settlements, self.loader)
        scores = self._model().score_rows(rows)
        ranked = []
        for row, score in zip(rows, scores):
            ranked.append(
                {
                    "record_id": row.get("target_id"),
                    "score": score,
                    "absolute_amount_difference": row.get("absolute_amount_difference"),
                    "date_difference_days": row.get("date_difference_days"),
                    "reference_exact_match": row.get("reference_exact_match"),
                    "utr_similarity": row.get("utr_similarity"),
                    "candidate_rank_by_amount": row.get("candidate_rank_by_amount"),
                }
            )
        ranked.sort(key=lambda item: item["score"], reverse=True)

        top = ranked[0]
        runner = ranked[1] if len(ranked) > 1 else None
        top_score = float(top["score"])
        runner_score = float(runner["score"]) if runner else None
        margin = None if runner_score is None else top_score - runner_score
        threshold = self._threshold()
        ambiguous = (
            runner_score is not None
            and margin is not None
            and margin < self.settings.ambiguity_margin
            and runner_score >= threshold * 0.5
        )

        if top_score < threshold:
            status = STATUS_UNMATCHED
            codes = ["ML_BELOW_THRESHOLD"]
            matched_id = None
        elif ambiguous:
            status = STATUS_AMBIGUOUS
            codes = ["ML_AMBIGUOUS_MARGIN"]
            matched_id = top["record_id"]
        else:
            status = STATUS_ML_MATCHED
            codes = ["ML_TOP_CANDIDATE"]
            matched_id = top["record_id"]

        return MlMatchResult(
            status=status,
            matched_record_id=matched_id,
            match_probability=top_score,
            runner_up_probability=runner_score,
            confidence_margin=margin,
            threshold=threshold,
            candidate_records=ranked,
            reason_codes=codes,
            explanation_facts={
                "threshold": threshold,
                "ambiguity_margin": self.settings.ambiguity_margin,
                "candidate_count": len(ranked),
                "top_record_id": top["record_id"],
                "runner_up_record_id": runner["record_id"] if runner else None,
            },
        )

    def _threshold(self) -> float:
        schema = self.loader.get_reconciliation_schema()
        if schema.get("threshold") is not None:
            return float(schema["threshold"])
        return 0.275
