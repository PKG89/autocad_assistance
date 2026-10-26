"""Focused unit tests for the independent survey parser service."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from autocad_assistance.services.survey_parser import (
    SurveyParseError,
    parse_survey_bytes,
)


class SurveyParserTests(unittest.TestCase):
    def test_semicolon_preserves_trailing_empty_field(self):
        raw = b"A;100;200;10;ground;\n"
        result = parse_survey_bytes(raw)
        self.assertEqual(result.delimiter, ";")
        self.assertEqual(result.encoding, "utf-8-sig")
        self.assertIsNone(result.header)
        self.assertEqual(result.rows, [["A", "100", "200", "10", "ground", ""]])

    def test_delimiter_priority_tab_over_comma(self):
        raw = b"A\t100,200\t300\t10\n"
        result = parse_survey_bytes(raw)
        self.assertEqual(result.delimiter, "\t")
        self.assertEqual(result.rows[0][0], "A")
        self.assertEqual(result.rows[0][1], "100,200")

    def test_comma_pipe_and_space_delimiters(self):
        cases = [
            (b"A,100,200,10\n", ",", ["A", "100", "200", "10"]),
            (b"A|100|200|10\n", "|", ["A", "100", "200", "10"]),
            (b"A  100  200  10\n", " ", ["A", "100", "200", "10"]),
        ]
        for raw, expected_delimiter, expected_row in cases:
            with self.subTest(delimiter=repr(expected_delimiter)):
                result = parse_survey_bytes(raw)
                self.assertEqual(result.delimiter, expected_delimiter)
                self.assertEqual(result.rows, [expected_row])

    def test_space_delimiter_discards_empty_cells(self):
        raw = b"A   100  200   10  ground\n"
        result = parse_survey_bytes(raw)
        self.assertEqual(result.delimiter, " ")
        self.assertEqual(result.rows, [["A", "100", "200", "10", "ground"]])

    def test_header_point_xyz_omitted_and_returned(self):
        raw = b"Point,X,Y,Z,Code\nA,1,2,3,g\nB,4,5,6,g\n"
        result = parse_survey_bytes(raw)
        self.assertEqual(result.header, ["Point", "X", "Y", "Z", "Code"])
        self.assertEqual(
            result.rows,
            [["A", "1", "2", "3", "g"], ["B", "4", "5", "6", "g"]],
        )

    def test_header_point_yxz_case_insensitive(self):
        raw = b"point;y;x;z\nA;200;100;10\n"
        result = parse_survey_bytes(raw)
        self.assertEqual(result.header, ["point", "y", "x", "z"])
        self.assertEqual(result.rows, [["A", "200", "100", "10"]])

    def test_short_rows_skipped_order_preserved(self):
        raw = b"skip,me\nA,1,2,3\nB,4,5\nC,6,7,8,code\n"
        result = parse_survey_bytes(raw)
        self.assertEqual(
            result.rows,
            [["A", "1", "2", "3"], ["C", "6", "7", "8", "code"]],
        )

    def test_utf8_bom_accepted(self):
        raw = b"\xef\xbb\xbfA,1,2,3\n"
        result = parse_survey_bytes(raw)
        self.assertEqual(result.encoding, "utf-8-sig")
        self.assertEqual(result.rows, [["A", "1", "2", "3"]])

    def test_cp1251_fallback_when_utf8_fails(self):
        # Cyrillic point label encoded as Windows-1251 (invalid UTF-8).
        raw = "Точка;1;2;3;грунт\n".encode("cp1251")
        result = parse_survey_bytes(raw)
        self.assertNotEqual(result.encoding, "utf-8-sig")
        self.assertEqual(result.rows[0][0], "Точка")
        self.assertEqual(result.rows[0][4], "грунт")

    def test_ascii_chardet_result_maps_to_cp1251(self):
        # Invalid UTF-8 so the chardet fallback path runs; ascii -> cp1251.
        invalid_utf8 = b"A;1;2;3;\xff\n"
        with patch(
            "autocad_assistance.services.survey_parser.chardet.detect",
            return_value={"encoding": "ascii"},
        ) as detect:
            result = parse_survey_bytes(invalid_utf8)
        detect.assert_called_once_with(invalid_utf8)
        self.assertEqual(result.encoding, "cp1251")
        self.assertEqual(result.rows[0][:4], ["A", "1", "2", "3"])

    def test_unknown_chardet_encoding_raises_survey_parse_error(self):
        invalid_utf8 = b"A;1;2;3;\xff\n"
        with patch(
            "autocad_assistance.services.survey_parser.chardet.detect",
            return_value={"encoding": "not-a-real-codec"},
        ) as detect:
            with self.assertRaises(SurveyParseError) as caught:
                parse_survey_bytes(invalid_utf8)
        detect.assert_called_once_with(invalid_utf8)
        self.assertIsInstance(caught.exception.__cause__, LookupError)

    def test_empty_chardet_result_for_invalid_utf8_raises_survey_parse_error(self):
        invalid_utf8 = b"\xff\xfeA;1;2;3\n"
        with patch(
            "autocad_assistance.services.survey_parser.chardet.detect",
            return_value={},
        ) as detect:
            with self.assertRaises(SurveyParseError) as caught:
                parse_survey_bytes(invalid_utf8)
        detect.assert_called_once_with(invalid_utf8)
        self.assertIsInstance(caught.exception.__cause__, UnicodeDecodeError)

    def test_empty_or_header_only_raises_without_partial(self):
        cases = [
            b"",
            b"\n\n",
            b"Point,X,Y,Z\n",
            b"a,b,c\n",
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(SurveyParseError):
                    parse_survey_bytes(raw)


if __name__ == "__main__":
    unittest.main()
