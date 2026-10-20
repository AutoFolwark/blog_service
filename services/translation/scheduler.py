from apscheduler.schedulers.asyncio import AsyncIOScheduler
from googletrans import LANGUAGES

from config import settings
from services.translation.jobs import process_due_jobs


def validate_translation_languages() -> None:
    missing = [
        language
        for language in settings.TRANSLATION_LANGUAGES
        if language not in LANGUAGES
    ]
    if missing:
        raise RuntimeError(f"Unknown translation languages: {', '.join(missing)}")


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        process_due_jobs,
        "interval",
        seconds=settings.TRANSLATION_INTERVAL_SECONDS,
        max_instances=1,
        coalesce=True,
        id="article_translations",
    )
    return scheduler
