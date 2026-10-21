import asyncio
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

for _key in (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_PROFILE",
    "AWS_DEFAULT_PROFILE",
    "AWS_SECURITY_TOKEN",
):
    os.environ.pop(_key, None)
os.environ["AWS_SHARED_CREDENTIALS_FILE"] = "/dev/null"
os.environ["AWS_CONFIG_FILE"] = "/dev/null"
os.environ["TRANSLATION_ENABLED"] = "false"


def pytest_configure():
    from config import settings

    settings.TRANSLATION_REQUEST_DELAY_SECONDS = 0
    settings.TRANSLATION_ENABLED = False


def pytest_runtest_teardown(item):
    from database.db.session import engine_async

    asyncio.run(engine_async.dispose())


class TestDatabase:
    def __init__(self, engine, sessions):
        self.engine = engine
        self.sessions = sessions


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    from database.db.session import get_async_db
    from database.models import Base
    from main import app

    path = tmp_path / "test.sqlite"
    sync_engine = create_engine(f"sqlite:///{path}")
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    sessions = async_sessionmaker(
        bind=async_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    Base.metadata.create_all(sync_engine)
    monkeypatch.setattr("services.translation.jobs.AsyncSessionLocal", sessions)

    async def override_db():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_async_db] = override_db
    try:
        yield TestDatabase(sync_engine, sessions)
    finally:
        app.dependency_overrides.pop(get_async_db, None)
        Base.metadata.drop_all(sync_engine)
        sync_engine.dispose()
        asyncio.run(async_engine.dispose())


@pytest.fixture
def client(test_db):
    from main import app

    yield TestClient(app)
