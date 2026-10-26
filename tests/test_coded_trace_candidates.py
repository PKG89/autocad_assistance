"""Offline synthetic checks for explicit boundaries and no-end alternatives."""

from dataclasses import replace
from hashlib import sha256
from unittest.mock import patch
import unittest

from autocad_assistance.services import coded_trace_candidates as trace
from autocad_assistance.services.survey_contract import SurveyContext, build_survey_dataset


MAPPING = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}
RAW = (
    b"Point,X,Y,Z,Code\n"
    b"A1,0,0,1,1\n"
    b"B1,2,-1,2,1\n"
    b"A2,1,1,3,2\n"
    b"B2,2,1,4,0\n"
    b"A3,2,0,5,0\n"
    b"A4,3,0,6,1\n"
    b"A5x,4,0,7,0\n"
)


def dataset(raw=RAW):
    return build_survey_dataset(raw, MAPPING, context=SurveyContext(
        coordinate_system="synthetic", horizontal_unit="m", vertical_unit="m"))


def explicit():
    return [
        trace.TraceAnnotation(1, "A", "r1", 10, "start"),
        trace.TraceAnnotation(2, "B", "r2", 10, "start"),
        trace.TraceAnnotation(3, "A", "r1", 20, "continue"),
        trace.TraceAnnotation(4, "B", "r2", 20, "end"),
        trace.TraceAnnotation(5, "A", "r1", 30, "end"),
        trace.TraceAnnotation(6, "A", "r2", 40, "start"),
        trace.TraceAnnotation(7, "A", "r2", 50, "end"),
    ]


def pairs(candidate):
    return [(edge["from"]["rowIndex"], edge["to"]["rowIndex"])
            for edge in candidate["edges"]]


