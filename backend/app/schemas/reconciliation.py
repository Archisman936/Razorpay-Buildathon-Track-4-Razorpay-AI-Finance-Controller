from typing import Any, Optional

from pydantic import BaseModel, Field


class ReconciliationRunRequest(BaseModel):
    source_type: str = Field(..., examples=["bank_record"])
    source_id: str = Field(..., examples=["BNK_000001"])
    include_ml: bool = True
    include_exception: bool = True


class ReconciliationResult(BaseModel):
    case_id: str
    source_record_id: str
    source_type: str
    status: str
    reconciliation_method: str
    matched_record_id: Optional[str] = None
    candidate_records: list[dict[str, Any]] = Field(default_factory=list)
    match_probability: Optional[float] = None
    runner_up_probability: Optional[float] = None
    confidence_margin: Optional[float] = None
    exception_type: Optional[str] = None
    exception_confidence: Optional[float] = None
    exception: Optional[dict[str, Any]] = None
    amount_difference: Optional[float] = None
    date_difference: Optional[int] = None
    reason_codes: list[str] = Field(default_factory=list)
    explanation_facts: dict[str, Any] = Field(default_factory=dict)
