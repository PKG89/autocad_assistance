"""Owner project/import API and browser shell contract."""

from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.project_store import ProjectStore
from autocad_assistance.services.uploads import store_upload


SOURCE = b"Point,X,Y,Z,Code\nP1,123.456,234.567,11.2,K\n"
PASSWORD = "Synthetic-only-owner-passphrase-123"
MAPPING = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}


class ProjectApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.owner = AuthStore(self.root / "auth").create_owner("owner", PASSWORD).user_id
        self.store = ProjectStore(self.root / "projects")
        self.app = create_app(
            auth_root=self.root / "auth", project_root=self.root / "projects",
            upload_root=self.root / "uploads", auth_origin="https://testserver",
        )

    async def login(self, client):
        response = await client.post(
            "/api/v1/auth/login", json={"username": "owner", "password": PASSWORD},
            headers={"Origin": "https://testserver"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return {"Origin": "https://testserver", "X-CSRF-Token": response.json()["csrfToken"]}

    async def test_import_preserves_source_mapping_context_and_restart(self):
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            self.assertEqual((await client.post("/api/v1/projects", content=b"invalid")).status_code, 401)
            self.assertEqual((await client.post(
                f"/api/v1/projects/{uuid4()}/revisions", content=b"x" * (64 * 1024 + 1),
            )).status_code, 401)
            headers = await self.login(client)
            oversized = await client.post(
                f"/api/v1/projects/{uuid4()}/revisions",
                content=b"x" * (64 * 1024 + 1), headers=headers,
            )
            self.assertEqual(oversized.status_code, 413)
            self.assertEqual(oversized.json()["error"]["code"], "PROJECT_BODY_TOO_LARGE")
            self.assertEqual((await client.post("/api/v1/projects", json={"name": "No csrf"})).status_code, 403)
            self.assertEqual(self.store.list_projects_for(self.owner), ())
            created = await client.post("/api/v1/projects", json={"name": "Участок 1"}, headers=headers)
            self.assertEqual(created.status_code, 201, created.text)
            project_id = created.json()["projectId"]
            listed = await client.get("/api/v1/projects?page=1&pageSize=1")
            self.assertEqual(listed.json()["pagination"]["totalItems"], 1)
            self.assertEqual(listed.json()["data"][0]["projectId"], project_id)
            uploaded = await client.post(
                "/api/v1/uploads", headers=headers,
                files={"file": ("survey.csv", SOURCE, "text/csv")},
            )
            self.assertEqual(uploaded.status_code, 201, uploaded.text)
            upload_id = uploaded.json()["uploadId"]
            preview = await client.get(f"/api/v1/uploads/{upload_id}/preview")
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.json()["columns"], ["Point", "X", "Y", "Z", "Code"])
            payload = {
                "uploadId": upload_id, "mapping": MAPPING,
                "coordinateSystem": "local survey grid", "horizontalUnit": "m",
                "verticalUnit": "m", "scaleFactor": "500",
            }
            imported = await client.post(
                f"/api/v1/projects/{project_id}/revisions", json=payload, headers=headers,
            )
            self.assertEqual(imported.status_code, 201, imported.text)
            body = imported.json()
            self.assertEqual(body["rowCount"], 1)
            self.assertEqual(body["warnings"], [])
            revision_id = body["revision"]["revisionId"]
            second = await client.post(
                f"/api/v1/projects/{project_id}/revisions",
                json=dict(payload, scaleFactor="1000"), headers=headers,
            )
            self.assertEqual(second.status_code, 201, second.text)
            self.assertEqual(second.json()["revision"]["sequence"], 2)
            revisions = await client.get(f"/api/v1/projects/{project_id}/revisions?pageSize=1")
            self.assertEqual(revisions.json()["pagination"]["totalItems"], 2)
            self.assertEqual(revisions.json()["data"][0]["revisionId"], second.json()["revision"]["revisionId"])
        reopened = ProjectStore(self.root / "projects")
        revision = reopened.assert_revision_owner(self.owner, revision_id)
        settings = json.loads(revision.settings_json)
        self.assertEqual(settings["coordinateSystem"], "local survey grid")
        self.assertEqual(settings["horizontalUnit"], "m")
        self.assertEqual(settings["scaleFactor"], "500")
        self.assertEqual(settings["renderSettings"]["mapping"], MAPPING)
        self.assertEqual(reopened.read_source_for(self.owner, project_id, revision_id), SOURCE)

    async def test_foreign_unknown_invalid_and_kml_do_not_accept_revision(self):
        foreign_owner = str(uuid4())
        foreign_project = self.store.create_owned_project(foreign_owner, "Foreign")
        mine = self.store.create_owned_project(self.owner, "Mine")
        foreign_upload = store_upload(BytesIO(SOURCE), "foreign.csv", self.root / "uploads", 10 * 1024 * 1024)
        self.store.register_upload_owner(foreign_owner, foreign_upload)
        own_upload = store_upload(BytesIO(SOURCE), "mine.csv", self.root / "uploads", 10 * 1024 * 1024)
        self.store.register_upload_owner(self.owner, own_upload)
        kml = store_upload(
            BytesIO(b"<kml><Placemark><Point><coordinates>1,2</coordinates></Point></Placemark></kml>"),
            "source.kml", self.root / "uploads", 10 * 1024 * 1024,
        )
        self.store.register_upload_owner(self.owner, kml)
        payload = {"uploadId": own_upload.upload_id, "mapping": MAPPING, "scaleFactor": "500"}
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            headers = await self.login(client)
            self.assertEqual((await client.get(f"/api/v1/projects/{foreign_project.project_id}/revisions")).status_code, 404)
            for candidate in (foreign_project.project_id, str(uuid4())):
                response = await client.post(
                    f"/api/v1/projects/{candidate}/revisions", json=payload, headers=headers,
                )
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["error"]["code"], "RESOURCE_NOT_FOUND")
            changed = dict(payload, uploadId=foreign_upload.upload_id)
            self.assertEqual((await client.post(
                f"/api/v1/projects/{mine.project_id}/revisions", json=changed, headers=headers,
            )).status_code, 404)
            invalid = dict(payload, mapping={"X": 1, "Y": 1, "Z": 3}, scaleFactor="500")
            self.assertEqual((await client.post(
                f"/api/v1/projects/{mine.project_id}/revisions", json=invalid, headers=headers,
            )).status_code, 422)
            bad_scale = dict(payload, scaleFactor="zero")
            self.assertEqual((await client.post(
                f"/api/v1/projects/{mine.project_id}/revisions", json=bad_scale, headers=headers,
            )).status_code, 422)
            kml_payload = dict(payload, uploadId=kml.upload_id)
            kml_response = await client.post(
                f"/api/v1/projects/{mine.project_id}/revisions", json=kml_payload, headers=headers,
            )
            self.assertEqual(kml_response.status_code, 422)
            self.assertEqual(kml_response.json()["error"]["code"], "UNSUPPORTED_IMPORT_FORMAT")
            self.assertEqual(self.store.list_revisions_for(self.owner, mine.project_id), ())

    async def test_web_shell_is_local_and_uses_strict_headers(self):
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            page = await client.get("/app")
            script = await client.get("/app/app.js")
            styles = await client.get("/app/styles.css")
            self.assertEqual((page.status_code, script.status_code, styles.status_code), (200, 200, 200))
            self.assertIn("script-src 'self'", page.headers["content-security-policy"])
            self.assertIn("no-store", page.headers["cache-control"])
            self.assertIn('src="/app/app.js"', page.text)
            self.assertNotIn("innerHTML", script.text)
            self.assertNotIn("localStorage", script.text)
            self.assertNotIn("sessionStorage", script.text)
            self.assertIn("textContent", script.text)
            self.assertIn("button:disabled", styles.text)
        unconfigured = create_app(upload_root=self.root / "public-uploads")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=unconfigured), base_url="https://testserver",
        ) as client:
            self.assertEqual((await client.get("/app")).status_code, 404)


if __name__ == "__main__":
    unittest.main()
