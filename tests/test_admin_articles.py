from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.models import ArticleTranslation

HTML = "<h1>Hello</h1>\n\n<p>This is <strong>html</strong>.</p>"

ADMIN_HEADERS = {
    "X-User-ID": "admin-1",
    "X-User-Email": "admin@example.com",
    "X-User-Role": "admin",
    "X-Permissions": (
        "blog.article.all:read,blog.article.all:write,blog.article.publish:write"
    ),
    "X-Token-Expires": "2099-01-01T00:00:00Z",
}


def test_admin_accepts_html_with_raw_newlines_in_json(client: TestClient):
    body = (
        '{"language":"en","title":"Hello","slug":"hello",'
        '"text":"<h1>Title</h1>\n\n<p>Paragraph</p>"}'
    )
    created = client.post(
        "/admin/v1/articles",
        headers={**ADMIN_HEADERS, "Content-Type": "application/json"},
        content=body,
    )
    assert created.status_code == 201
    assert (
        created.json()["translations"][0]["text"]
        == "<h1>Title</h1>\n\n<p>Paragraph</p>"
    )


def test_admin_accepts_html_quotes_inside_json_string(client: TestClient):
    body = """{
  "language": "pl",
  "title": "Pod Młotek",
  "slug": "pod-mlotek",
  "text": "<article>
        <img src="https://images.unsplash.com/photo.jpg" alt="Drewniany młotek">
        <p>Sotheby's oraz Christie's</p>
    </article>"
}"""
    created = client.post(
        "/admin/v1/articles",
        headers={**ADMIN_HEADERS, "Content-Type": "application/json"},
        content=body.encode(),
    )
    assert created.status_code == 201
    text = created.json()["translations"][0]["text"]
    assert 'src="https://images.unsplash.com/photo.jpg"' in text
    assert 'alt="Drewniany młotek"' in text
    assert "Sotheby's" in text


def test_admin_detects_language_when_omitted(client: TestClient, monkeypatch):
    seen: list[str] = []

    async def fake_detect(text: str) -> str:
        seen.append(text)
        return "pl"

    monkeypatch.setattr("services.articles.detect_language", fake_detect)
    created = client.post(
        "/admin/v1/articles",
        headers=ADMIN_HEADERS,
        json={
            "title": "Pod Młotek",
            "slug": "pod-mlotek",
            "text": "<article><p>Aukcja</p></article>",
        },
    )
    assert created.status_code == 201
    article = created.json()
    assert article["source_language"] == "pl"
    assert article["translations"][0]["language"] == "pl"
    assert article["target_languages_count"] == 5
    assert seen == ["Pod Młotek\nAukcja"]


def test_admin_generates_slug_from_title(client: TestClient):
    created = client.post(
        "/admin/v1/articles",
        headers=ADMIN_HEADERS,
        json={
            "language": "pl",
            "title": "Pod Młotek",
            "text": "<p>Aukcja</p>",
        },
    )
    assert created.status_code == 201
    assert created.json()["translations"][0]["slug"] == "pod-mlotek"

    again = client.post(
        "/admin/v1/articles",
        headers=ADMIN_HEADERS,
        json={
            "language": "pl",
            "title": "Pod Młotek",
            "text": "<p>Jeszcze raz</p>",
        },
    )
    assert again.status_code == 201
    assert again.json()["translations"][0]["slug"] == f"pod-mlotek-{again.json()['id']}"


def test_admin_rejects_broken_json(client: TestClient):
    created = client.post(
        "/admin/v1/articles",
        headers={**ADMIN_HEADERS, "Content-Type": "application/json"},
        content='{"language":',
    )
    assert created.status_code == 422


def test_admin_creates_changes_publishes_and_hides_html(client: TestClient, test_db):
    created = client.post(
        "/admin/v1/articles",
        headers=ADMIN_HEADERS,
        json={
            "language": "EN",
            "title": "Hello",
            "slug": "hello",
            "text": HTML,
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
            "text": HTML,
            "origin": "source",
        }
    ]
    listed = client.get("/admin/v1/articles", headers=ADMIN_HEADERS)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    fetched = client.get(f"/admin/v1/articles/{article['id']}", headers=ADMIN_HEADERS)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == article["id"]

    with Session(test_db.engine) as session:
        session.add(
            ArticleTranslation(
                article_id=article["id"],
                language="de",
                title="Hallo",
                slug="hallo",
                text="<h2>Hallo</h2>",
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
            "text": HTML + "\n\nUpdated.",
        },
    )
    assert changed.status_code == 200
    by_language = {item["language"]: item for item in changed.json()["translations"]}
    assert by_language["en"]["title"] == "Hello again"
    assert by_language["en"]["text"] == HTML + "\n\nUpdated."
    assert by_language["de"]["title"] == "Hallo"
    assert by_language["de"]["text"] == "<h2>Hallo</h2>"

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
            "text": HTML,
        },
    )
    article_id = created.json()["id"]

    denied = client.post(
        f"/admin/v1/articles/{article_id}/publish",
        headers=headers,
    )
    assert denied.status_code == 403
