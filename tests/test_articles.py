import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import Article, ArticleTranslation


@pytest.fixture
def db(test_db):
    with Session(test_db.engine) as session:
        yield session


def test_article_stores_two_languages(db: Session):
    article = Article(
        source_language="en",
        translations=[
            ArticleTranslation(
                language="en",
                title="Hello",
                slug="hello",
                text="English body",
            ),
            ArticleTranslation(
                language="DE",
                title="Hallo",
                slug="hallo",
                text="German body",
            ),
        ],
    )
    db.add(article)
    db.commit()
    db.refresh(article)

    by_language = {item.language: item for item in article.translations}
    assert article.status == "draft"
    assert set(by_language) == {"en", "de"}
    assert by_language["en"].title == "Hello"
    assert by_language["en"].text == "English body"
    assert by_language["de"].title == "Hallo"
    assert by_language["de"].slug == "hallo"


def test_one_translation_per_language(db: Session):
    article = Article(
        source_language="en",
        translations=[
            ArticleTranslation(
                language="en",
                title="Hello",
                slug="hello",
                text="Body",
            )
        ],
    )
    db.add(article)
    db.commit()

    db.add(
        ArticleTranslation(
            article_id=article.id,
            language="en",
            title="Again",
            slug="hello-again",
            text="Other",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_slug_unique_per_language(db: Session):
    db.add(
        Article(
            source_language="en",
            translations=[
                ArticleTranslation(
                    language="en",
                    title="First",
                    slug="same-slug",
                    text="First body",
                )
            ],
        )
    )
    db.commit()

    db.add(
        Article(
            source_language="en",
            translations=[
                ArticleTranslation(
                    language="en",
                    title="Second",
                    slug="same-slug",
                    text="Second body",
                )
            ],
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
