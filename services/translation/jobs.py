from datetime import datetime, timedelta, timezone

from slugify import slugify
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from config import settings
from database.db.session import AsyncSessionLocal
from database.models import Article, ArticleTranslation, ArticleTranslationJob
from services.translation.markdown import translate_markdown
from services.translation.translator import translate


def target_languages(source_language: str) -> list[str]:
    return [
        language
        for language in settings.TRANSLATION_LANGUAGES
        if language != source_language
    ]


async def enqueue(
    session, article: Article, languages: list[str], overwrite_manual: bool
) -> None:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(ArticleTranslationJob).where(
            ArticleTranslationJob.article_id == article.id
        )
    )
    existing = {job.language: job for job in result.scalars()}
    for language in languages:
        if language == article.source_language:
            continue
        job = existing.get(language)
        if job is None:
            job = ArticleTranslationJob(article_id=article.id, language=language)
            session.add(job)
            existing[language] = job
        job.status = "pending"
        job.overwrite_manual = overwrite_manual
        job.attempts = 0
        job.last_error = None
        job.next_attempt_at = now


async def mark_job_done(session, article_id: int, language: str) -> None:
    job = await session.scalar(
        select(ArticleTranslationJob).where(
            ArticleTranslationJob.article_id == article_id,
            ArticleTranslationJob.language == language,
        )
    )
    if job is None:
        return
    job.status = "done"
    job.last_error = None
    job.overwrite_manual = False


def languages_to_refresh(article: Article) -> list[str]:
    existing = {item.language: item for item in article.translations}
    chosen = []
    for language in target_languages(article.source_language):
        translation = existing.get(language)
        if translation is None or translation.origin == "auto":
            chosen.append(language)
    return chosen


async def reset_stale_running() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(ArticleTranslationJob)
            .where(ArticleTranslationJob.status == "running")
            .values(status="pending", next_attempt_at=datetime.now(timezone.utc))
        )
        await session.commit()


async def _unique_slug(session, language: str, title: str, article_id: int) -> str:
    base = slugify(title, max_length=480) or f"article-{article_id}"
    taken = await session.scalar(
        select(ArticleTranslation.id).where(
            ArticleTranslation.language == language,
            ArticleTranslation.slug == base,
            ArticleTranslation.article_id != article_id,
        )
    )
    if taken is None:
        return base
    return f"{base}-{article_id}"


async def _fail_job(session, job_id: int, exc: Exception) -> None:
    job = await session.get(ArticleTranslationJob, job_id)
    if job is None:
        return
    job.attempts += 1
    job.last_error = str(exc)[:2000]
    if job.attempts >= settings.TRANSLATION_MAX_ATTEMPTS:
        job.status = "failed"
    else:
        delay = settings.TRANSLATION_RETRY_BASE_SECONDS * (2 ** (job.attempts - 1))
        job.status = "pending"
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    await session.commit()


async def _process_one(job_id: int) -> None:
    async with AsyncSessionLocal() as session:
        job = await session.get(ArticleTranslationJob, job_id)
        if job is None or job.status != "pending":
            return
        job.status = "running"
        await session.commit()
        try:
            result = await session.execute(
                select(Article)
                .where(Article.id == job.article_id)
                .options(selectinload(Article.translations))
            )
            article = result.scalar_one()
            source = next(
                item
                for item in article.translations
                if item.language == article.source_language
            )
            existing = {item.language: item for item in article.translations}
            current = existing.get(job.language)
            if (
                current is not None
                and current.origin == "manual"
                and not job.overwrite_manual
            ):
                job.status = "done"
                job.last_error = None
                await session.commit()
                return
            title = await translate(source.title, source.language, job.language)
            body = await translate_markdown(source.text, source.language, job.language)
            slug = await _unique_slug(session, job.language, title, article.id)
            if current is None:
                session.add(
                    ArticleTranslation(
                        article_id=article.id,
                        language=job.language,
                        title=title,
                        slug=slug,
                        text=body,
                        origin="auto",
                    )
                )
            else:
                current.title = title
                current.slug = slug
                current.text = body
                current.origin = "auto"
            job.status = "done"
            job.last_error = None
            await session.commit()
        except Exception as exc:
            await session.rollback()
            await _fail_job(session, job_id, exc)


async def process_due_jobs() -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ArticleTranslationJob.id)
            .where(
                ArticleTranslationJob.status == "pending",
                ArticleTranslationJob.next_attempt_at <= now,
            )
            .order_by(ArticleTranslationJob.next_attempt_at)
            .limit(settings.TRANSLATION_BATCH_SIZE)
        )
        job_ids = list(result.scalars())
    for job_id in job_ids:
        await _process_one(job_id)
