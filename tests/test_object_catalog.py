"""SinoKOD/config evidence is snapshotted without executing configuration."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.object_catalog import (
    CONFIG_PATH, SINO_PATH, SNAPSHOT_PATH, CatalogSourceError,
    build_current_snapshot, build_snapshot, load_snapshot, lookup, snapshot_bytes,
)


ORIGIN = "https://testserver"
PASSWORD = "Synthetic-only-owner-passphrase-123"


class ObjectCatalogTests(unittest.TestCase):
    def test_snapshot_is_stable_and_source_bound(self):
        with patch.dict(sys.modules, {"autocad_assistance.config": None}):
            built = build_current_snapshot()
        self.assertEqual(snapshot_bytes(built), SNAPSHOT_PATH.read_bytes())
        self.assertEqual(load_snapshot(), built)
        self.assertEqual(len(built["entries"]), 75)
        self.assertEqual(built["sources"]["config.py"], sha256(CONFIG_PATH.read_bytes()).hexdigest())
        self.assertEqual(built["sources"]["SinoKOD.txt"], sha256(SINO_PATH.read_bytes()).hexdigest())
        self.assertEqual([row["sourceLine"] for row in built["entries"]], list(range(2, 77)))
        self.assertEqual(built["lineLayerOverrides"].keys(), {"gaz", "neft", "voda"})
        self.assertEqual(lookup(built, "moln")["blockCandidates"][0]["blockName"], "109a")
        self.assertEqual(lookup(built, "gaz1")["lineRule"]["layer"], "(036) Газопроводы")
        self.assertEqual(lookup(built, "vlGB")["status"], "dynamic_support")
        self.assertEqual(lookup(built, "tower1")["status"], "dynamic_tower")
        self.assertEqual(lookup(built, "unknown-code")["status"], "unmapped")

    def test_conflict_is_visible_and_source_drift_changes_snapshot(self):
        config = CONFIG_PATH.read_text(encoding="utf-8")
        sino = SINO_PATH.read_text(encoding="utf-8")
        changed = config.replace('"code": {"fonar", "фонар"}',
                                 '"code": {"fonar", "фонар", "moln"}', 1)
        self.assertNotEqual(changed, config)
        built = build_snapshot(changed, sino)
        moln = next(row for row in built["entries"] if row["code"] == "moln")
        self.assertEqual(moln["status"], "ambiguous")
        self.assertEqual(len(moln["blockCandidates"]), 2)
        self.assertNotEqual(snapshot_bytes(built), SNAPSHOT_PATH.read_bytes())
        self.assertNotEqual(snapshot_bytes(build_snapshot(config, sino + "\n")), SNAPSHOT_PATH.read_bytes())

    def test_executable_config_is_rejected_without_execution(self):
        config = CONFIG_PATH.read_text(encoding="utf-8")
        sino = SINO_PATH.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "must-not-exist"
            attack = config.replace('"name": "109a"',
                f'"name": __import__("pathlib").Path({str(marker)!r}).touch()', 1)
            with self.assertRaises(CatalogSourceError):
                build_snapshot(attack, sino)
            self.assertFalse(marker.exists())
        with self.assertRaises(CatalogSourceError):
            build_snapshot("polyline_prefixes = eval('danger')", sino)


class ObjectCatalogApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        AuthStore(root / "auth").create_owner("owner", PASSWORD)
        self.app = create_app(auth_root=root / "auth", project_root=root / "projects",
                              upload_root=root / "uploads", auth_origin=ORIGIN)

    async def test_catalog_page_and_exact_lookup_need_owner(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            self.assertEqual((await client.get("/api/v1/object-catalog")).status_code, 401)
            login = await client.post("/api/v1/auth/login", json={
                "username": "owner", "password": PASSWORD,
            }, headers={"Origin": ORIGIN})
            self.assertEqual(login.status_code, 200, login.text)
            first = await client.get("/api/v1/object-catalog?page=1&pageSize=20")
            self.assertEqual(first.status_code, 200, first.text)
            page = first.json()
            self.assertEqual(page["pagination"]["totalItems"], 75)
            self.assertEqual(len(page["data"]), 20)
            self.assertTrue(page["pagination"]["hasMore"])
            self.assertEqual(first.headers["cache-control"], "no-store")
            last = await client.get("/api/v1/object-catalog?page=4&pageSize=20")
            self.assertEqual(len(last.json()["data"]), 15)
            self.assertEqual((await client.get("/api/v1/object-catalog?pageSize=51")).status_code, 422)
            found = await client.get("/api/v1/object-catalog/lookup/moln")
            self.assertEqual(found.status_code, 200, found.text)
            self.assertEqual(found.json()["status"], "mapped")
            self.assertEqual(found.json()["matchingEntries"][0]["sourceLine"], 2)
            self.assertEqual((await client.get("/api/v1/object-catalog/lookup/unknown-code")).json()
                             ["status"], "unmapped")


if __name__ == "__main__":
    unittest.main()
