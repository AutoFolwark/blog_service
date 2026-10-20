import asyncio
import re

from config import settings
from services.translation.translator import TranslationError, translate

FENCE_START = re.compile(r"^(```+|~~~+)")
IMAGE_LINE = re.compile(r"^!\[[^\]]*\]\([^)\s]+(?:\s+\"[^\"]*\")?\)\s*$")
HTML_START = re.compile(r"^</?[A-Za-z]")
INLINE_CODE = re.compile(r"`[^`\n]+`")
LINK = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)(\))")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _segments(text: str) -> list[tuple[str, str]]:
    lines = text.split("\n")
    segments: list[tuple[str, str]] = []
    prose: list[str] = []

    def flush_prose() -> None:
        if prose:
            segments.append(("prose", "\n".join(prose)))
            prose.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        fence = FENCE_START.match(stripped)
        if fence:
            flush_prose()
            marker = fence.group(1)[0]
            block = [line]
            index += 1
            while index < len(lines) and not lines[index].lstrip().startswith(marker * 3):
                block.append(lines[index])
                index += 1
            if index < len(lines):
                block.append(lines[index])
                index += 1
            segments.append(("skip", "\n".join(block)))
            continue
        if IMAGE_LINE.match(stripped):
            flush_prose()
            segments.append(("skip", line))
            index += 1
            continue
        if (
            stripped.startswith("<")
            and not stripped.lower().startswith("<http")
            and HTML_START.match(stripped)
        ):
            flush_prose()
            block = [line]
            index += 1
            while index < len(lines) and lines[index].strip():
                block.append(lines[index])
                index += 1
            segments.append(("skip", "\n".join(block)))
            continue
        if stripped == "":
            flush_prose()
            segments.append(("blank", ""))
            index += 1
            continue
        prose.append(line)
        index += 1
    flush_prose()
    return segments


def _protect(text: str) -> tuple[str, list[str]]:
    values: list[str] = []

    def take(value: str) -> str:
        values.append(value)
        return f"XTOKEN{len(values) - 1}X"

    protected = INLINE_CODE.sub(lambda match: take(match.group(0)), text)

    def replace_link(match: re.Match[str]) -> str:
        return f"{match.group(1)}{take(match.group(2))}{match.group(3)}"

    return LINK.sub(replace_link, protected), values


def _restore(text: str, values: list[str]) -> str:
    for index, value in enumerate(values):
        token = f"XTOKEN{index}X"
        if token not in text:
            raise TranslationError(f"Translation dropped placeholder {token}")
        text = text.replace(token, value)
    return text


def split_chunks(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for sentence in SENTENCE.split(text):
        while len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:limit])
            sentence = sentence[limit:]
        if not sentence:
            continue
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= limit:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


async def _translate_prose(text: str, src: str, dest: str) -> str:
    protected, values = _protect(text)
    parts = []
    for chunk in split_chunks(protected, settings.TRANSLATION_CHUNK_CHARS):
        if settings.TRANSLATION_REQUEST_DELAY_SECONDS > 0:
            await asyncio.sleep(settings.TRANSLATION_REQUEST_DELAY_SECONDS)
        parts.append(await translate(chunk, src, dest))
    return _restore(" ".join(parts) if len(parts) > 1 else parts[0], values)


async def translate_markdown(text: str, src: str, dest: str) -> str:
    if not text or src == dest:
        return text
    rendered: list[str] = []
    for kind, segment in _segments(text):
        if kind == "blank":
            rendered.append("")
        elif kind == "skip":
            rendered.append(segment)
        else:
            rendered.append(await _translate_prose(segment, src, dest))
    return "\n".join(rendered)
