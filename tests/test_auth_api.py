"""Opt-in HTTPS owner session adapter checks."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import httpx

from autocad_assistance.api import create_app
from autocad_assistance.api.auth import COOKIE_NAME
from autocad_assistance.services.auth_store import AuthStore


PASSWORD = "Synthetic-only-owner-passphrase-123"


class AuthApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "identity"
        self.upload_root = Path(self.temp.name) / "uploads"
        AuthStore(self.root).create_owner("owner", PASSWORD)
        self.app = create_app(
            upload_root=self.upload_root, auth_root=self.root, auth_origin="https://testserver"
        )

    async def test_login_session_csrf_challenge_and_logout(self):
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            wrong_origin = await client.post(
                "/api/v1/auth/login", json={"username": "owner", "password": PASSWORD},
                headers={"Origin": "https://other.example"},
            )
            self.assertEqual(wrong_origin.status_code, 403)
            forged_host = await client.post(
                "/api/v1/auth/login", json={"username": "owner", "password": PASSWORD},
                headers={"Host": "other.example", "Origin": "https://other.example"},
            )
            self.assertEqual(forged_host.status_code, 403)
            login = await client.post(
                "/api/v1/auth/login", json={"username": "owner", "password": PASSWORD},
                headers={"Origin": "https://testserver"},
            )
            self.assertEqual(login.status_code, 200, login.text)
            cookie = login.headers["set-cookie"]
            for attribute in (COOKIE_NAME, "Secure", "HttpOnly", "SameSite=strict", "Path=/"):
                self.assertIn(attribute.lower(), cookie.lower())
            self.assertEqual(login.headers["cache-control"], "no-store")
            self.assertNotIn(client.cookies.get(COOKIE_NAME), login.text)
            session = await client.get("/api/v1/auth/session")
            self.assertEqual(session.status_code, 200)
            csrf = session.json()["csrfToken"]
            invalid_csrf = await client.post(
                "/api/v1/auth/telegram-link-challenge",
                headers={"Origin": "https://testserver", "X-CSRF-Token": "wrong"},
            )
            self.assertEqual(invalid_csrf.status_code, 403)
            self.assertEqual((await client.get("/api/v1/auth/session")).status_code, 200)
            challenge = await client.post(
                "/api/v1/auth/telegram-link-challenge",
                headers={"Origin": "https://testserver", "X-CSRF-Token": csrf},
            )
            self.assertEqual(challenge.status_code, 200)
            self.assertGreaterEqual(len(challenge.json()["code"]), 16)
            no_origin = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
            self.assertEqual(no_origin.status_code, 403)
            logout = await client.post(
                "/api/v1/auth/logout",
                headers={"Origin": "https://testserver", "X-CSRF-Token": csrf},
            )
            self.assertEqual(logout.status_code, 200)
            self.assertEqual((await client.get("/api/v1/auth/session")).status_code, 401)

    async def test_revoke_all_http_rejection_and_body_limit(self):
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            login = await client.post(
                "/api/v1/auth/login", json={"username": "owner", "password": PASSWORD},
                headers={"Origin": "https://testserver"},
            )
            self.assertEqual(login.status_code, 200)
            csrf = login.json()["csrfToken"]
            too_large = await client.post(
                "/api/v1/auth/login", content=b"x" * 4097,
                headers={"Origin": "https://testserver"},
            )
            self.assertEqual(too_large.status_code, 413)
            self.assertEqual(too_large.json()["error"]["code"], "AUTH_BODY_TOO_LARGE")
            revoke = await client.post(
                "/api/v1/auth/revoke-all",
                headers={"Origin": "https://testserver", "X-CSRF-Token": csrf},
            )
            self.assertEqual(revoke.status_code, 200)
            self.assertEqual((await client.get("/api/v1/auth/session")).status_code, 401)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            insecure = await client.post(
                "/api/v1/auth/login", json={"username": "owner", "password": PASSWORD},
                headers={"Origin": "http://testserver"},
            )
            self.assertEqual(insecure.status_code, 403)

    async def test_routes_are_absent_when_auth_is_not_configured(self):
        with self.assertRaises(ValueError):
            create_app(upload_root=self.upload_root, auth_root=self.root)
        with self.assertRaises(ValueError):
            create_app(upload_root=self.upload_root, auth_root=self.root, auth_origin="http://testserver")
        app = create_app(upload_root=self.upload_root)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            self.assertEqual((await client.get("/api/v1/auth/session")).status_code, 404)
            self.assertEqual((await client.get("/health")).status_code, 200)


if __name__ == "__main__":
    unittest.main()
