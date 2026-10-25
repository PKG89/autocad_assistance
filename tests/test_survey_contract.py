"""Contract tests for measured survey rows and their provenance."""

from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import unittest

import pandas as pd

from autocad_assistance.bot.run import _telegram_contract_rows
from autocad_assistance.services.column_mapping import MappingValidationError
from autocad_assistance.services.survey_contract import (
    SurveyContext,
    SurveyContractError,
    build_survey_dataset,
    make_survey_dataset,
)


MAPPING = {"Point": 0, "Y": 1, "X": 2, "Z": 3, "Code": 4, "Comments": 5}


class SurveyContractTests(unittest.TestCase):
    def test_swapped_axes_and_source_lines_are_lossless(self):
        raw = (
            b"Point;Y;X;Z;Code;Comments\n"
            b"\n"
            b"short;row\n"
            b"A;200;100.000;12.500;ground;note\n"
            b"A;210;110;13;ground;\n"
            b";220;120;14;;last\n"
        )
        dataset = build_survey_dataset(raw, MAPPING)
        self.assertEqual(dataset.source_sha256, sha256(raw).hexdigest())
        self.assertEqual([r.source_line_number for r in dataset.records], [4, 5, 6])
        self.assertEqual([r.source_row_index for r in dataset.records], [1, 2, 3])
        self.assertEqual(dataset.records[0].source_cells, ("A", "200", "100.000", "12.500", "ground", "note"))
        self.assertEqual(dataset.records[0].x, Decimal("100.000"))
        self.assertEqual(dataset.records[0].y, Decimal("200"))
        self.assertEqual(dataset.records[0].z, Decimal("12.500"))
        self.assertEqual(dataset.mapped_rows[0]["X"], "100.000")
        self.assertEqual(dataset.mapped_rows[0]["Comments"], "note")
        self.assertEqual(
            [warning.code for warning in dataset.warnings],
            [
                "DUPLICATE_POINT_ID",
                "EMPTY_POINT_ID",
                "UNKNOWN_COORDINATE_SYSTEM",
                "UNKNOWN_HORIZONTAL_UNIT",
                "UNKNOWN_VERTICAL_UNIT",
            ],
        )
        self.assertEqual(dataset.records[2].point_id, "")
        self.assertEqual(len(dataset.records), 3)

    def test_unknown_height_and_nonfinite_values_fail_instead_of_zero(self):
        for value in ("", "NaN", "Inf", "-Infinity", "oops"):
            with self.subTest(value=value), self.assertRaises(MappingValidationError) as caught:
                build_survey_dataset(
                    f"A,1,2,{value},ground\n".encode(),
                    {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4},
                )
            self.assertEqual(caught.exception.code, "INVALID_COORDINATE")

    def test_local_coordinate_system_and_scale_do_not_transform_xyz(self):
        raw = b"A,100.0001,200.0002,10.0003,ground\n"
        context = SurveyContext(
            coordinate_system=" Local site grid ",
            horizontal_unit="m",
            vertical_unit="m",
            scale_factor=Decimal("500"),
        )
        dataset = build_survey_dataset(
            raw,
            {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4},
            context=context,
        )
        self.assertEqual(dataset.context.coordinate_system, "Local site grid")
        self.assertEqual(dataset.context.scale_factor, Decimal("500"))
        self.assertEqual(dataset.records[0].x_text, "100.0001")
        self.assertEqual(dataset.records[0].x, Decimal("100.0001"))
        self.assertEqual(dataset.warnings, ())

    def test_telegram_shape_can_use_the_same_contract_without_losing_comments(self):
        rows = [["P", "1", "2", "3", "code", "one", "two"]]
        mapped = [{"Point": "P", "X": "1", "Y": "2", "Z": "3", "Code": "code", "Comments": "one two"}]
        dataset = make_survey_dataset(
            mapped,
            source_rows=rows,
            source_sha256=sha256(b"P,1,2,3,code,one,two\n").hexdigest(),
        )
        self.assertEqual(dataset.records[0].source_cells, tuple(rows[0]))
        self.assertEqual(dataset.mapped_rows[0]["Comments"], "one two")

    def test_telegram_dxf_adapter_uses_source_provenance_and_current_scale(self):
        source = pd.DataFrame([["P", "1", "2", "3", "code", "one", "two"]])
        final = pd.DataFrame(
            [["P", "1", "2", "3", "code", "one two"]],
            columns=["Point", "X", "Y", "Z", "Code", "Coments"],
        )
        rows, warnings = _telegram_contract_rows(
            {
                "data_initial": source,
                "survey_source_sha256": sha256(b"P,1,2,3,code,one,two\n").hexdigest(),
                "survey_source_line_numbers": (1,),
            },
            final,
            0.5,
        )
        self.assertEqual(rows[0]["Comments"], "one two")
        self.assertEqual(rows[0]["X"], "1")
        self.assertEqual([warning.code for warning in warnings], [
            "UNKNOWN_COORDINATE_SYSTEM",
            "UNKNOWN_HORIZONTAL_UNIT",
            "UNKNOWN_VERTICAL_UNIT",
        ])
        final.loc[0, "Z"] = ""
        with self.assertRaises(SurveyContractError):
            _telegram_contract_rows(
                {
                    "data_initial": source,
                    "survey_source_sha256": sha256(b"P,1,2,3,code,one,two\n").hexdigest(),
                },
                final,
                0.5,
            )

    def test_provenance_and_context_must_be_explicitly_valid(self):
        with self.assertRaises(SurveyContractError) as caught:
            make_survey_dataset([], source_rows=[["A"]], source_sha256="0" * 64)
        self.assertEqual(caught.exception.code, "INVALID_PROVENANCE")
        with self.assertRaises(SurveyContractError):
            SurveyContext(coordinate_system=" ")
        with self.assertRaises(SurveyContractError):
            SurveyContext(scale_factor=0)
        with self.assertRaises(SurveyContractError):
            SurveyContext(scale_factor=Decimal("1e-400"))

    def test_underflow_is_not_silently_converted_to_zero_for_dxf(self):
        with self.assertRaises(SurveyContractError) as caught:
            make_survey_dataset(
                [{"Point": "A", "X": "1e-400", "Y": "2", "Z": "3", "Code": "", "Comments": None}],
                source_rows=[["A", "1e-400", "2", "3"]],
                source_sha256="0" * 64,
            )
        self.assertEqual(caught.exception.code, "INVALID_COORDINATE")
