from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute

from core.json_body import loads_lenient_json


class LenientJSONRoute(APIRoute):
    """Parse admin JSON that contains pasted article HTML.

    The body may include raw newlines and raw quotes inside ``text``,
    such as ``<img src="...">``. Other broken JSON is still rejected.
    """

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            async def load_json():
                if not hasattr(request, "_json"):
                    body = await request.body()
                    request._json = loads_lenient_json(body)
                return request._json

            request.json = load_json
            return await original(request)

        return handler
