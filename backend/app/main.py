from fastapi import FastAPI

from backend.app.api.routes import api_router
from backend.app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Razorpay AI Finance Controller",
        version="0.1.0",
        description="Deterministic + ML reconciliation over normalized PostgreSQL data.",
    )
    app.include_router(api_router)
    return app


app = create_app()
