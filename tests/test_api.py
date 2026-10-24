"""Focused contract tests for the isolated FastAPI adapter."""

import hashlib
import os
from pathlib import Path
import unittest
from uuid import UUID

import httpx

from autocad_assistance.api import create_app


class HealthEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_contract(self):
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "autocad-assistance-geo-ai"},
        )
        self.assertEqual(response.headers["content-type"], "application/json")


class UploadEndpointTests(unittest.IsolatedAsyncioTestCase):
    def upload_root(self) -> Path:
        return Path(os.environ["UPLOAD_ROOT"]) / self._testMethodName

    async def request(self, *, filename: str, content: bytes, max_bytes: int = 1024):
        app = create_app(
            upload_root=self.upload_root(),
            max_upload_bytes=max_bytes,
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/api/v1/uploads",
                files={"file": (filename, content, "application/octet-stream")},
            )

    async def test_upload_uses_server_generated_path(self):
        payload = b"Point;X;Y;Z;Code\n1;100;200;10;ground\n"
        response = await self.request(
            filename=r"..\..\survey.csv",
            content=payload,
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        UUID(body["uploadId"])
        self.assertEqual(body["originalFilename"], "survey.csv")
        self.assertEqual(body["format"], "csv")
        self.assertEqual(body["sizeBytes"], len(payload))
        self.assertEqual(body["sha256"], hashlib.sha256(payload).hexdigest())

        stored = (
            self.upload_root()
            / body["uploadId"]
            / f"{body['uploadId']}.csv"
        )
        self.assertEqual(stored.read_bytes(), payload)

    async def test_upload_rejects_unsupported_format(self):
        response = await self.request(filename="survey.exe", content=b"not executable")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["code"],
            "UNSUPPORTED_FILE_FORMAT",
        )
        self.assertFalse(self.upload_root().exists())

    async def test_upload_rejects_oversized_file_without_partial_data(self):
        response = await self.request(
            filename="survey.txt",
            content=b"12345",
            max_bytes=4,
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "UPLOAD_TOO_LARGE")
        self.assertEqual(list(self.upload_root().rglob("*")), [])

    async def test_upload_requires_file_with_consistent_error_shape(self):
        app = create_app(upload_root=self.upload_root())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post("/api/v1/uploads")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request",
                }
            },
        )

    async def test_request_body_limit_has_consistent_error_shape(self):
        response = await self.request(
            filename="survey.txt",
            content=b"x" * 100_000,
            max_bytes=1024,
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "UPLOAD_TOO_LARGE")
        self.assertFalse(self.upload_root().exists())


if __name__ == "__main__":
    unittest.main()
