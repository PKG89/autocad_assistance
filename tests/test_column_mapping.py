"""Focused unit tests for explicit survey column mapping."""

from __future__ import annotations

import unittest

from autocad_assistance.services.column_mapping import (
    MappingValidationError,
    map_survey_rows,
)


class ColumnMappingTests(unittest.TestCase):
    def test_maps_rows_without_mutating_source(self):
        rows = [
            ["P1", "100", "200", "10", "G", "note"],
            ["P2", "110", "210", "11", "G2", ""],
        ]
        mapping = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4, "Comments": 5}
        original_rows = [row[:] for row in rows]

        result = map_survey_rows(rows, mapping)

        self.assertEqual(rows, original_rows)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(
            result.rows[0],
            {
                "Point": "P1",
                "X": "100",
                "Y": "200",
                "Z": "10",
                "Code": "G",
                "Comments": "note",
            },
        )

    def test_maps_absent_code_cell_to_empty_string(self):
        rows = [["P1", "1", "2", "3"], ["P2", "4", "5", "6", "C2"]]
        mapping = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}

        result = map_survey_rows(rows, mapping)

        self.assertEqual(result.rows[0]["Code"], "")
        self.assertIsNone(result.rows[0]["Comments"])

    def test_comments_absent_cell_returns_none(self):
        rows = [["P1", "1", "2", "3", "C"], ["P2", "4", "5", "6", "C2", "comment"]]
        mapping = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4, "Comments": 5}

        result = map_survey_rows(rows, mapping)

        self.assertIsNone(result.rows[0]["Comments"])

    def test_rejects_missing_required_mapping_keys(self):
        with self.assertRaises(MappingValidationError) as ctx:
            map_survey_rows([["P1", "1", "2", "3", "C"]], {"Point": 0, "X": 1, "Y": 2, "Z": 3})

        self.assertEqual(ctx.exception.code, "INVALID_COLUMN_MAPPING")

    def test_rejects_duplicate_indices(self):
        with self.assertRaises(MappingValidationError) as ctx:
            map_survey_rows(
                [["P1", "1", "2", "3", "C"]],
                {"Point": 0, "X": 1, "Y": 1, "Z": 3, "Code": 4},
            )

        self.assertEqual(ctx.exception.code, "INVALID_COLUMN_MAPPING")

    def test_rejects_bool_index(self):
        with self.assertRaises(MappingValidationError) as ctx:
            map_survey_rows(
                [["P1", "1", "2", "3", "C"]],
                {"Point": 0, "X": True, "Y": 2, "Z": 3, "Code": 4},
            )

        self.assertEqual(ctx.exception.code, "INVALID_COLUMN_MAPPING")

    def test_rejects_out_of_range_mapping_index(self):
        with self.assertRaises(MappingValidationError) as ctx:
            map_survey_rows(
                [["P1", "1", "2", "3", "C"]],
                {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 99},
            )

        self.assertEqual(ctx.exception.code, "INVALID_COLUMN_MAPPING")

    def test_rejects_row_missing_required_selected_field(self):
        rows = [["P1", "1", "2", "3", "C"], ["P2", "10", "20"]]
        mapping = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}

        with self.assertRaises(MappingValidationError) as ctx:
            map_survey_rows(rows, mapping)

        self.assertEqual(ctx.exception.code, "INVALID_COLUMN_MAPPING")

    def test_rejects_invalid_coordinate_values(self):
        bad_rows = [
            [["P1", "", "2", "3", "C"]],
            [["P1", "abc", "2", "3", "C"]],
            [["P1", "nan", "2", "3", "C"]],
            [["P1", "inf", "2", "3", "C"]],
        ]
        mapping = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}

        for rows in bad_rows:
            with self.assertRaises(MappingValidationError) as ctx:
                map_survey_rows(rows, mapping)
            self.assertEqual(ctx.exception.code, "INVALID_COORDINATE")

    def test_preserves_explicit_axis_selection_order(self):
        rows = [["P1", "100", "200", "300", "C"]]
        mapping = {"Point": 0, "X": 2, "Y": 1, "Z": 3, "Code": 4}

        result = map_survey_rows(rows, mapping)

        self.assertEqual(result.rows[0]["X"], "200")
        self.assertEqual(result.rows[0]["Y"], "100")


if __name__ == "__main__":
    unittest.main()