class CodedTraceTests(unittest.TestCase):
    def test_explicit_end_interleaved_objects_and_separate_chains(self):
        source = dataset()
        before = source.records
        first = trace.build_coded_trace_candidates(source, explicit(), mode="explicit_end")
        second = trace.build_coded_trace_candidates(source, explicit(), mode="explicit_end")
        self.assertEqual(first, second)
        self.assertEqual(source.records, before)
        self.assertEqual(first["sourceSha256"], sha256(RAW).hexdigest())
        self.assertEqual(first["profileVersion"], "drawcode-explicit-v1")
        self.assertEqual(first["objectCount"], 2)
        a, b = first["groups"]
        self.assertEqual((a["objectId"], b["objectId"]), ("A", "B"))
        self.assertEqual(a["status"], "explicit_candidate")
        self.assertEqual(a["candidates"][0]["chainCount"], 2)
        self.assertEqual(pairs(a["candidates"][0]), [(1, 3), (3, 5), (6, 7)])
        self.assertEqual(pairs(b["candidates"][0]), [(2, 4)])
        self.assertEqual(a["candidates"][0]["edges"][0]["from"]["xyz"], ["0", "0", "1"])
        self.assertEqual(a["candidates"][0]["edges"][0]["reason"],
                         "EXPLICIT_ANNOTATION_ACTION_AND_ORDER")
        self.assertEqual(first["annotationSource"], "caller-supplied-synthetic")
        self.assertEqual(a["annotations"][0]["receiverId"], "r1")
        self.assertEqual(first["codeDiagnostics"][0]["diagnostics"][0]["code"],
                         "AMBIGUOUS_TOKEN")

    def test_explicit_errors_abstain_whole_object(self):
        source = dataset()
        base = explicit()
        changes = (
            (3, {"action": "start"}, "REPEATED_START"),
            (1, {"action": "end"}, "ORPHAN_END"),
            (1, {"action": "continue"}, "ORPHAN_CONTINUE"),
            (5, {"action": "continue"}, "REPEATED_START"),
            (3, {"order_key": 10}, "DUPLICATE_ORDER_KEY"),
            (3, {"order_key": None}, "ORDER_KEY_MISSING_OR_INVALID"),
            (3, {"action": None}, "ACTION_MISSING_OR_INVALID"),
        )
        for row, fields, reason in changes:
            with self.subTest(row=row, fields=fields):
                items = [replace(item, **fields) if item.row_index == row else item
                         for item in base]
                result = trace.build_coded_trace_candidates(source, items, mode="explicit_end")
                a = result["groups"][0]
                self.assertEqual(a["status"], "needs_review")
                self.assertIn(reason, a["reasons"])
                self.assertEqual(a["candidates"], [])
                self.assertEqual(pairs(result["groups"][1]["candidates"][0]), [(2, 4)])
        truncated = [item for item in base if item.row_index != 7]
        result = trace.build_coded_trace_candidates(source, truncated, mode="explicit_end")
        self.assertIn("UNFINISHED_CHAIN", result["groups"][0]["reasons"])
        self.assertEqual(result["groups"][0]["candidates"], [])

    def test_no_end_alternatives_are_review_only_and_differ_by_receiver(self):
        source = dataset()
        annotations = [trace.TraceAnnotation(row, "A", receiver)
                       for row, receiver in ((1, "r1"), (3, "r1"), (5, "r2"),
                                             (6, "r2"), (7, "r1"))]
        result = trace.build_coded_trace_candidates(source, annotations,
                                                     mode="no_end_review")
        group = result["groups"][0]
        self.assertEqual(group["status"], "needs_review")
        self.assertEqual(group["reasons"], ["END_NOT_OBSERVED"])
        self.assertEqual([item["label"] for item in group["candidates"]],
                         ["source_order", "per_receiver"])
        self.assertEqual(pairs(group["candidates"][0]),
                         [(1, 3), (3, 5), (5, 6), (6, 7)])
        self.assertEqual(pairs(group["candidates"][1]), [(1, 3), (3, 7), (5, 6)])
        missing = [replace(item, receiver_id=None) if item.row_index == 5 else item
                   for item in annotations]
        result = trace.build_coded_trace_candidates(source, missing,
                                                     mode="no_end_review")
        self.assertEqual([c["label"] for c in result["groups"][0]["candidates"]],
                         ["source_order"])
        self.assertIn("RECEIVER_ID_MISSING", result["groups"][0]["reasons"])

    def test_duplicate_and_missing_ids_limits_and_annotation_bounds(self):
        source = dataset()
        items = explicit()
        with self.assertRaises(trace.CodedTraceInvalid):
            trace.build_coded_trace_candidates(source, items + [items[0]], mode="explicit_end")
        with self.assertRaises(trace.CodedTraceInvalid):
            trace.build_coded_trace_candidates(source, [trace.TraceAnnotation(999, "A")],
                                               mode="no_end_review")
        with self.assertRaises(trace.CodedTraceInvalid):
            trace.build_coded_trace_candidates(source, items, mode="unknown")
        with self.assertRaises(trace.CodedTraceInvalid):
            trace.build_coded_trace_candidates(source,
                [replace(items[0], receiver_id="")], mode="no_end_review")
        with self.assertRaises(trace.CodedTraceInvalid):
            trace.build_coded_trace_candidates(source, [items[0]], mode="no_end_review")
        missing = [trace.TraceAnnotation(1, None, "r1")]
        result = trace.build_coded_trace_candidates(source, missing, mode="no_end_review")
        self.assertEqual(result["diagnostics"], [{"code": "OBJECT_ID_MISSING", "rowIndex": 1}])
        duplicate_raw = RAW.replace(b"A2,", b"A1,")
        dupe = trace.build_coded_trace_candidates(dataset(duplicate_raw), items,
                                                   mode="explicit_end")
        self.assertEqual(dupe["groups"][0]["reasons"], ["DUPLICATE_POINT_ID"])
        self.assertEqual(dupe["groups"][0]["candidates"], [])
        with patch.object(trace, "MAX_OBJECT_POINTS", 2):
            with self.assertRaises(trace.CodedTraceLimit):
                trace.build_coded_trace_candidates(source, items, mode="explicit_end")
        with patch.object(trace, "MAX_OBJECTS", 1):
            with self.assertRaises(trace.CodedTraceLimit):
                trace.build_coded_trace_candidates(source, items, mode="explicit_end")
        with patch.object(trace, "MAX_TOTAL_POINTS", 6):
            with self.assertRaises(trace.CodedTraceLimit):
                trace.build_coded_trace_candidates(source, items, mode="explicit_end")


if __name__ == "__main__":
    unittest.main()
