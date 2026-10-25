"""Small ASGI guards used by the HTTP adapter."""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi.responses import JSONResponse


ASGIApp = Callable[[dict[str, Any], Callable[..., Awaitable[dict]], Callable[..., Awaitable[None]]], Awaitable[None]]


class _RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    """Reject an oversized upload request before multipart parsing completes."""

    def __init__(self, app: ASGIApp, *, path: str, max_body_bytes: int,
                 error_code: str = "UPLOAD_TOO_LARGE", subject: str = "Upload request") -> None:
        self.app = app
        self.path = path
        self.max_body_bytes = max_body_bytes
        self.error_code = error_code
        self.subject = subject

    def _response(self) -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": self.error_code,
                    "message": (
                        f"{self.subject} exceeds the {self.max_body_bytes}-byte limit"
                    ),
                }
            },
        )

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("path") != self.path:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", ()))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_body_bytes:
                    await self._response()(scope, receive, send)
                    return
            except ValueError:
                pass

        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await self._response()(scope, receive, send)
