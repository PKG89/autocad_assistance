"""Focused tests for the upload preview API contract."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

import httpx

from autocad_assistance.api import create_app


class UploadPreviewEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def upload_root(self) -> Path:
        return Path(self._tmp.name) / self._testMethodName

    async def upload(self, *, filename: str, content: bytes, max_preview_rows: int = 5):
        app = create_app(
            upload_root=self.upload_root(),
            max_upload_bytes=1024 * 1024,
            max_preview_rows=max_preview_rows,
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/uploads",
                files={"file": (filename, content, "application/octet-stream")},
            )
        self.assertEqual(response.status_code, 201)
        return response.json()["uploadId"]

    async def get_preview(self, upload_id: str, query: str = "", max_preview_rows: int = 5):
        app = create_app(
            upload_root=self.upload_root(),
            max_upload_bytes=1024 * 1024,
            max_preview_rows=max_preview_rows,
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(f"/api/v1/uploads/{upload_id}/preview{query}")

    async def test_preview_success_with_header_and_default_limit(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=(
                b"Point,X,Y,Z,Code\n"
                b"A,1,2,3,g\n"
                b"B,4,5,6,g\n"
                b"C,7,8,9,g\n"
            ),
            max_preview_rows=2,
        )

        response = await self.get_preview(upload_id, max_preview_rows=2)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["uploadId"], upload_id)
        self.assertEqual(body["format"], "csv")
        self.assertEqual(body["columns"], ["Point", "X", "Y", "Z", "Code"])
        self.assertEqual(body["rowCount"], 3)
        self.assertEqual(body["returnedRows"], 2)
        self.assertEqual(body["rows"], [["A", "1", "2", "3", "g"], ["B", "4", "5", "6", "g"]])
        self.assertEqual(body["warnings"], [])

    async def test_preview_success_without_header_generates_columns_and_warnings(self):
        upload_id = await self.upload(
            filename="survey.txt",
            content=b"A;1;2;3\nB;4;5;6;code\n",
        )

        response = await self.get_preview(upload_id, query="?limit=10")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "PREVIEW_LIMIT_EXCEEDED")

        response = await self.get_preview(upload_id, query="?limit=5")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["columns"], ["Column 1", "Column 2", "Column 3", "Column 4", "Column 5"])
        self.assertEqual(
            body["warnings"],
            [
                {"code": "HEADER_NOT_DETECTED", "message": "Survey header was not detected"},
                {
                    "code": "INCONSISTENT_COLUMNS",
                    "message": "Survey rows have inconsistent column counts",
                },
            ],
        )

    async def test_preview_validates_limit_before_lookup(self):
        unknown_id = str(uuid4())
        response = await self.get_preview(
            unknown_id,
            query="?limit=6",
            max_preview_rows=5,
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "PREVIEW_LIMIT_EXCEEDED")

    async def test_preview_unknown_upload_returns_not_found(self):
        response = await self.get_preview(str(uuid4()))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "UPLOAD_NOT_FOUND")

    async def test_preview_invalid_uuid_uses_validation_handler(self):
        response = await self.get_preview("not-a-uuid")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(),
            {"error": {"code": "VALIDATION_ERROR", "message": "Invalid request"}},
        )

    async def test_preview_rejects_non_positive_limit(self):
        response = await self.get_preview(str(uuid4()), query="?limit=0")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    async def test_preview_rejects_kml_format(self):
        upload_id = await self.upload(filename="survey.kml", content=b"<kml></kml>")
        response = await self.get_preview(upload_id)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "UNSUPPORTED_PREVIEW_FORMAT")

    async def test_preview_rejects_header_only_survey(self):
        upload_id = await self.upload(filename="survey.csv", content=b"Point,X,Y,Z\n")
        response = await self.get_preview(upload_id)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_SURVEY")
        self.assertNotIn("path", response.json()["error"])

    async def test_preview_rejects_oversized_csv_field(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"Point,X,Y,Z\n" + (b"A" * 140000) + b",1,2,3\n",
        )
        response = await self.get_preview(upload_id)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "INVALID_SURVEY",
                    "message": "Survey data cannot be previewed",
                }
            },
        )

    async def test_preview_rejects_symlinked_upload_directory(self):
        root = self.upload_root()
        root.mkdir(parents=True, exist_ok=True)
        upload_id = str(uuid4())
        target = root / "real-dir"
        target.mkdir()
        (target / f"{upload_id}.csv").write_bytes(b"A,1,2,3\n")
        (root / upload_id).symlink_to(target, target_is_directory=True)

        response = await self.get_preview(upload_id)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "UPLOAD_NOT_FOUND")

    async def test_preview_rejects_symlinked_upload_file(self):
        root = self.upload_root()
        root.mkdir(parents=True, exist_ok=True)
        upload_id = str(uuid4())
        upload_dir = root / upload_id
        upload_dir.mkdir()
        target = root / "external.csv"
        target.write_bytes(b"A,1,2,3\n")
        (upload_dir / f"{upload_id}.csv").symlink_to(target)

        response = await self.get_preview(upload_id)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "UPLOAD_NOT_FOUND")

    async def test_create_app_rejects_non_positive_preview_rows(self):
        with self.assertRaises(ValueError):
            create_app(upload_root=self.upload_root(), max_preview_rows=0)


if __name__ == "__main__":
    unittest.main()
