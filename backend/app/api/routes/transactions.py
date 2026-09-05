from fastapi import APIRouter, HTTPException

from backend.app.database.repositories.bank_repository import BankRepository
from backend.app.database.repositories.payment_repository import PaymentRepository
from backend.app.database.repositories.settlement_repository import SettlementRepository

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


@router.get("/{source_type}/{source_id}")
def get_transaction(source_type: str, source_id: str) -> dict:
    kind = source_type.strip().lower()
    row = None
    if kind in {"bank", "bank_record", "bank_records"}:
        row = BankRepository().get_by_id(source_id)
    elif kind in {"payment", "payments"}:
        row = PaymentRepository().get_by_id(source_id)
    elif kind in {"order", "orders"}:
        row = PaymentRepository().get_order(source_id)
    elif kind in {"settlement", "settlements"}:
        row = SettlementRepository().get_by_id(source_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported source_type '{source_type}'")
    if not row:
        raise HTTPException(status_code=404, detail=f"{source_type} not found: {source_id}")
    return {"source_type": kind, "record": _jsonable(row)}


def _jsonable(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        out[key] = str(value) if hasattr(value, "isoformat") or hasattr(value, "quantize") else value
    return out
