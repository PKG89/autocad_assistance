"""Synthetic contract checks for the bounded, provenance-labelled 029A parser."""

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.field_code_profile import (
    PROFILE_PATH, PROFILE_SHA256, PROFILE_VERSION, FieldCodeError,
    load_profile, parse_code,
)


ORIGIN = "https://testserver"
PASSWORD = "Synthetic-only-owner-passphrase-123"


class FieldCodeProfileTests(unittest.TestCase):
    def test_snapshot_is_versioned_and_source_bound(self):
        profile = load_profile()
        self.assertEqual(sha256(PROFILE_PATH.read_bytes()).hexdigest(), PROFILE_SHA256)
        self.assertEqual(profile["profileVersion"], PROFILE_VERSION)
        self.assertEqual(profile["catalogVersion"], "object-code-v1")
        self.assertEqual(len(profile["pointCodes"]), 11)
        self.assertTrue(all(len(value) == 64 for value in profile["sourceEvidence"].values()))
        with tempfile.TemporaryDirectory() as root:
            modified = Path(root) / "profile.json"
            modified.write_bytes(PROFILE_PATH.read_bytes() + b" ")
            with patch("autocad_assistance.services.field_code_profile.PROFILE_PATH", modified):
                with self.assertRaises(FieldCodeError):
                    load_profile()

    def test_raw_code_spans_unknown_and_ambiguous_roles(self):
        profile = load_profile()
        raw = " KIK\tKM 1 0 11 kik & && "
        result = parse_code(profile, raw)
        self.assertEqual(result["rawCode"], raw)
        self.assertEqual([item["raw"] for item in result["tokens"]],
                         ["KIK", "KM", "1", "0", "11", "kik", "&", "&&"])
        self.assertEqual([raw[item["start"]:item["end"]] for item in result["tokens"]],
                         [item["raw"] for item in result["tokens"]])
        self.assertEqual([len(item["candidates"]) for item in result["tokens"]],
                         [1, 1, 2, 2, 1, 0, 0, 0])
        self.assertEqual([item["code"] for item in result["diagnostics"]],
                         ["AMBIGUOUS_TOKEN", "AMBIGUOUS_TOKEN",
                          "UNKNOWN_TOKEN", "UNKNOWN_TOKEN", "UNKNOWN_TOKEN"])
        self.assertEqual(parse_code(profile, "DER_L DER_X")["diagnostics"], [])

    def test_empty_invalid_controls_and_bounds(self):
        profile = load_profile()
        self.assertEqual(parse_code(profile, " \t ")["diagnostics"][0]["code"], "EMPTY_CODE")
        self.assertEqual(parse_code(profile, "")["rawCode"], "")
        for raw in ("KIK\nKM", "KIK\rKM", "KIK\x00KM", "KIK\x7fKM",
                    "KIK\x85KM", "KIK\u200bKM", "a" * 129,
                    " ".join("a" for _ in range(33))):
            with self.subTest(raw=raw[:20]), self.assertRaises(FieldCodeError):
                parse_code(profile, raw)
        self.assertEqual(len(parse_code(profile, " ".join("a" for _ in range(32)))["tokens"]), 32)


class FieldCodeProfileApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        AuthStore(root / "auth").create_owner("owner", PASSWORD)
        self.app = create_app(auth_root=root / "auth", project_root=root / "projects",
                              upload_root=root / "uploads", auth_origin=ORIGIN)

    async def test_profile_parse_auth_csrf_body_and_catalog_parity(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            url = "/api/v1/object-catalog/parse"
            payload = {"profileVersion": PROFILE_VERSION, "rawCode": "KIK 1 odd"}
            self.assertEqual((await client.get("/api/v1/object-catalog/profiles/drawcode-explicit-v1")).status_code, 401)
            self.assertEqual((await client.post(url, json=payload)).status_code, 401)
            login = await client.post("/api/v1/auth/login", json={
                "username": "owner", "password": PASSWORD,
            }, headers={"Origin": ORIGIN})
            self.assertEqual(login.status_code, 200, login.text)
            headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrfToken"]}
            self.assertEqual((await client.post(url, json=payload)).status_code, 403)
            profile = await client.get("/api/v1/object-catalog/profiles/drawcode-explicit-v1")
            self.assertEqual(profile.status_code, 200)
            self.assertEqual(profile.json()["profileSha256"], PROFILE_SHA256)
            parsed = await client.post(url, json=payload, headers=headers)
            self.assertEqual(parsed.status_code, 200, parsed.text)
            self.assertEqual(parsed.json()["rawCode"], payload["rawCode"])
            self.assertEqual([d["code"] for d in parsed.json()["diagnostics"]],
                             ["AMBIGUOUS_TOKEN", "UNKNOWN_TOKEN"])
            self.assertEqual(parsed.headers["cache-control"], "no-store")
            self.assertEqual((await client.post(url, json={**payload, "profileVersion": "unknown"},
                                                headers=headers)).json()["error"]["code"], "PROFILE_UNSUPPORTED")
            self.assertEqual((await client.post(url, json={**payload, "rawCode": "x" * 129},
                                                headers=headers)).status_code, 422)
            oversized = await client.post(url, content=b"{" + b" " * 4096 + b"}", headers={
                **headers, "Content-Type": "application/json"})
            self.assertEqual(oversized.status_code, 413)
            catalog = await client.get("/api/v1/object-catalog/lookup/moln")
            self.assertEqual(catalog.status_code, 200)
            self.assertEqual(catalog.json()["status"], "mapped")


if __name__ == "__main__":
    unittest.main()
