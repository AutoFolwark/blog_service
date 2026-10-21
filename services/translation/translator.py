from googletrans import LANGUAGES, Translator

from config import settings


class TranslationError(Exception):
    pass


async def detect_language(text: str) -> str:
    sample = text.strip()[: settings.TRANSLATION_CHUNK_CHARS]
    if not sample:
        raise TranslationError("Article text is empty")
    try:
        async with Translator(raise_exception=True) as translator:
            detected = await translator.detect(sample)
    except TranslationError:
        raise
    except Exception as exc:
        raise TranslationError(str(exc)) from exc
    lang = getattr(detected, "lang", "")
    if isinstance(lang, list):
        lang = lang[0] if lang else ""
    code = str(lang or "").strip().lower().replace("_", "-")
    if code not in LANGUAGES and code.split("-")[0] in LANGUAGES:
        code = code.split("-")[0]
    if code not in LANGUAGES:
        raise TranslationError("Could not detect the article language")
    return code


async def translate(text: str, src: str, dest: str) -> str:
    if src == dest:
        return text
    try:
        async with Translator(raise_exception=True) as translator:
            result = await translator.translate(text, src=src, dest=dest)
    except TranslationError:
        raise
    except Exception as exc:
        raise TranslationError(str(exc)) from exc
    translated = getattr(result, "text", None)
    if not translated or not str(translated).strip():
        raise TranslationError("Translator returned an empty result")
    return str(translated)
