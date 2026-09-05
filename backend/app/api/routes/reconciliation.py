from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.dependencies import get_pipeline
from backend.app.schemas.reconciliation import ReconciliationResult, ReconciliationRunRequest
from backend.app.services.orchestration.pipeline import ReconciliationPipeline
from backend.app.services.reconciliation.reconciliation_service import RecordNotFoundError

router = APIRouter(prefix="/api/v1/reconciliation", tags=["reconciliation"])


@router.post("/run", response_model=ReconciliationResult)
def run_reconciliation(
    payload: ReconciliationRunRequest,
    pipeline: ReconciliationPipeline = Depends(get_pipeline),
) -> dict:
    try:
        return pipeline.run_case(
            source_type=payload.source_type,
            source_id=payload.source_id,
            include_ml=payload.include_ml,
            include_exception=payload.include_exception,
        )
    except RecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
