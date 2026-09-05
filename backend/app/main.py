import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes import api_router
from backend.app.core.logging import configure_logging, get_logger
from backend.app.database.init_db import ensure_database_initialized

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run auto-initialization on startup
    try:
        res = ensure_database_initialized()
        logger.info("Database startup check: %s", res)
    except Exception as exc:
        logger.warning("Auto-database initialization on startup encountered: %s", exc)
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Razorpay AI Finance Controller",
        version="0.1.0",
        description="Deterministic + ML reconciliation over normalized PostgreSQL data.",
        lifespan=lifespan,
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

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled server error processing %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "error": type(exc).__name__},
        )

    app.include_router(api_router)
    return app


app = create_app()

