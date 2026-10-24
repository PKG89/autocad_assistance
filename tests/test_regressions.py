"""Offline regression checks: python -m unittest discover -s tests -v."""

from geoai_bootstrap import require_isolation
require_isolation()

import atexit
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

import ezdxf
import pandas as pd
from pyproj import Transformer
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import CallbackContext, ConversationHandler

from autocad_assistance import state
from autocad_assistance.bot import file_handlers as fh, run
from autocad_assistance.dxf_generator import generate_dxf_ezdxf
from autocad_assistance.dxf_generator.surface import build_tin_surface, TIN_TRIANGLE_LAYER
from autocad_assistance.keyboard import BUTTON_NEW_DXF
from autocad_assistance.kml_generator.dxf_reader import load_dxf_lines
from autocad_assistance.kml_generator.kml_to_dxf import kml_to_dxf

atexit.unregister(run._on_exit)


def survey():
    return pd.DataFrame(
        [["a", 0., 0., 10., "ground", ""],
         ["b", 40., 0., 11., "ground", ""],
         ["c", 0., 40., 12., "ground", ""]],
        columns=["Point", "X", "Y", "Z", "Code", "Coments"],
    )


class GeometryTests(unittest.TestCase):
    def test_base_and_refined_tin_vertices(self):
        for refine in (False, True):
            with self.subTest(refine=refine):
                doc = ezdxf.new()
                result = build_tin_surface(survey(), doc.modelspace(), ["ground"], 1000, refine)
                faces = list(doc.modelspace().query("3DFACE"))
                self.assertEqual(len(faces), result.base_triangles + result.refined_triangles)
                base = [f for f in faces if f.dxf.layer == TIN_TRIANGLE_LAYER]
                self.assertEqual(len(base), 1)
                self.assertEqual(
                    {tuple(getattr(base[0].dxf, f"vtx{i}")) for i in range(3)},
                    {(0., 0., 10.), (40., 0., 11.), (0., 40., 12.)},
                )
                for face in faces:
                    a, b, c = (getattr(face.dxf, f"vtx{i}") for i in range(3))
                    self.assertGreater((b - a).cross(c - a).magnitude, 0)

    def test_kml_lines_preserve_altitudes_after_save(self):
        transformer = Transformer.from_crs(4326, 3857, always_xy=True)
        coords = [(37., 55., 100.), (37.001, 55.001, 150.), (37.002, 55.002, 175.)]
        with tempfile.TemporaryDirectory() as directory:
            for count in (2, 3):
                with self.subTest(vertices=count):
                    output = str(Path(directory) / f"line{count}.dxf")
                    with patch("autocad_assistance.kml_generator.kml_to_dxf.ezdxf.readfile", return_value=ezdxf.new()):
                        kml_to_dxf([], [(coords[:count], "survey")], transformer, output)
                    extracted = load_dxf_lines(output)[0][0]
                    self.assertEqual([p[2] for p in extracted], [p[2] for p in coords[:count]])
                    x, y = transformer.transform(coords[0][0], coords[0][1])
                    self.assertAlmostEqual(extracted[0][0], x)
                    self.assertAlmostEqual(extracted[0][1], y)

    def test_polyline_closure_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind in ("lw", "3d"):
                for closed in (False, True):
                    with self.subTest(kind=kind, closed=closed):
                        doc = ezdxf.new()
                        points = [(0, 0, 1), (10, 0, 2), (10, 10, 3), (0, 10, 4)]
                        if kind == "lw":
                            doc.modelspace().add_lwpolyline([p[:2] for p in points], close=closed)
                        else:
                            doc.modelspace().add_polyline3d(points, close=closed)
                        path = str(Path(directory) / "polyline.dxf")
                        doc.saveas(path)
                        coords = load_dxf_lines(path)[0][0]
                        self.assertEqual(len(coords), 5 if closed else 4)
                        self.assertEqual(coords[0] == coords[-1], closed)

    def test_invalid_coordinates_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "invalid.dxf"
            for value in ("", "bad", float("nan"), float("inf"), float("-inf")):
                with self.subTest(value=value):
                    df = survey().astype({"X": object})
                    df.loc[1, "X"] = value
                    with self.assertRaisesRegex(ValueError, "Строка данных 2"):
                        generate_dxf_ezdxf(df, str(output))
                    self.assertFalse(output.exists())

    def test_template_generation_smoke(self):
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "survey.dxf")
            generate_dxf_ezdxf(survey(), output, tin_settings={"codes": ["ground"]})
            doc = ezdxf.readfile(output)
            self.assertFalse(doc.audit().has_errors)
            face = doc.modelspace().query("3DFACE")[0]
            self.assertNotEqual(face.dxf.vtx0, face.dxf.vtx1)


