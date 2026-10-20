from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ArticleWrite(BaseModel):
    language: str = Field(min_length=1, max_length=35)
    title: str = Field(min_length=1, max_length=512)
    slug: str = Field(min_length=1, max_length=512)
    text: str = Field(
        min_length=1,
        description="Article body in Markdown. Stored as Markdown, not HTML.",
    )

    @field_validator("language")
    @classmethod
    def lowercase_language(cls, value: str) -> str:
        return value.strip().lower()


class ArticleRetranslate(BaseModel):
    languages: list[str] | None = None


class ArticleTranslationOut(BaseModel):
    language: str
    title: str
    slug: str
    text: str
    origin: str

    model_config = ConfigDict(from_attributes=True)


class TranslationStatusOut(BaseModel):
    language: str
    status: str
    attempts: int = 0
    last_error: str | None = None
    next_attempt_at: datetime | None = None


class ArticleOut(BaseModel):
    id: int
    status: str
    source_language: str
    published_at: datetime | None
    translations: list[ArticleTranslationOut]
    translated_languages_count: int
    target_languages_count: int
    translations_status: list[TranslationStatusOut]


class ArticlePage(BaseModel):
    items: list[ArticleOut]
    page: int
    size: int
    total: int
