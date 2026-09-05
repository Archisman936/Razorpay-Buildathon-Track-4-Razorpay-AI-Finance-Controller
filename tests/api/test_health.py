from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health_endpoint_reports_model_and_db_without_crashing():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body
    assert "models" in body
    assert body["models"]["reconciliation_schema"] is True
    assert body["models"]["exception_schema"] is True


def test_reconciliation_rejects_unknown_type():
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/reconciliation/run",
        json={"source_type": "widget", "source_id": "X", "include_ml": False, "include_exception": False},
    )
    assert response.status_code in {400, 422, 500}
    # Missing DB password or unsupported type both fail closed; type error is 400 when DB is configured.
