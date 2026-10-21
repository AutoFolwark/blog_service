import json
from typing import Any


def loads_lenient_json(body: bytes | str) -> Any:
    """Parse article JSON that contains pasted HTML.

    ``strict=False`` allows raw newlines inside strings. If the HTML also
    contains raw quotes, as in ``<img src="...">``, parse the object again
    and keep a quote that does not end the JSON string.
    """
    try:
        return json.loads(body, strict=False)
    except json.JSONDecodeError as first_error:
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        try:
            return _LenientJSON(text).parse()
        except (json.JSONDecodeError, UnicodeError):
            raise first_error from None


class _LenientJSON:
    def __init__(self, source: str) -> None:
        self.source = source
        self.length = len(source)
        self.index = 0

    def parse(self) -> Any:
        value = self._value()
        self._skip()
        if self.index != self.length:
            raise json.JSONDecodeError("Extra data", self.source, self.index)
        return value

    def _value(self) -> Any:
        self._skip()
        if self.index < self.length and self.source[self.index] == "{":
            return self._object()
        if self.index < self.length and self.source[self.index] == '"':
            return self._string()
        raise json.JSONDecodeError("Expecting value", self.source, self.index)

    def _object(self) -> dict[str, Any]:
        self.index += 1
        result: dict[str, Any] = {}
        self._skip()
        if self.index < self.length and self.source[self.index] == "}":
            self.index += 1
            return result
        while True:
            self._skip()
            if self.index >= self.length or self.source[self.index] != '"':
                raise json.JSONDecodeError(
                    "Expecting property name", self.source, self.index
                )
            key = self._string()
            self._skip()
            if self.index >= self.length or self.source[self.index] != ":":
                raise json.JSONDecodeError(
                    "Expecting ':' delimiter", self.source, self.index
                )
            self.index += 1
            result[key] = self._value()
            self._skip()
            if self.index >= self.length:
                raise json.JSONDecodeError(
                    "Expecting ',' delimiter", self.source, self.index
                )
            char = self.source[self.index]
            if char == ",":
                self.index += 1
                continue
            if char == "}":
                self.index += 1
                return result
            raise json.JSONDecodeError(
                "Expecting ',' delimiter", self.source, self.index
            )

    def _string(self) -> str:
        self.index += 1
        characters: list[str] = []
        while self.index < self.length:
            char = self.source[self.index]
            if char == '"':
                if self._quote_ends_string():
                    self.index += 1
                    return "".join(characters)
                characters.append('"')
                self.index += 1
                continue
            if char == "\\":
                characters.append(self._escape())
                continue
            characters.append(char)
            self.index += 1
        raise json.JSONDecodeError("Unterminated string", self.source, self.index)

    def _quote_ends_string(self) -> bool:
        cursor = self.index + 1
        while cursor < self.length and self.source[cursor] in " \t\r\n":
            cursor += 1
        if cursor >= self.length:
            return True
        return self.source[cursor] in ",}]:"

    def _escape(self) -> str:
        self.index += 1
        if self.index >= self.length:
            raise json.JSONDecodeError("Unterminated string", self.source, self.index)
        escaped = self.source[self.index]
        self.index += 1
        return {
            "n": "\n",
            "r": "\r",
            "t": "\t",
            '"': '"',
            "\\": "\\",
            "/": "/",
        }.get(escaped, escaped)

    def _skip(self) -> None:
        while self.index < self.length and self.source[self.index] in " \t\r\n":
            self.index += 1