class ImportTests(unittest.IsolatedAsyncioTestCase):
    async def test_csv_empty_fields_and_mapping_preserved(self):
        for mapping in ("1", "2"):
            for via_text in (False, True):
                with self.subTest(mapping=mapping, via_text=via_text), tempfile.TemporaryDirectory() as directory:
                    async def download(custom_path):
                        Path(custom_path).write_text(
                            "Point;X;Y;Z;Code;Comment\n1;100;200;;300;note\n2;110;210;12;;comment\n",
                            encoding="utf-8",
                        )
                    document = NS(file_name="input.csv", get_file=AsyncMock(return_value=NS(download_to_drive=download)))
                    update = NS(
                        effective_user=NS(id=1, username="test"), effective_chat=NS(id=1),
                        message=NS(document=document, reply_text=AsyncMock(), text=mapping),
                        callback_query=NS(data=mapping, answer=AsyncMock(), edit_message_text=AsyncMock()),
                    )
                    ctx = NS(user_data={})
                    with patch.object(fh.tempfile, "mkdtemp", return_value=directory), \
                            patch.object(fh.db, "record_usage"), \
                            patch.object(fh, "show_workflow_menu", new=AsyncMock()):
                        await fh.handle_file(update, ctx)
                        handler = fh.handle_mapping_text if via_text else fh.handle_mapping_callback
                        await handler(update, ctx)
                    data = ctx.user_data["final_data"]
                    self.assertEqual(len(data), 2)
                    self.assertEqual(data.iloc[0]["Z"], "")
                    self.assertEqual(data.iloc[0]["Code"], "300")
                    self.assertEqual(data.iloc[0]["X"], "100" if mapping == "1" else "200")
                    self.assertEqual(data.iloc[1]["Code"], "")
                    self.assertEqual(data.iloc[1]["Coments"], "comment")


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for target, kwargs in [
            ("autocad_assistance.bot.run.db.init_db", {}),
            ("autocad_assistance.bot.file_handlers.db.record_usage", {}),
            ("autocad_assistance.bot.file_handlers.show_workflow_menu", {"new": AsyncMock()}),
            ("telegram.CallbackQuery.answer", {"new": AsyncMock()}),
            ("telegram.CallbackQuery.edit_message_text", {"new": AsyncMock()}),
            ("telegram.Message.reply_text", {"new": AsyncMock()}),
        ]:
            p = patch(target, **kwargs)
            p.start()
            self.addCleanup(p.stop)
        self.app = run.build_app(token="123456:OFFLINE_TEST_ONLY")
        self.conv = next(h for h in self.app.handlers[0] if isinstance(h, ConversationHandler))
        self.conv._conversations[(7, 7)] = state.STATE_WORKFLOW
        self.context = CallbackContext(self.app, chat_id=7, user_id=7)
        self.context.user_data["data_initial"] = pd.DataFrame([["1", "100", "200", "10", "ground"]])

    async def dispatch(self, callback=None, text=None):
        user = User(7, "Test", False)
        message = Message(1, datetime.now(timezone.utc), Chat(7, "private"), from_user=user, text=text)
        update = Update(1, callback_query=CallbackQuery("query", user, "instance", message=message, data=callback)) if callback else Update(1, message=message)
        for handler in self.app.handlers[0]:
            match = handler.check_update(update)
            if match is not None and match is not False:
                await handler.handle_update(update, self.app, match, self.context)
                return handler
        self.fail("No handler matched")

    async def test_mapping_callback_then_text_updates_conversation(self):
        self.assertIs(await self.dispatch(callback="workflow_mapping"), self.conv)
        self.assertEqual(self.conv._conversations[(7, 7)], state.STATE_MAPPING)
        await self.dispatch(text="2")
        self.assertEqual(self.conv._conversations[(7, 7)], state.STATE_WORKFLOW)
        self.assertEqual(self.context.user_data["final_data"].iloc[0]["X"], "200")

    async def test_scale_prompt_and_selection(self):
        await self.dispatch(callback="workflow_scale")
        self.assertEqual(self.conv._conversations[(7, 7)], state.STATE_SCALE)
        self.assertIn("Выберите масштаб", Message.reply_text.call_args.args[0])
        await self.dispatch(callback="scale_500")
        self.assertEqual(self.conv._conversations[(7, 7)], state.STATE_WORKFLOW)
        self.assertEqual(self.context.user_data["scale_value"], 500)

    async def test_new_file_resets_state_and_projection(self):
        self.context.user_data.update(kml_to_dxf_mode=True, kml_file_path="old.kml", dxf_projection="old", dxf_transformer="old", kml_lon_hint=37)
        await self.dispatch(callback="workflow_newfile")
        self.assertEqual(self.context.user_data, {})
        self.assertEqual(self.conv._conversations[(7, 7)], state.STATE_FILE)

    async def test_main_menu_can_restart_ended_conversation(self):
        self.conv._conversations.clear()
        await self.dispatch(text=BUTTON_NEW_DXF)
        self.assertEqual(self.conv._conversations[(7, 7)], state.STATE_FILE)


if __name__ == "__main__":
    unittest.main()
