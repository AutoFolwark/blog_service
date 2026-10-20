from datetime import datetime, timezone

from rfc9457 import BadRequestProblem, NotFoundProblem
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from database.models import Article, ArticleTranslation
from schemas.article import (
    ArticleOut,
    ArticlePage,
    ArticleRetranslate,
    ArticleTranslationOut,
    ArticleWrite,
    TranslationStatusOut,
)
from services.translation.jobs import (
    enqueue,
    languages_to_refresh,
    mark_job_done,
    target_languages,
)


class ArticleConflictProblem(BadRequestProblem):
    status = 409
    title = "Article conflict"


def serialize_article(article: Article) -> ArticleOut:
    targets = target_languages(article.source_language)
    translated = {
        item.language for item in article.translations if item.language in targets
    }
    jobs = {job.language: job for job in article.jobs}
    status: list[TranslationStatusOut] = []
    for language in targets:
        job = jobs.get(language)
        if job is not None:
            status.append(
                TranslationStatusOut(
                    language=language,
                    status=job.status,
                    attempts=job.attempts,
                    last_error=job.last_error,
                    next_attempt_at=job.next_attempt_at,
                )
            )
        elif language in translated:
            status.append(
                TranslationStatusOut(language=language, status="done", attempts=0)
            )
        else:
            status.append(
                TranslationStatusOut(language=language, status="pending", attempts=0)
            )
    return ArticleOut(
        id=article.id,
        status=article.status,
        source_language=article.source_language,
        published_at=article.published_at,
        translations=[
            ArticleTranslationOut.model_validate(item) for item in article.translations
        ],
        translated_languages_count=len(translated),
        target_languages_count=len(targets),
        translations_status=status,
    )


async def _load_article(session: AsyncSession, article_id: int) -> Article:
    result = await session.execute(
        select(Article)
        .where(Article.id == article_id)
        .options(
            selectinload(Article.translations),
            selectinload(Article.jobs),
        )
    )
    article = result.scalar_one_or_none()
    if article is None:
        raise NotFoundProblem(detail="Article not found")
    return article


async def _save(session: AsyncSession, article: Article) -> Article:
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ArticleConflictProblem(
            detail="An article already uses this slug for that language"
        ) from None
    return await _load_article(session, article.id)


def _translation(data: ArticleWrite, origin: str) -> ArticleTranslation:
    return ArticleTranslation(
        language=data.language,
        title=data.title,
        slug=data.slug,
        text=data.text,
        origin=origin,
    )


async def create_article(session: AsyncSession, data: ArticleWrite) -> ArticleOut:
    article = Article(
        source_language=data.language,
        translations=[_translation(data, "source")],
    )
    session.add(article)
    await session.flush()
    await enqueue(session, article, list(settings.TRANSLATION_LANGUAGES), False)
    return serialize_article(await _save(session, article))


async def update_article(
    session: AsyncSession, article_id: int, data: ArticleWrite
) -> ArticleOut:
    article = await _load_article(session, article_id)
    existing = {item.language: item for item in article.translations}
    translation = existing.get(data.language)
    if data.language == article.source_language:
        if translation is None:
            article.translations.append(_translation(data, "source"))
        else:
            translation.title = data.title
            translation.slug = data.slug
            translation.text = data.text
            translation.origin = "source"
        await enqueue(session, article, languages_to_refresh(article), False)
    else:
        if translation is None:
            article.translations.append(_translation(data, "manual"))
        else:
            translation.title = data.title
            translation.slug = data.slug
            translation.text = data.text
            translation.origin = "manual"
        await mark_job_done(session, article.id, data.language)
    return serialize_article(await _save(session, article))


async def publish_article(session: AsyncSession, article_id: int) -> ArticleOut:
    article = await _load_article(session, article_id)
    article.status = "published"
    article.published_at = datetime.now(timezone.utc)
    return serialize_article(await _save(session, article))


async def hide_article(session: AsyncSession, article_id: int) -> ArticleOut:
    article = await _load_article(session, article_id)
    article.status = "draft"
    article.published_at = None
    return serialize_article(await _save(session, article))


async def get_article(session: AsyncSession, article_id: int) -> ArticleOut:
    return serialize_article(await _load_article(session, article_id))


async def list_articles(session: AsyncSession, page: int, size: int) -> ArticlePage:
    total = await session.scalar(select(func.count()).select_from(Article))
    result = await session.execute(
        select(Article)
        .options(
            selectinload(Article.translations),
            selectinload(Article.jobs),
        )
        .order_by(Article.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = result.scalars().unique().all()
    return ArticlePage(
        items=[serialize_article(item) for item in items],
        page=page,
        size=size,
        total=total or 0,
    )


async def retranslate_article(
    session: AsyncSession,
    article_id: int,
    data: ArticleRetranslate | None,
) -> ArticleOut:
    article = await _load_article(session, article_id)
    targets = target_languages(article.source_language)
    if data is None or data.languages is None:
        chosen = targets
    else:
        chosen = []
        for language in data.languages:
            code = language.strip().lower()
            if code not in targets:
                raise BadRequestProblem(detail=f"Unsupported language: {code}")
            if code not in chosen:
                chosen.append(code)
    await enqueue(session, article, chosen, True)
    return serialize_article(await _save(session, article))
