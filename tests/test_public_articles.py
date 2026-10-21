from fastapi.testclient import TestClient

from tests.test_admin_articles import ADMIN_HEADERS, HTML


def _publish(client: TestClient, **overrides) -> dict:
    payload = {
        "language": "en",
        "title": "Hello",
        "slug": "hello",
        "text": HTML,
    }
    payload.update(overrides)
    created = client.post("/admin/v1/articles", headers=ADMIN_HEADERS, json=payload)
    assert created.status_code == 201
    article_id = created.json()["id"]
    published = client.post(
        f"/admin/v1/articles/{article_id}/publish",
        headers=ADMIN_HEADERS,
    )
    assert published.status_code == 200
    return published.json()


def test_public_list_and_item_need_no_permissions(client: TestClient):
    article = _publish(client)
    updated = client.put(
        f"/admin/v1/articles/{article['id']}",
        headers=ADMIN_HEADERS,
        json={
            "language": "de",
            "title": "Hallo",
            "slug": "hallo",
            "text": "<p>Hallo</p>",
        },
    )
    assert updated.status_code == 200

    listed = client.get("/public/v1/articles", params={"language": "en"})
    assert listed.status_code == 200
    page = listed.json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == article["id"]
    assert page["items"][0]["language"] == "en"
    assert page["items"][0]["title"] == "Hello"
    assert page["items"][0]["slug"] == "hello"
    assert page["items"][0]["description"] == "Hello This is html."
    assert page["items"][0]["published_at"]
    assert "translations_status" not in page["items"][0]

    german = client.get("/public/v1/articles", params={"language": "DE"})
    assert german.status_code == 200
    assert german.json()["items"][0]["slug"] == "hallo"
    assert german.json()["items"][0]["description"] == "Hallo"

    fetched = client.get("/public/v1/articles/en/hello")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["text"] == HTML
    assert {item["language"] for item in body["translations"]} == {"en", "de"}
    assert "origin" not in body


def test_public_list_description_is_about_300_characters(client: TestClient):
    words = " ".join(f"word{index}" for index in range(120))
    _publish(client, title="Long", slug="long", text=f'<p>{words}</p><img src="x">')

    listed = client.get("/public/v1/articles", params={"language": "en", "size": 20})
    assert listed.status_code == 200
    description = listed.json()["items"][0]["description"]
    assert description.startswith("word0 ")
    assert "<" not in description
    assert len(description) <= 300
    assert len(description) >= 280


def test_public_routes_hide_drafts(client: TestClient):
    created = client.post(
        "/admin/v1/articles",
        headers=ADMIN_HEADERS,
        json={
            "language": "en",
            "title": "Draft",
            "slug": "draft",
            "text": HTML,
        },
    )
    assert created.status_code == 201

    listed = client.get("/public/v1/articles")
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    missing = client.get("/public/v1/articles/en/draft")
    assert missing.status_code == 404

    _publish(client, title="Live", slug="live")
    hidden_id = client.get("/public/v1/articles/en/live").json()["id"]
    hidden = client.post(
        f"/admin/v1/articles/{hidden_id}/hide",
        headers=ADMIN_HEADERS,
    )
    assert hidden.status_code == 200
    assert client.get("/public/v1/articles/en/live").status_code == 404
    assert client.get("/public/v1/articles").json()["total"] == 0
