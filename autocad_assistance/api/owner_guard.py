"""Authenticate owner resource routes before FastAPI parses a request body."""

from urllib.parse import urlsplit

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from autocad_assistance.api.auth import COOKIE_NAME
from autocad_assistance.services.auth_store import AuthError, AuthStore


class OwnerGuardMiddleware:
    def __init__(self, app: ASGIApp, *, store: AuthStore, trusted_origin: str) -> None:
        self.app = app
        self.store = store
        self.trusted_origin = trusted_origin
        self.trusted_host = urlsplit(trusted_origin).netloc

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/v1/") or path.startswith("/api/v1/auth/"):
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        if request.url.scheme != "https" or request.url.netloc != self.trusted_host:
            response = self._error(403, "HTTPS_REQUIRED")
        else:
            try:
                grant = await run_in_threadpool(self.store.authenticate, request.cookies.get(COOKIE_NAME))
            except AuthError:
                response = self._error(401, "AUTH_REQUIRED")
            else:
                response = None
                if request.method not in {"GET", "HEAD", "OPTIONS"}:
                    try:
                        if request.headers.get("origin") != self.trusted_origin:
                            raise AuthError("Origin mismatch")
                        self.store.check_csrf(grant, request.headers.get("x-csrf-token"))
                    except AuthError:
                        response = self._error(403, "SESSION_OR_CSRF_INVALID")
                if response is None:
                    scope["geoai.owner_id"] = grant.user.user_id
        if response is not None:
            await response(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    @staticmethod
    def _error(status: int, code: str) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": "Access denied"}},
            headers={"Cache-Control": "no-store"},
        )
