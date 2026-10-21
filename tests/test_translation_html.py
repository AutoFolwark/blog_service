import asyncio

import pytest

from services.translation.html import translate_html, visible_article_text
from services.translation.translator import TranslationError, detect_language


def _patch(monkeypatch, translate):
    monkeypatch.setattr("services.translation.html.translate", translate)


def test_markup_stays_and_text_is_translated(monkeypatch):
    calls = []

    async def fake(text, src, dest):
        calls.append(text)
        return f"[{dest}] {text}"

    _patch(monkeypatch, fake)
    result = asyncio.run(
        translate_html(
            '<h1>Hello</h1>\n<p>See <a href="https://example.com/a">docs</a>.</p>',
            "en",
            "de",
        )
    )
    assert "<h1>" in result and "</h1>" in result
    assert 'href="https://example.com/a"' in result
    assert "[de] Hello" in result
    assert "[de] See" in result
    assert "[de] docs" in result
    assert "https://example.com/a" not in "".join(calls)


def test_code_script_and_pre_stay_unchanged(monkeypatch):
    calls = []

    async def fake(text, src, dest):
        calls.append(text)
        return f"[{dest}] {text}"

    _patch(monkeypatch, fake)
    result = asyncio.run(
        translate_html(
            "<p>Hello</p><pre><code>code()</code></pre>"
            "<p>Use <code>npm install</code> please.</p>"
            "<script>alert(1)</script>",
            "en",
            "de",
        )
    )
    sent = "".join(calls)
    assert "code()" not in sent
    assert "npm install" not in sent
    assert "alert(1)" not in sent
    assert "<pre><code>code()</code></pre>" in result
    assert "<code>npm install</code>" in result
    assert "<script>alert(1)</script>" in result
    assert "[de] Hello" in result
    assert "[de] Use" in result
    assert "[de] please." in result


def test_alt_text_is_translated_and_src_stays(monkeypatch):
    async def fake(text, src, dest):
        return f"[{dest}] {text}"

    _patch(monkeypatch, fake)
    result = asyncio.run(
        translate_html(
            '<img alt="A red car" src="https://cdn.example/a.jpg">', "en", "de"
        )
    )
    assert 'alt="[de] A red car"' in result
    assert 'src="https://cdn.example/a.jpg"' in result


def test_entities_stay_escaped(monkeypatch):
    async def fake(text, src, dest):
        return f"[{dest}] {text}"

    _patch(monkeypatch, fake)
    result = asyncio.run(translate_html("<p>Tom &amp; Jerry</p>", "en", "de"))
    assert result == "<p>[de] Tom &amp; Jerry</p>"


def test_paragraph_text_is_extracted_whole(monkeypatch):
    calls = []

    async def fake(text, src, dest):
        calls.append(text)
        return text

    _patch(monkeypatch, fake)
    paragraph = "Sentence one is here. Sentence two is here. Sentence three is here."
    asyncio.run(translate_html(f"<p>{paragraph}</p>", "en", "de"))
    assert calls == [paragraph]


def test_visible_article_text_drops_markup():
    sample = visible_article_text(
        "Pod Młotek",
        '<article><img src="https://example.com/a.jpg" alt="młotek"><p>Aukcja</p></article>',
    )
    assert sample == "Pod Młotek\nAukcja"


def test_detect_language_reads_googletrans_result(monkeypatch):
    class _Detected:
        lang = "pl"

    class _Translator:
        def __init__(self, raise_exception=True):
            self.raise_exception = raise_exception

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def detect(self, text):
            assert "Aukcja" in text
            return _Detected()

    monkeypatch.setattr("services.translation.translator.Translator", _Translator)
    assert asyncio.run(detect_language("Aukcja w Warszawie")) == "pl"


def test_detect_language_rejects_an_unknown_code(monkeypatch):
    class _Detected:
        lang = ""

    class _Translator:
        def __init__(self, raise_exception=True):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def detect(self, text):
            return _Detected()

    monkeypatch.setattr("services.translation.translator.Translator", _Translator)
    with pytest.raises(TranslationError, match="Could not detect"):
        asyncio.run(detect_language("???"))
