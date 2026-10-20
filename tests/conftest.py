import asyncio
import os

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
