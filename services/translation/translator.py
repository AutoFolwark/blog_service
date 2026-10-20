from googletrans import Translator


class TranslationError(Exception):
    pass


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
