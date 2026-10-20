from contextlib import asynccontextmanager

import redis.asyncio as redis
import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_problem.handler import add_exception_handler, new_exception_handler

from config import settings
from routers.admin.articles import admin_articles_router
from routers.health import health_router
from services.translation.jobs import reset_stale_running
from services.translation.scheduler import (
    build_scheduler,
    validate_translation_languages,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = redis.from_url(settings.REDIS_URL)
    FastAPICache.init(RedisBackend(redis_client), prefix="blog-cache")
    scheduler = None
    if settings.TRANSLATION_ENABLED:
        validate_translation_languages()
        await reset_stale_running()
        scheduler = build_scheduler()
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


docs_url = "/docs" if settings.enable_docs else None
redoc_url = "/redoc" if settings.enable_docs else None
openapi_url = "/openapi.json" if settings.enable_docs else None
app = FastAPI(
    lifespan=lifespan,
    root_path=settings.ROOT_PATH,
    title="Blog Service",
    description="Bidmax blog API",
    version="0.0.1",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

eh = new_exception_handler()
add_exception_handler(app, eh)

public_v1_router = APIRouter(prefix="/public/v1")
app.include_router(public_v1_router)

admin_v1_router = APIRouter(prefix="/admin/v1")
admin_v1_router.include_router(admin_articles_router)
app.include_router(admin_v1_router)

app.include_router(health_router, tags=["Health"])


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8002)
