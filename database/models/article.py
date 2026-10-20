from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from database.models.base import Base


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published')",
            name="ck_articles_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_language: Mapped[str] = mapped_column(String(35), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft"
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    translations: Mapped[list["ArticleTranslation"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list["ArticleTranslationJob"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
    )


class ArticleTranslation(Base):
    __tablename__ = "article_translations"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "language",
            name="uq_article_translations_article_language",
        ),
        UniqueConstraint(
            "language",
            "slug",
            name="uq_article_translations_language_slug",
        ),
        CheckConstraint(
            "origin IN ('source', 'auto', 'manual')",
            name="ck_article_translations_origin",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(35), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    slug: Mapped[str] = mapped_column(String(512), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(
        String(16), nullable=False, default="source", server_default="source"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    article: Mapped[Article] = relationship(back_populates="translations")

    @validates("language")
    def _lowercase_language(self, _key: str, value: str) -> str:
        return value.lower()


class ArticleTranslationJob(Base):
    __tablename__ = "article_translation_jobs"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "language",
            name="uq_article_translation_jobs_article_language",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed')",
            name="ck_article_translation_jobs_status",
        ),
        Index("ix_article_translation_jobs_due", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(35), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    overwrite_manual: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    attempts: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    article: Mapped[Article] = relationship(back_populates="jobs")

    @validates("language")
    def _lowercase_language(self, _key: str, value: str) -> str:
        return value.lower()
