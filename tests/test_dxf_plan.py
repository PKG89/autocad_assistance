"""Read-only, bounded DXF plan projection for local coordinates."""

from __future__ import annotations

from io import StringIO
import unittest
from unittest.mock import patch

import ezdxf

from autocad_assistance.services import dxf_plan


def drawing_bytes() -> bytes:
    drawing = ezdxf.new("R2010")
    model = drawing.modelspace()
    model.add_point((1_000_000, 2_000_000, 31), dxfattribs={"layer": "Measured"})
    model.add_line((1_000_000, 2_000_000), (1_000_010, 2_000_020),
                   dxfattribs={"layer": "Lines"})
    model.add_mtext("A" * 80, dxfattribs={"insert": (1_000_000, 2_000_000),
                                          "layer": "Labels"})
    block = drawing.blocks.new("SYMBOL")
    block.add_circle((0, 0), 1, dxfattribs={"layer": "0"})
    model.add_blockref("SYMBOL", (1_000_005, 2_000_005),
                       dxfattribs={"layer": "Symbols"})
    output = StringIO()
    drawing.write(output)
    return output.getvalue().encode("utf-8")


class DxfPlanTests(unittest.TestCase):
    def test_local_geometry_block_and_text_are_bounded_without_mutation(self):
        raw = drawing_bytes()
        original = bytes(raw)
        plan = dxf_plan.project_plan(raw, "synthetic-job")
        self.assertEqual(raw, original)
        self.assertEqual(plan["jobId"], "synthetic-job")
        self.assertEqual(plan["sourceEntities"], 4)
        self.assertEqual(plan["unsupported"], {})
        self.assertEqual(plan["bounds"]["minX"], 1_000_000)
        self.assertEqual(plan["bounds"]["maxY"], 2_000_020)
        self.assertEqual({entry["name"] for entry in plan["layers"]},
                         {"Measured", "Lines", "Labels", "Symbols"})
        point = next(entry for entry in plan["entities"] if entry["type"] == "POINT")
        self.assertEqual(point["point"], [1_000_000, 2_000_000, 31])
        insert = next(entry for entry in plan["entities"] if entry["type"] == "INSERT")
        self.assertTrue(insert["complete"])
        self.assertEqual(insert["children"][0]["type"], "CIRCLE")
        self.assertEqual(insert["children"][0]["layer"], "Symbols")
        label = next(entry for entry in plan["entities"] if entry["type"] == "MTEXT")
        self.assertEqual(len(label["text"]), dxf_plan.MAX_TEXT_CHARS)

    def test_corrupt_and_over_limit_input_are_rejected(self):
        with self.assertRaises(dxf_plan.PlanInvalidError):
            dxf_plan.project_plan(b"garbage", "job")
        with self.assertRaises(dxf_plan.PlanLimitError):
            dxf_plan.project_plan(b"x" * (dxf_plan.MAX_DXF_BYTES + 1), "job")
        raw = drawing_bytes()
        with patch.object(dxf_plan, "MAX_ENTITIES", 2):
            with self.assertRaises(dxf_plan.PlanLimitError):
                dxf_plan.project_plan(raw, "job")
        with patch.object(dxf_plan, "MAX_VERTICES", 1):
            with self.assertRaises(dxf_plan.PlanLimitError):
                dxf_plan.project_plan(raw, "job")

    def test_bulged_polyline_is_explicitly_unsupported(self):
        drawing = ezdxf.new("R2010")
        drawing.modelspace().add_lwpolyline([(0, 0, 1), (2, 0, 0)], format="xyb")
        output = StringIO()
        drawing.write(output)
        plan = dxf_plan.project_plan(output.getvalue().encode("utf-8"), "job")
        self.assertEqual(plan["entities"], [])
        self.assertEqual(plan["unsupported"], {"LWPOLYLINE_BULGE": 1})


if __name__ == "__main__":
    unittest.main()
