"""Focused contract tests for explicit mapping preview API."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

import httpx

from autocad_assistance.api import create_app


class MappingEndpointTests(unittest.IsolatedAsyncioTestCase):
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

    async def map_rows(
        self,
        upload_id: str,
        payload: dict,
        query: str = "",
        max_preview_rows: int = 5,
    ):
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
            return await client.post(
                f"/api/v1/uploads/{upload_id}/mapping{query}",
                json=payload,
            )

    async def test_mapping_success_returns_typed_rows(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"A,1,2,3,C1,hello\nB,4,5,6,C2,world\n",
            max_preview_rows=5,
        )
        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4, "Comments": 5}},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["uploadId"], upload_id)
        self.assertEqual(body["rowCount"], 2)
        self.assertEqual(body["returnedRows"], 2)
        self.assertEqual(
            body["rows"][0],
            {"Point": "A", "X": "1", "Y": "2", "Z": "3", "Code": "C1", "Comments": "hello"},
        )

    async def test_mapping_returns_null_comments_when_not_selected(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"A,1,2,3,C1\n",
        )
        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["rows"][0]["Comments"])

    async def test_mapping_reports_duplicate_ids_and_unknown_coordinate_context(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"A,1,2,3,C1\nA,4,5,6,C2\n",
        )
        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([row["Point"] for row in body["rows"]], ["A", "A"])
        self.assertEqual(
            [warning["code"] for warning in body["warnings"]],
            [
                "DUPLICATE_POINT_ID",
                "UNKNOWN_COORDINATE_SYSTEM",
                "UNKNOWN_HORIZONTAL_UNIT",
                "UNKNOWN_VERTICAL_UNIT",
            ],
        )
        self.assertEqual(body["warnings"][0]["rowIndex"], 2)

    async def test_mapping_validates_all_rows_even_when_limited(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"A,1,2,3,C1\nB,nan,5,6,C2\n",
            max_preview_rows=5,
        )
        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
            query="?limit=1",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_COORDINATE")

    async def test_mapping_uses_limit_default_and_bound(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"A,1,2,3,C1\nB,4,5,6,C2\nC,7,8,9,C3\n",
            max_preview_rows=2,
        )

        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
            max_preview_rows=2,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["returnedRows"], 2)

        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
            query="?limit=3",
            max_preview_rows=2,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "PREVIEW_LIMIT_EXCEEDED")

    async def test_mapping_rejects_kml(self):
        upload_id = await self.upload(filename="survey.kml", content=b"<kml></kml>")
        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "UNSUPPORTED_MAPPING_FORMAT")

    async def test_mapping_unknown_upload_not_found(self):
        response = await self.map_rows(
            str(uuid4()),
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "UPLOAD_NOT_FOUND")

    async def test_mapping_rejects_symlinked_upload_directory(self):
        root = self.upload_root()
        root.mkdir(parents=True, exist_ok=True)
        upload_id = str(uuid4())
        target = root / "real-dir"
        target.mkdir()
        (target / f"{upload_id}.csv").write_bytes(b"A,1,2,3,C1\n")
        (root / upload_id).symlink_to(target, target_is_directory=True)

        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "UPLOAD_NOT_FOUND")

    async def test_mapping_invalid_uuid_uses_validation_handler(self):
        response = await self.map_rows(
            "not-a-uuid",
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(),
            {"error": {"code": "VALIDATION_ERROR", "message": "Invalid request"}},
        )

    async def test_mapping_invalid_body_uses_validation_handler(self):
        upload_id = await self.upload(filename="survey.csv", content=b"A,1,2,3,C1\n")
        response = await self.map_rows(upload_id, payload={"wrong": {}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    async def test_mapping_reports_invalid_column_mapping(self):
        upload_id = await self.upload(filename="survey.csv", content=b"A,1,2,3,C1\n")
        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": 1, "Y": 1, "Z": 3, "Code": 4}},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_COLUMN_MAPPING")

    async def test_mapping_rejects_boolean_index(self):
        upload_id = await self.upload(filename="survey.csv", content=b"A,1,2,3,C1\n")
        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": True, "Y": 2, "Z": 3, "Code": 4}},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_COLUMN_MAPPING")

    async def test_mapping_rejects_empty_or_unusable_survey(self):
        upload_id = str(uuid4())
        folder = self.upload_root() / upload_id
        folder.mkdir(parents=True)
        (folder / f"{upload_id}.csv").write_bytes(b"Point,X,Y,Z\n")
        response = await self.map_rows(
            upload_id,
            payload={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_SURVEY")
        self.assertNotIn("path", response.json()["error"])


if __name__ == "__main__":
    unittest.main()
