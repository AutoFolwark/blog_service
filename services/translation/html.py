import asyncio
import re

from bs4 import BeautifulSoup, NavigableString

from config import settings
from services.translation.translator import translate

SKIP_TAGS = ["script", "style", "pre", "code", "textarea", "svg", "math"]
TEXT_ATTRIBUTES = ("alt", "title")


def _skipped(node) -> bool:
    name = getattr(node, "name", None)
    if name in SKIP_TAGS:
        return True
    return node.find_parent(SKIP_TAGS) is not None


async def _translate_text(text: str, src: str, dest: str) -> str:
    visible = text.strip()
    if not visible:
        return text
    if settings.TRANSLATION_REQUEST_DELAY_SECONDS > 0:
        await asyncio.sleep(settings.TRANSLATION_REQUEST_DELAY_SECONDS)
    translated = await translate(visible, src, dest)
    return text.replace(visible, translated, 1)


DESCRIPTION_LENGTH = 300


def article_description(html: str, limit: int = DESCRIPTION_LENGTH) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all(SKIP_TAGS):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ", strip=True).split())
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    if len(text) <= limit:
        return text
    shortened = text[:limit]
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0]
    return shortened.rstrip()


def visible_article_text(title: str, html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all(SKIP_TAGS):
        tag.decompose()
    body = soup.get_text(separator=" ", strip=True)
    return f"{title.strip()}\n{body}".strip()


async def translate_html(text: str, src: str, dest: str) -> str:
    if not text or src == dest:
        return text
    soup = BeautifulSoup(text, "html.parser")
    strings = [
        node
        for node in soup.find_all(string=True)
        if type(node) is NavigableString and node.strip() and not _skipped(node)
    ]
    for node in strings:
        node.replace_with(await _translate_text(str(node), src, dest))
    for tag in soup.select("[alt], [title]"):
        if _skipped(tag):
            continue
        for attr in TEXT_ATTRIBUTES:
            value = tag.get(attr)
            if isinstance(value, str):
                tag[attr] = await _translate_text(value, src, dest)
    return str(soup)
