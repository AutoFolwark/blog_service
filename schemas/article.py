from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ArticleWrite(BaseModel):
    language: str | None = Field(
        default=None,
        max_length=35,
        description="Language code. Detected from the title and HTML when omitted.",
    )
    title: str = Field(min_length=1, max_length=512)
    slug: str | None = Field(
        default=None,
        max_length=512,
        description="Public slug. Generated from the title when omitted.",
    )
    text: str = Field(
        min_length=1,
        description="Article body as HTML supplied by the admin. Stored as HTML.",
    )

    @field_validator("language")
    @classmethod
    def lowercase_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned or None

    @field_validator("slug")
    @classmethod
    def empty_slug_is_missing(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


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


class PublicArticleCard(BaseModel):
    id: int
    language: str
    title: str
    slug: str
    description: str
    published_at: datetime


class PublicTranslationLink(BaseModel):
    language: str
    title: str
    slug: str


class PublicArticleOut(PublicArticleCard):
    text: str
    translations: list[PublicTranslationLink]


class PublicArticlePage(BaseModel):
    items: list[PublicArticleCard]
    page: int
    size: int
    total: int
