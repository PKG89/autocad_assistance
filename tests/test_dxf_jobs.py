from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from autocad_assistance.services.dxf_jobs import render_dxf_bytes


def _mapped_rows() -> tuple[dict[str, str | None], ...]:
    return (
        {
            "Point": "A",
            "X": "100",
            "Y": "200",
            "Z": "10",
            "Code": "ground",
            "Comments": "note",
        },
    )


class DxfJobsTests(unittest.TestCase):
    def test_render_dxf_bytes_supports_comments_mapping_and_tin_passthrough(self):
        captured: dict[str, object] = {}

        def fake_generate(frame, output_path, scale_factor=1.0, tin_settings=None):
            captured["columns"] = list(frame.columns)
            captured["comment"] = frame.iloc[0]["Coments"]
            captured["scale_factor"] = scale_factor
            captured["tin_settings"] = tin_settings
            Path(output_path).write_bytes(b"DXF-BYTES")

        with patch("autocad_assistance.services.dxf_jobs.generate_dxf_ezdxf", new=fake_generate):
            result = render_dxf_bytes(
                _mapped_rows(),
                scale_factor=0.5,
                tin_settings={"codes": ["ground"], "refine": True},
            )

        self.assertEqual(result, b"DXF-BYTES")
        self.assertIn("Coments", captured["columns"])
        self.assertEqual(captured["comment"], "note")
        self.assertEqual(captured["scale_factor"], 0.5)
        self.assertEqual(captured["tin_settings"], {"codes": ["ground"], "refine": True})

    def test_render_dxf_bytes_normalizes_absent_comments_without_fabricating_none(self):
        captured: dict[str, object] = {}

        def fake_generate(frame, output_path, scale_factor=1.0, tin_settings=None):
            del scale_factor, tin_settings
            captured["comments"] = list(frame["Coments"])
            Path(output_path).write_bytes(b"DXF-BYTES")

        rows = (
            {"Point": "A", "X": "1", "Y": "2", "Z": "3", "Code": "g", "Comments": None},
            {"Point": "B", "X": "4", "Y": "5", "Z": "6", "Code": "g", "Comments": None},
            {"Point": "C", "X": "7", "Y": "8", "Z": "9", "Code": "g", "Comments": "actual note"},
        )
        with patch("autocad_assistance.services.dxf_jobs.generate_dxf_ezdxf", new=fake_generate):
            render_dxf_bytes(rows)

        self.assertEqual(captured["comments"], ["", "", "actual note"])

    def test_render_dxf_bytes_rejects_non_finite_coordinates_before_output(self):
        frame = pd.DataFrame(
            [["A", "100", "nan", "10", "g", ""]],
            columns=["Point", "X", "Y", "Z", "Code", "Coments"],
        )

        with patch("autocad_assistance.services.dxf_jobs.generate_dxf_ezdxf") as generate:
            with self.assertRaisesRegex(ValueError, "non-finite coordinate 'Y'"):
                render_dxf_bytes(frame)
            generate.assert_not_called()

    def test_render_dxf_bytes_cleans_partial_job_on_generation_error(self):
        with tempfile.TemporaryDirectory() as jobs_root:
            root = Path(jobs_root)

            def fake_generate(_frame, output_path, scale_factor=1.0, tin_settings=None):
                del scale_factor, tin_settings
                Path(output_path).write_bytes(b"partial")
                raise RuntimeError("boom")

            with patch("autocad_assistance.services.dxf_jobs.generate_dxf_ezdxf", new=fake_generate):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    render_dxf_bytes(_mapped_rows(), jobs_root=root)

            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
