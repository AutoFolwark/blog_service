import json
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute


class LenientJSONRoute(APIRoute):
    """Parse JSON bodies with control characters allowed inside strings.

    Article Markdown is often pasted with raw newlines. Standard JSON rejects
    those characters; ``strict=False`` accepts them and still rejects broken JSON.
    """

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            async def load_json():
                if not hasattr(request, "_json"):
                    body = await request.body()
                    request._json = json.loads(body, strict=False)
                return request._json

            request.json = load_json
            return await original(request)

        return handler
