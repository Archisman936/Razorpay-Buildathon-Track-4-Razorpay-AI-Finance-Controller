import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import api_router
from backend.app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Razorpay AI Finance Controller",
        version="0.1.0",
        description="Deterministic + ML reconciliation over normalized PostgreSQL data.",
    )

    # Enable CORS for Vercel, local dev, and custom client domains
    cors_origins_env = os.getenv("CORS_ORIGINS", "*")
    origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()] or ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True if "*" not in origins else False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()
