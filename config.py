from enum import Enum

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.utils import load_secrets

load_dotenv()


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class Permissions(str, Enum):
    ARTICLE_ALL_READ = "blog.article.all:read"
    ARTICLE_ALL_WRITE = "blog.article.all:write"
    ARTICLE_PUBLISH_WRITE = "blog.article.publish:write"


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "blog-service"
    DEBUG: bool = True
    ROOT_PATH: str = ""
    ENVIRONMENT: Environment = Environment.DEVELOPMENT

    @property
    def enable_docs(self) -> bool:
        return self.ENVIRONMENT in [Environment.DEVELOPMENT]

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = Field(
        default="test_db",
        validation_alias=AliasChoices("BLOG_DB_NAME", "DB_NAME"),
    )
    DB_USER: str = Field(
        default="postgres",
        validation_alias=AliasChoices("BLOG_DB_USER", "DB_USER"),
    )
    DB_PASS: str = Field(
        default="testpass",
        validation_alias=AliasChoices("BLOG_DB_PASS", "DB_PASS"),
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Translation
    TRANSLATION_ENABLED: bool = True
    TRANSLATION_LANGUAGES: list[str] = ["en", "pl", "uk", "cs", "de", "sl"]
    TRANSLATION_INTERVAL_SECONDS: int = 60
    TRANSLATION_BATCH_SIZE: int = 10
    TRANSLATION_MAX_ATTEMPTS: int = 5
    TRANSLATION_RETRY_BASE_SECONDS: int = 60
    TRANSLATION_REQUEST_DELAY_SECONDS: float = 1.0
    TRANSLATION_CHUNK_CHARS: int = 4500

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


load_secrets()
settings = Settings()
