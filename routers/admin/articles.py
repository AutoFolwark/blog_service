from AuthTools.Permissions.dependencies import require_permissions
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import Permissions
from core.routing import LenientJSONRoute
from database.db.session import get_async_db
from schemas.article import ArticleOut, ArticlePage, ArticleRetranslate, ArticleWrite
from services.articles import (
    create_article,
    get_article,
    hide_article,
    list_articles,
    publish_article,
    retranslate_article,
    update_article,
)

admin_articles_router = APIRouter(
    prefix="/articles",
    tags=["Admin Articles"],
    route_class=LenientJSONRoute,
)


@admin_articles_router.get(
    "",
    response_model=ArticlePage,
    description=(
        "List articles, including drafts. "
        f"Required permission: {Permissions.ARTICLE_ALL_READ.value}"
    ),
    dependencies=[Depends(require_permissions(Permissions.ARTICLE_ALL_READ))],
)
async def list_all_articles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
) -> ArticlePage:
    return await list_articles(db, page, size)


@admin_articles_router.post(
    "",
    response_model=ArticleOut,
    status_code=201,
    description=(
        "Create an article. The text is HTML from the admin. "
        "Language is detected from the title and HTML when omitted. "
        "The slug is generated from the title when omitted. "
        f"Required permission: {Permissions.ARTICLE_ALL_WRITE.value}"
    ),
    dependencies=[Depends(require_permissions(Permissions.ARTICLE_ALL_WRITE))],
)
async def create_one_article(
    data: ArticleWrite,
    db: AsyncSession = Depends(get_async_db),
) -> ArticleOut:
    return await create_article(db, data)


@admin_articles_router.get(
    "/{article_id}",
    response_model=ArticleOut,
    description=(
        "Get one article, including drafts. "
        f"Required permission: {Permissions.ARTICLE_ALL_READ.value}"
    ),
    dependencies=[Depends(require_permissions(Permissions.ARTICLE_ALL_READ))],
)
async def get_one_article(
    article_id: int,
    db: AsyncSession = Depends(get_async_db),
) -> ArticleOut:
    return await get_article(db, article_id)


@admin_articles_router.put(
    "/{article_id}",
    response_model=ArticleOut,
    description=(
        "Create or change the article text for one language. The text is HTML. "
        "Editing the source re-queues automatic translations. "
        "Editing another language saves a manual translation. "
        f"Required permission: {Permissions.ARTICLE_ALL_WRITE.value}"
    ),
    dependencies=[Depends(require_permissions(Permissions.ARTICLE_ALL_WRITE))],
)
async def change_one_article(
    article_id: int,
    data: ArticleWrite,
    db: AsyncSession = Depends(get_async_db),
) -> ArticleOut:
    return await update_article(db, article_id, data)


@admin_articles_router.post(
    "/{article_id}/translate",
    response_model=ArticleOut,
    description=(
        "Queue translation from the source language again. "
        "This overwrites manual edits for the chosen languages. "
        f"Required permission: {Permissions.ARTICLE_ALL_WRITE.value}"
    ),
    dependencies=[Depends(require_permissions(Permissions.ARTICLE_ALL_WRITE))],
)
async def translate_one_article(
    article_id: int,
    data: ArticleRetranslate | None = None,
    db: AsyncSession = Depends(get_async_db),
) -> ArticleOut:
    return await retranslate_article(db, article_id, data)


@admin_articles_router.post(
    "/{article_id}/publish",
    response_model=ArticleOut,
    description=(
        "Publish an article. "
        f"Required permission: {Permissions.ARTICLE_PUBLISH_WRITE.value}"
    ),
    dependencies=[Depends(require_permissions(Permissions.ARTICLE_PUBLISH_WRITE))],
)
async def publish_one_article(
    article_id: int,
    db: AsyncSession = Depends(get_async_db),
) -> ArticleOut:
    return await publish_article(db, article_id)


@admin_articles_router.post(
    "/{article_id}/hide",
    response_model=ArticleOut,
    description=(
        "Hide an article by returning it to draft. "
        f"Required permission: {Permissions.ARTICLE_PUBLISH_WRITE.value}"
    ),
    dependencies=[Depends(require_permissions(Permissions.ARTICLE_PUBLISH_WRITE))],
)
async def hide_one_article(
    article_id: int,
    db: AsyncSession = Depends(get_async_db),
) -> ArticleOut:
    return await hide_article(db, article_id)
