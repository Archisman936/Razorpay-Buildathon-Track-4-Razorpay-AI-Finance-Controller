"""Dashboard summary endpoint — real metrics from PostgreSQL."""

from fastapi import APIRouter
from backend.app.database.connection import fetch_one, fetch_all

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary() -> dict:
    """Return real reconciliation metrics derived from the database."""

    # Bank record reconciliation stats (bank records vs settlements)
    bank_total = fetch_one("SELECT COUNT(*) AS cnt FROM bank_records") or {}
    bank_reconciled = fetch_one(
        "SELECT COUNT(*) AS cnt FROM bank_records WHERE settlement_id IS NOT NULL"
    ) or {}
    bank_unreconciled = fetch_one(
        "SELECT COUNT(*) AS cnt FROM bank_records WHERE settlement_id IS NULL"
    ) or {}

    total = int(bank_total.get("cnt", 0))
    reconciled = int(bank_reconciled.get("cnt", 0))
    unreconciled = int(bank_unreconciled.get("cnt", 0))
    rate = round((reconciled / total * 100), 2) if total > 0 else 0.0

    # Total discrepancy: sum of amounts in unreconciled CREDIT bank records
    discrepancy_row = fetch_one(
        "SELECT COALESCE(SUM(amount),0) AS total FROM bank_records "
        "WHERE settlement_id IS NULL AND transaction_type = %s",
        ("CREDIT",),
    ) or {}
    total_discrepancy = float(discrepancy_row.get("total", 0))

    # Category breakdown in bank records
    category_rows = fetch_all(
        "SELECT category, COUNT(*) AS cnt FROM bank_records GROUP BY category ORDER BY cnt DESC"
    )
    category_breakdown = [
        {"category": r["category"] or "UNKNOWN", "count": int(r["cnt"])}
        for r in category_rows
    ]

    # Payment status breakdown
    payment_status_rows = fetch_all(
        "SELECT status, COUNT(*) AS cnt FROM payments GROUP BY status ORDER BY cnt DESC"
    )
    payment_status = [
        {"status": r["status"] or "UNKNOWN", "count": int(r["cnt"])}
        for r in payment_status_rows
    ]

    # Settlement amounts summary
    settlement_row = fetch_one(
        "SELECT COUNT(*) AS cnt, "
        "COALESCE(SUM(gross_amount),0) AS gross, "
        "COALESCE(SUM(net_amount),0) AS net, "
        "COALESCE(SUM(total_fees),0) AS fees "
        "FROM settlements"
    ) or {}

    # Recent bank records (last 10 by transaction_date)
    recent_rows = fetch_all(
        "SELECT bank_record_id, merchant_id, transaction_date, amount, "
        "transaction_type, category, settlement_id "
        "FROM bank_records ORDER BY transaction_date DESC, bank_record_id DESC LIMIT 10"
    )
    recent_records = []
    for r in recent_rows:
        recent_records.append({
            "id": r["bank_record_id"],
            "merchant_id": r["merchant_id"],
            "date": str(r["transaction_date"]) if r["transaction_date"] else None,
            "amount": float(r["amount"]) if r["amount"] else 0,
            "type": r["transaction_type"],
            "category": r["category"],
            "reconciled": r["settlement_id"] is not None,
        })

    # Counts per table
    table_counts = {}
    for tbl in ["bank_records", "payments", "settlements", "orders", "invoices", "refunds"]:
        row = fetch_one(f"SELECT COUNT(*) AS cnt FROM {tbl}") or {}
        table_counts[tbl] = int(row.get("cnt", 0))

    return {
        "reconciliation": {
            "total": total,
            "reconciled": reconciled,
            "unreconciled": unreconciled,
            "rate": rate,
            "total_discrepancy_amount": total_discrepancy,
        },
        "category_breakdown": category_breakdown,
        "payment_status": payment_status,
        "settlements": {
            "count": int(settlement_row.get("cnt", 0)),
            "gross_amount": float(settlement_row.get("gross", 0)),
            "net_amount": float(settlement_row.get("net", 0)),
            "total_fees": float(settlement_row.get("fees", 0)),
        },
        "recent_records": recent_records,
        "table_counts": table_counts,
    }
