"""FastAPI 라우터. prefix 는 모두 `/api/v1` (버저닝을 처음부터)."""

from app.routers.places import router as places_router
from app.routers.videos import router as videos_router

__all__ = ["places_router", "videos_router"]
