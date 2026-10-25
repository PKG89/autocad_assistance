"""Offline tracing suggestion exposes both synthetic gains and regressions."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from autocad_assistance.services.trace_benchmark import benchmark
from autocad_assistance.services.trace_experiment import (
    TraceInvalidError, TraceLimitError, experiment,
)


FIXTURE = Path(__file__).resolve().parents[1] / "harness" / "fixtures" / "030-synthetic-objects.json"


class TraceExperimentTests(unittest.TestCase):
    def test_heldout_whole_objects_show_gain_and_legitimate_crossing_regression(self):
        raw = FIXTURE.read_bytes()
        fixture = json.loads(raw)
        first = benchmark(fixture)
        second = benchmark(fixture)
        self.assertEqual(first, second)
        self.assertEqual(FIXTURE.read_bytes(), raw)
        self.assertTrue(first["reviewOnly"])
        self.assertEqual(first["evidence"], "synthetic_only_not_domain_validated")
        positive = first["holdoutByClass"]["uncrossing-helpful"]
        self.assertEqual((positive["legacyMatchedEdges"], positive["candidateMatchedEdges"]), (2, 4))
        self.assertEqual(positive["improvements"], 1)
        negative = first["holdoutByClass"]["crossing-legitimate"]
        self.assertEqual((negative["legacyMatchedEdges"], negative["candidateMatchedEdges"]), (5, 3))
        self.assertEqual(negative["regressions"], 1)
        self.assertTrue(all(item["candidateCrossings"] == 0 for item in first["objects"]["holdout"]))
        self.assertTrue({item["objectFamilyId"] for item in first["objects"]["development"]}
                        .isdisjoint({item["objectFamilyId"] for item in first["objects"]["holdout"]}))

    def test_source_xyz_context_and_gap_diagnostics_are_read_only(self):
        values = [[1, 0, 0, 10], [2, 2, 0, 20], [3, 1, 1, 30], [4, 3, 1, 40]]
        original = deepcopy(values)
        result = experiment(values, context_lines=[[[1, 1, -1], [2, 1, 2]]])
        self.assertEqual(values, original)
        self.assertEqual(result["allRowIndexes"], [1, 2, 3, 4])
        for name in ("sourceOrder", "legacyNearest", "candidateUncrossed"):
            self.assertEqual(sorted(result[name]["rowIndexes"]), [1, 2, 3, 4])
            self.assertIn("rankedGaps", result[name])
            self.assertIn("turnReversals", result[name])
            self.assertIn("environmentCrossings", result[name])
        self.assertTrue(result["reviewOnly"])

    def test_bounds_invalid_truth_and_partition_leakage(self):
        with self.assertRaises(TraceInvalidError):
            experiment([[1, 0, 0], [1, 1, 0]])
        with self.assertRaises(TraceInvalidError):
            experiment([[1, 0, 0], [2, float("nan"), 0]])
        with self.assertRaises(TraceLimitError):
            experiment([[index + 1, index, 0] for index in range(101)])
        with self.assertRaises(TraceLimitError):
            experiment([[1, 0, 0], [2, 1, 0]],
                       context_lines=[[[1, 0, 0], [2, 1, 0]]] * 11)
        fixture = json.loads(FIXTURE.read_text())
        bad_truth = deepcopy(fixture)
        bad_truth["holdout"][0]["truth"] = [1, 1, 2, 3, 4]
        with self.assertRaises(TraceInvalidError):
            benchmark(bad_truth)
        copied = deepcopy(fixture)
        copied["holdout"][0]["points"] = deepcopy(copied["development"][0]["points"])
        with self.assertRaises(TraceInvalidError):
            benchmark(copied)
        copied_family = deepcopy(fixture)
        copied_family["holdout"][0]["objectFamilyId"] = copied_family["development"][0]["objectFamilyId"]
        with self.assertRaises(TraceInvalidError):
            benchmark(copied_family)
        crossing = fixture["holdout"][0]["points"]
        with patch("autocad_assistance.services.trace_experiment.MAX_UNCROSSINGS", 0):
            limited = experiment(crossing)
        self.assertTrue(limited["candidateIncomplete"])


if __name__ == "__main__":
    unittest.main()
