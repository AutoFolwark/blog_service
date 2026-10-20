import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.db.session import engine
from database.models import ArticleTranslation, Base
from main import app

MARKDOWN = "# Hello\n\nThis is **markdown**."

ADMIN_HEADERS = {
    "X-User-ID": "admin-1",
    "X-User-Email": "admin@example.com",
    "X-User-Role": "admin",
    "X-Permissions": (
        "blog.article.all:read,blog.article.all:write,blog.article.publish:write"
    ),
    "X-Token-Expires": "2099-01-01T00:00:00Z",
}


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine):
        yield TestClient(app)
    Base.metadata.drop_all(engine)


def test_admin_accepts_markdown_with_raw_newlines_in_json(client: TestClient):
    body = (
        '{"language":"en","title":"Hello","slug":"hello","text":"# Title\n\nParagraph"}'
    )
    created = client.post(
        "/admin/v1/articles",
        headers={**ADMIN_HEADERS, "Content-Type": "application/json"},
        content=body,
    )
    assert created.status_code == 201
    assert created.json()["translations"][0]["text"] == "# Title\n\nParagraph"


def test_admin_rejects_broken_json(client: TestClient):
    created = client.post(
        "/admin/v1/articles",
        headers={**ADMIN_HEADERS, "Content-Type": "application/json"},
        content='{"language":',
    )
    assert created.status_code == 422


def test_admin_creates_changes_publishes_and_hides_markdown(client: TestClient):
    created = client.post(
        "/admin/v1/articles",
        headers=ADMIN_HEADERS,
        json={
            "language": "EN",
            "title": "Hello",
            "slug": "hello",
            "text": MARKDOWN,
        },
    )
    assert created.status_code == 201
    article = created.json()
    assert article["status"] == "draft"
    assert article["source_language"] == "en"
    assert article["translated_languages_count"] == 0
    assert article["target_languages_count"] == 5
    assert len(article["translations_status"]) == 5
    assert article["translations"] == [
        {
            "language": "en",
            "title": "Hello",
            "slug": "hello",
            "text": MARKDOWN,
            "origin": "source",
        }
    ]
    listed = client.get("/admin/v1/articles", headers=ADMIN_HEADERS)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    fetched = client.get(f"/admin/v1/articles/{article['id']}", headers=ADMIN_HEADERS)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == article["id"]

    with Session(engine) as session:
        session.add(
            ArticleTranslation(
                article_id=article["id"],
                language="de",
                title="Hallo",
                slug="hallo",
                text="## Hallo",
            )
        )
        session.commit()

    changed = client.put(
        f"/admin/v1/articles/{article['id']}",
        headers=ADMIN_HEADERS,
        json={
            "language": "en",
            "title": "Hello again",
            "slug": "hello",
            "text": MARKDOWN + "\n\nUpdated.",
        },
    )
    assert changed.status_code == 200
    by_language = {item["language"]: item for item in changed.json()["translations"]}
    assert by_language["en"]["title"] == "Hello again"
    assert by_language["en"]["text"] == MARKDOWN + "\n\nUpdated."
    assert by_language["de"]["title"] == "Hallo"
    assert by_language["de"]["text"] == "## Hallo"

    published = client.post(
        f"/admin/v1/articles/{article['id']}/publish",
        headers=ADMIN_HEADERS,
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None

    hidden = client.post(
        f"/admin/v1/articles/{article['id']}/hide",
        headers=ADMIN_HEADERS,
    )
    assert hidden.status_code == 200
    assert hidden.json()["status"] == "draft"
    assert hidden.json()["published_at"] is None


def test_admin_endpoints_reject_missing_permission(client: TestClient):
    headers = {**ADMIN_HEADERS, "X-Permissions": "blog.article.all:write"}
    created = client.post(
        "/admin/v1/articles",
        headers=ADMIN_HEADERS,
        json={
            "language": "en",
            "title": "Hello",
            "slug": "hello",
            "text": MARKDOWN,
        },
    )
    article_id = created.json()["id"]

    denied = client.post(
        f"/admin/v1/articles/{article_id}/publish",
        headers=headers,
    )
    assert denied.status_code == 403
