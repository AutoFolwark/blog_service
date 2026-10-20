import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config import settings
from database.db.session import AsyncSessionLocal, engine
from database.models import Article, ArticleTranslationJob, Base
from schemas.article import ArticleRetranslate, ArticleWrite
from services.articles import (
    create_article,
    get_article,
    retranslate_article,
    update_article,
)
from services.translation.jobs import process_due_jobs
from services.translation.translator import TranslationError


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


SOURCE = ArticleWrite(
    language="en",
    title="Hello",
    slug="hello",
    text="# Hello\n\nBody",
)


@pytest.fixture
def tables():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _patch_translate(monkeypatch, translate):
    monkeypatch.setattr("services.translation.jobs.translate", translate)
    monkeypatch.setattr("services.translation.markdown.translate", translate)


async def fake_translate(text, src, dest):
    return f"[{dest}] {text}"


async def failing_translate(text, src, dest):
    raise TranslationError("nope")


def test_process_due_jobs_translates_every_target_language(tables, monkeypatch):
    _patch_translate(monkeypatch, fake_translate)

    async def scenario():
        async with AsyncSessionLocal() as session:
            created = await create_article(session, SOURCE)
        assert created.target_languages_count == 5
        assert created.translated_languages_count == 0
        assert len(created.translations_status) == 5
        await process_due_jobs()
        async with AsyncSessionLocal() as session:
            loaded = await get_article(session, created.id)
        assert loaded.translated_languages_count == 5
        assert {item.status for item in loaded.translations_status} == {"done"}
        german = next(item for item in loaded.translations if item.language == "de")
        assert german.origin == "auto"
        assert german.title == "[de] Hello"
        assert "[de]" in german.text

    asyncio.run(scenario())


def test_failed_translation_retries_then_fails(tables, monkeypatch):
    _patch_translate(monkeypatch, failing_translate)
    previous = settings.TRANSLATION_MAX_ATTEMPTS
    settings.TRANSLATION_MAX_ATTEMPTS = 2

    async def scenario():
        async with AsyncSessionLocal() as session:
            created = await create_article(session, SOURCE)
        await process_due_jobs()
        async with AsyncSessionLocal() as session:
            jobs = list(
                (
                    await session.execute(
                        select(ArticleTranslationJob).where(
                            ArticleTranslationJob.article_id == created.id
                        )
                    )
                ).scalars()
            )
        assert jobs
        assert all(job.attempts == 1 for job in jobs)
        assert all(job.status == "pending" for job in jobs)
        assert all(job.last_error and "nope" in job.last_error for job in jobs)
        assert all(
            _as_utc(job.next_attempt_at) > datetime.now(timezone.utc) for job in jobs
        )

        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        async with AsyncSessionLocal() as session:
            rows = list(
                (
                    await session.execute(
                        select(ArticleTranslationJob).where(
                            ArticleTranslationJob.article_id == created.id
                        )
                    )
                ).scalars()
            )
            for row in rows:
                row.next_attempt_at = past
            await session.commit()
        await process_due_jobs()
        async with AsyncSessionLocal() as session:
            failed = list(
                (
                    await session.execute(
                        select(ArticleTranslationJob).where(
                            ArticleTranslationJob.article_id == created.id
                        )
                    )
                ).scalars()
            )
        assert all(job.status == "failed" for job in failed)
        assert all(job.attempts == 2 for job in failed)

    try:
        asyncio.run(scenario())
    finally:
        settings.TRANSLATION_MAX_ATTEMPTS = previous


def test_source_edit_keeps_manual_and_translate_overwrites_it(tables, monkeypatch):
    _patch_translate(monkeypatch, fake_translate)

    async def scenario():
        async with AsyncSessionLocal() as session:
            created = await create_article(session, SOURCE)
        await process_due_jobs()
        async with AsyncSessionLocal() as session:
            await update_article(
                session,
                created.id,
                ArticleWrite(
                    language="de",
                    title="Manuell",
                    slug="manuell",
                    text="Manueller Text",
                ),
            )
            await update_article(
                session,
                created.id,
                ArticleWrite(
                    language="en",
                    title="Hello again",
                    slug="hello",
                    text="# Hello again",
                ),
            )
            article = await session.execute(
                select(Article)
                .where(Article.id == created.id)
                .options(selectinload(Article.jobs), selectinload(Article.translations))
            )
            loaded = article.scalar_one()
            jobs = {job.language: job for job in loaded.jobs}
            assert jobs["de"].status == "done"
            assert jobs["pl"].status == "pending"
        await process_due_jobs()
        async with AsyncSessionLocal() as session:
            kept = await get_article(session, created.id)
        german = next(item for item in kept.translations if item.language == "de")
        assert german.origin == "manual"
        assert german.title == "Manuell"
        polish = next(item for item in kept.translations if item.language == "pl")
        assert polish.title == "[pl] Hello again"

        async with AsyncSessionLocal() as session:
            await retranslate_article(
                session, created.id, ArticleRetranslate(languages=["de"])
            )
        await process_due_jobs()
        async with AsyncSessionLocal() as session:
            overwritten = await get_article(session, created.id)
        german = next(
            item for item in overwritten.translations if item.language == "de"
        )
        assert german.origin == "auto"
        assert german.title == "[de] Hello again"

    asyncio.run(scenario())
