"""One synthetic survey through authenticated web and offline Telegram handlers."""

from __future__ import annotations

import asyncio
from hashlib import sha256
from io import BytesIO
import json
import platform
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import ezdxf
from ezdxf.math import Vec3
import httpx

from autocad_assistance.api import create_app
from autocad_assistance.bot import file_handlers, run
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.survey_contract import SurveyContext, build_survey_dataset


FIXTURE = Path(__file__).resolve().parents[1] / "harness" / "fixtures" / "021-field.csv"
SOURCE = FIXTURE.read_bytes()
MAPPING = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4, "Comments": 5}
ORIGIN = "https://testserver"
PASSWORD = "Synthetic-only-owner-passphrase-021"
SUPPORTED = {"POINT", "MTEXT", "INSERT", "LINE", "LWPOLYLINE", "POLYLINE", "3DFACE", "CIRCLE"}


def _canonical(value):
    if isinstance(value, Vec3):
        return [component.hex() for component in value]
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return repr(value)


def semantic_inventory(raw: bytes, path: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    path.write_bytes(raw)
    doc = ezdxf.readfile(path)
    inventory = []
    unsupported = []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind not in SUPPORTED:
            unsupported.append(kind)
            continue
        attributes = {
            key: _canonical(value)
            for key, value in entity.dxfattribs().items()
            if key not in {"handle", "owner", "paperspace"}
        }
        if kind == "MTEXT":
            attributes["content"] = entity.text
        if kind == "LWPOLYLINE":
            attributes["vertices"] = _canonical(list(entity.get_points("xyseb")))
            attributes["closed"] = entity.closed
        if kind == "POLYLINE":
            attributes["vertices"] = [_canonical(vertex.dxf.location) for vertex in entity.vertices]
            attributes["closed"] = entity.is_closed
        inventory.append(json.dumps([kind, attributes], sort_keys=True, ensure_ascii=False))
    return tuple(sorted(inventory)), tuple(sorted(unsupported))


class WebTelegramAcceptanceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        AuthStore(self.root / "auth").create_owner("owner", PASSWORD)
        self.app = create_app(
            auth_root=self.root / "auth", project_root=self.root / "projects",
            upload_root=self.root / "uploads", jobs_root=self.root / "jobs",
            auth_origin=ORIGIN,
        )
        self.addCleanup(self.app.state.job_manager.close)

    async def _web_flow(self):
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
            login = await client.post("/api/v1/auth/login", json={
                "username": "owner", "password": PASSWORD,
            }, headers={"Origin": ORIGIN})
            self.assertEqual(login.status_code, 200, login.text)
            headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrfToken"]}
            started = time.perf_counter()
            upload = await client.post("/api/v1/uploads", headers=headers,
                files={"file": ("021-field.csv", SOURCE, "text/csv")})
            self.assertEqual(upload.status_code, 201, upload.text)
            upload_id = upload.json()["uploadId"]
            preview = await client.get(f"/api/v1/uploads/{upload_id}/preview")
            self.assertEqual(preview.status_code, 200, preview.text)
            project = await client.post("/api/v1/projects", headers=headers,
                json={"name": "Synthetic parity"})
            self.assertEqual(project.status_code, 201, project.text)
            project_id = project.json()["projectId"]
            imported = await client.post(f"/api/v1/projects/{project_id}/revisions",
                headers=headers, json={
                    "uploadId": upload_id, "mapping": MAPPING,
                    "coordinateSystem": None, "horizontalUnit": None,
                    "verticalUnit": None, "scaleFactor": "500",
                })
            self.assertEqual(imported.status_code, 201, imported.text)
            revision_id = imported.json()["revision"]["revisionId"]
            job = await client.post("/api/v1/jobs", headers={
                **headers, "Idempotency-Key": str(uuid4()),
            }, json={"revisionId": revision_id, "tinSettings": {"codes": ["ground"], "refine": False}})
            self.assertEqual(job.status_code, 201, job.text)
            job_id = job.json()["jobId"]
            for _ in range(240):
                state = await client.get(f"/api/v1/jobs/{job_id}")
                self.assertEqual(state.status_code, 200, state.text)
                if state.json()["status"] in {"succeeded", "failed", "cancelled"}:
                    break
                await asyncio.sleep(0.05)
            self.assertEqual(state.json()["status"], "succeeded", state.text)
            self.assertTrue(state.json()["resultReady"])
            download = await client.get(f"/api/v1/jobs/{job_id}/result")
            self.assertEqual(download.status_code, 200, download.text[:100])
            elapsed = time.perf_counter() - started
            return preview.json(), imported.json(), download.content, elapsed

    async def _telegram_flow(self):
        user = SimpleNamespace(id=1, username="synthetic")
        chat = SimpleNamespace(id=1, send_message=AsyncMock(return_value=SimpleNamespace(message_id=1)))
        bot = SimpleNamespace(send_document=AsyncMock(), delete_message=AsyncMock())
        context = SimpleNamespace(user_data={}, bot=bot)
        file = SimpleNamespace(download_to_drive=AsyncMock(
            side_effect=lambda custom_path: Path(custom_path).write_bytes(SOURCE),
        ))
        document = SimpleNamespace(file_name="021-field.csv", get_file=AsyncMock(return_value=file))
        message = SimpleNamespace(document=document, reply_text=AsyncMock())
        query = SimpleNamespace(
            data="1", from_user=user, answer=AsyncMock(), edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(
            message=message, effective_user=user, effective_chat=chat, callback_query=query,
        )
        with patch.object(file_handlers.db, "record_usage"), patch.object(run.db, "init_db"):
            started = time.perf_counter()
            await file_handlers.handle_file(update, context)
            self.addCleanup(shutil.rmtree, Path(context.user_data["file_path"]).parent)
            parsed_rows = context.user_data["data_initial"].fillna("").astype(str).values.tolist()
            await file_handlers.handle_mapping_callback(update, context)
            query.data = "scale_500"
            await file_handlers.handle_scale_callback(update, context)
            context.user_data["tin_codes"] = ["ground"]
            query.data = "workflow_generate"
            application = run.build_app(token="123456:OFFLINE_TEST_ONLY")
            callback = next(
                handler.callback for handlers in application.handlers.values() for handler in handlers
                if getattr(getattr(handler, "callback", None), "__name__", "") == "_workflow_generate"
            )
            await callback(update, context)
            self.assertEqual(bot.send_document.await_count, 1)
            rendered = bot.send_document.await_args.kwargs["document"].getvalue()
            elapsed = time.perf_counter() - started
            return parsed_rows, context.user_data, rendered, elapsed

    async def test_web_and_offline_telegram_have_same_semantic_dxf(self):
        web_preview, web_import, web_dxf, web_seconds = await self._web_flow()
        telegram_rows, telegram_state, telegram_dxf, telegram_seconds = await self._telegram_flow()
        self.assertEqual(web_preview["rows"], telegram_rows[:len(web_preview["rows"])])
        self.assertEqual(web_import["rowCount"], len(telegram_rows))
        self.assertEqual(telegram_state["survey_source_sha256"], sha256(SOURCE).hexdigest())
        self.assertEqual(telegram_state["mapping"], {key: value for key, value in MAPPING.items() if key != "Comments"})
        self.assertEqual(telegram_state["scale_factor"], 0.5)
        web_rows = build_survey_dataset(SOURCE, MAPPING, context=SurveyContext(scale_factor="500")).mapped_rows
        telegram_rows_mapped, telegram_warnings = run._telegram_contract_rows(
            telegram_state, telegram_state["final_data"], telegram_state["scale_factor"],
        )
        self.assertEqual(web_rows, telegram_rows_mapped)
        self.assertEqual(
            sorted(item["code"] for item in web_import["warnings"]),
            sorted(item.code for item in telegram_warnings),
        )
        web_inventory, web_unsupported = semantic_inventory(web_dxf, self.root / "web.dxf")
        telegram_inventory, telegram_unsupported = semantic_inventory(
            telegram_dxf, self.root / "telegram.dxf",
        )
        self.assertEqual(web_unsupported, ())
        self.assertEqual(telegram_unsupported, ())
        self.assertEqual(web_inventory, telegram_inventory)
        self.assertTrue(any('"INSERT"' in item for item in web_inventory))
        changed = ezdxf.readfile(self.root / "web.dxf")
        point = next(entity for entity in changed.modelspace() if entity.dxftype() == "POINT")
        x, y, z = point.dxf.location
        point.dxf.location = (x + 1, y, z)
        changed.saveas(self.root / "changed.dxf")
        changed_inventory, changed_unsupported = semantic_inventory(
            (self.root / "changed.dxf").read_bytes(), self.root / "changed-copy.dxf",
        )
        self.assertEqual(changed_unsupported, ())
        self.assertNotEqual(web_inventory, changed_inventory)
        print("GEOAI021_METRICS " + json.dumps({
            "fixture_sha256": sha256(SOURCE).hexdigest(),
            "web_seconds": round(web_seconds, 6),
            "telegram_seconds": round(telegram_seconds, 6),
            "parent_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "child_peak_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
            "python": sys.version.split()[0], "platform": platform.platform(),
            "entity_count": len(web_inventory),
        }, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
