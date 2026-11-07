import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

logger = logging.getLogger(__name__)
router = APIRouter()


def _stores_available(request: Request) -> bool:
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        request.app.state.qdrant.get_collections()
    except Exception:
        logger.warning("Health check failed", exc_info=True)
        return False
    return True


@router.get("/api/health")
def health(request: Request) -> JSONResponse:
    if _stores_available(request):
        return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "unavailable"}, status_code=503)
