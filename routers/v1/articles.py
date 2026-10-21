from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.db.session import get_async_db
from schemas.article import PublicArticleOut, PublicArticlePage
from services.articles import get_published_article, list_published_articles

public_articles_router = APIRouter(prefix="/articles", tags=["Articles"])


@public_articles_router.get(
    "",
    response_model=PublicArticlePage,
    description="List published articles in one language. No authentication.",
)
async def list_public_articles(
    language: str = Query("en", min_length=1, max_length=35),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
) -> PublicArticlePage:
    return await list_published_articles(db, language, page, size)


@public_articles_router.get(
    "/{language}/{slug}",
    response_model=PublicArticleOut,
    description="Get one published article by language and slug. No authentication.",
)
async def get_public_article(
    language: str,
    slug: str,
    db: AsyncSession = Depends(get_async_db),
) -> PublicArticleOut:
    return await get_published_article(db, language, slug)
