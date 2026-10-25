"""HTTPS cookie adapter for the opt-in owner identity store."""

from __future__ import annotations

from urllib.parse import urlsplit
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from autocad_assistance.services.auth_store import AuthBusyError, AuthError, AuthStore, SessionGrant


COOKIE_NAME = "__Host-geoai_session"


class LoginPayload(BaseModel):
    username: str
    password: str


def _response(status: int, body: dict) -> JSONResponse:
    return JSONResponse(status_code=status, content=body, headers={"Cache-Control": "no-store"})


def _error(status: int, code: str, message: str) -> JSONResponse:
    return _response(status, {"error": {"code": code, "message": message}})


def _secure_origin(request: Request, trusted_origin: str) -> bool:
    return (
        request.url.scheme == "https"
        and request.url.netloc == urlsplit(trusted_origin).netloc
        and request.headers.get("origin") == trusted_origin
    )


def _secure_request(request: Request, trusted_origin: str) -> bool:
    return request.url.scheme == "https" and request.url.netloc == urlsplit(trusted_origin).netloc


def _session_body(grant: SessionGrant) -> dict:
    return {
        "userId": grant.user.user_id,
        "username": grant.user.username,
        "telegramLinked": grant.user.telegram_user_id is not None,
        "absoluteExpiresAt": grant.absolute_expires_at,
        "csrfToken": grant.csrf_token,
    }


def _set_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token, path="/", secure=True, httponly=True, samesite="strict"
    )


def _clear_cookie(response: JSONResponse) -> None:
    response.set_cookie(
        COOKIE_NAME, "", path="/", secure=True, httponly=True,
        samesite="strict", max_age=0, expires=0,
    )


def validate_auth_origin(trusted_origin: str) -> str:
    if not isinstance(trusted_origin, str):
        raise ValueError("auth_origin must be one exact HTTPS origin")
    parsed = urlsplit(trusted_origin)
    if (
        parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/")
        or parsed.query or parsed.fragment or parsed.username or parsed.password
        or trusted_origin.endswith("/")
    ):
        raise ValueError("auth_origin must be one exact HTTPS origin")
    return trusted_origin


def create_auth_router(store: AuthStore, trusted_origin: str) -> APIRouter:
    trusted_origin = validate_auth_origin(trusted_origin)
    router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

    @router.post("/login")
    async def login(request: Request, payload: LoginPayload):
        if not _secure_origin(request, trusted_origin):
            return _error(403, "ORIGIN_REQUIRED", "HTTPS same-origin request required")
        try:
            grant = await run_in_threadpool(
                store.login, payload.username, payload.password,
                previous_token=request.cookies.get(COOKIE_NAME),
            )
        except AuthBusyError:
            return _error(429, "AUTH_BUSY", "Authentication is busy; retry shortly")
        except AuthError:
            return _error(401, "INVALID_CREDENTIALS", "Invalid credentials")
        response = _response(200, _session_body(grant))
        _set_cookie(response, grant.token)
        return response

    @router.get("/session")
    async def session(request: Request):
        if not _secure_request(request, trusted_origin):
            return _error(403, "HTTPS_REQUIRED", "HTTPS is required")
        try:
            grant = await run_in_threadpool(store.authenticate, request.cookies.get(COOKIE_NAME))
        except AuthError:
            return _error(401, "AUTH_REQUIRED", "Authentication required")
        return _response(200, _session_body(grant))

    async def require_mutation(request: Request) -> SessionGrant | JSONResponse:
        if not _secure_origin(request, trusted_origin):
            return _error(403, "ORIGIN_REQUIRED", "HTTPS same-origin request required")
        try:
            grant = await run_in_threadpool(store.authenticate, request.cookies.get(COOKIE_NAME), touch=False)
            store.check_csrf(grant, request.headers.get("x-csrf-token"))
        except AuthError:
            return _error(403, "SESSION_OR_CSRF_INVALID", "Session or CSRF token is invalid")
        return grant

    @router.post("/logout")
    async def logout(request: Request):
        authorized = await require_mutation(request)
        if isinstance(authorized, JSONResponse):
            return authorized
        await run_in_threadpool(store.logout, authorized.token)
        response = _response(200, {"status": "logged_out"})
        _clear_cookie(response)
        return response

    @router.post("/revoke-all")
    async def revoke_all(request: Request):
        authorized = await require_mutation(request)
        if isinstance(authorized, JSONResponse):
            return authorized
        count = await run_in_threadpool(store.revoke_all, authorized.user.user_id)
        response = _response(200, {"status": "revoked", "sessionCount": count})
        _clear_cookie(response)
        return response

    @router.post("/telegram-link-challenge")
    async def link_challenge(request: Request):
        authorized = await require_mutation(request)
        if isinstance(authorized, JSONResponse):
            return authorized
        code = await run_in_threadpool(store.create_link_challenge, authorized.user.user_id)
        return _response(200, {"code": code, "expiresInSeconds": 600})

    return router
