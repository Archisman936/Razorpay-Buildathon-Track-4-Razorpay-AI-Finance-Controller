from fastapi import APIRouter

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.reconciliation import router as reconciliation_router
from backend.app.api.routes.transactions import router as transactions_router
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.dashboard import router as dashboard_router
from backend.app.api.routes.upload import router as upload_router
from backend.app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(reconciliation_router)
api_router.include_router(transactions_router)
api_router.include_router(chat_router)
api_router.include_router(dashboard_router)
api_router.include_router(upload_router)
api_router.include_router(system_router)

