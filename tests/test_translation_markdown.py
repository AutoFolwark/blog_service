import asyncio

import pytest

from config import settings
from services.translation.markdown import translate_markdown
from services.translation.translator import TranslationError


def _patch(monkeypatch, translate):
    monkeypatch.setattr("services.translation.markdown.translate", translate)


def test_code_fence_and_inline_code_stay_unchanged(monkeypatch):
    calls = []

    async def fake(text, src, dest):
        calls.append(text)
        return f"[{dest}] {text}"

    _patch(monkeypatch, fake)
    result = asyncio.run(
        translate_markdown(
            "Hello\n\n```\ncode()\n```\n\nUse `npm install` please.", "en", "de"
        )
    )
    assert "code()" not in "".join(calls)
    assert "npm install" not in "".join(calls)
    assert "```" in result
    assert "code()" in result
    assert "`npm install`" in result


def test_link_url_survives_translation(monkeypatch):
    async def fake(text, src, dest):
        return f"[{dest}] {text}"

    _patch(monkeypatch, fake)
    result = asyncio.run(
        translate_markdown("See [docs](https://example.com/a).", "en", "de")
    )
    assert "https://example.com/a" in result


def test_long_blocks_are_split(monkeypatch):
    calls = []

    async def fake(text, src, dest):
        calls.append(text)
        return text

    _patch(monkeypatch, fake)
    previous = settings.TRANSLATION_CHUNK_CHARS
    settings.TRANSLATION_CHUNK_CHARS = 40
    try:
        text = "Sentence one is here. Sentence two is here. Sentence three is here."
        asyncio.run(translate_markdown(text, "en", "de"))
    finally:
        settings.TRANSLATION_CHUNK_CHARS = previous
    assert len(calls) > 1
    assert all(len(call) <= 40 for call in calls)


def test_missing_placeholder_raises(monkeypatch):
    async def fake(text, src, dest):
        return "plain text"

    _patch(monkeypatch, fake)
    with pytest.raises(TranslationError):
        asyncio.run(translate_markdown("Use `npm install` please.", "en", "de"))
