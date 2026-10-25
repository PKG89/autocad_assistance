"""Synthetic whole-object benchmark for review-only tracing suggestions."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from autocad_assistance.services.trace_experiment import TraceInvalidError, experiment


def _edges(order: list[int]) -> set[tuple[int, int]]:
    return {tuple(sorted((left, right))) for left, right in zip(order, order[1:])}


def _score(order: list[int], truth: list[int]) -> dict:
    expected = _edges(truth)
    observed = _edges(order)
    correct = len(expected & observed)
    return {"matchedEdges": correct, "truthEdges": len(expected),
            "extraEdges": len(observed - expected),
            "missingEdges": len(expected - observed)}


def benchmark(fixture: dict) -> dict:
    if not isinstance(fixture, dict) or not all(
        isinstance(fixture.get(split), list) for split in ("development", "holdout")
    ):
        raise TraceInvalidError("Benchmark fixture is invalid")
    all_objects = fixture["development"] + fixture["holdout"]
    if not fixture["development"] or not fixture["holdout"] or len(all_objects) > 100:
        raise TraceInvalidError("Benchmark object count is invalid")
    if any(not isinstance(obj, dict) for obj in all_objects):
        raise TraceInvalidError("Benchmark object is invalid")
    ids = [obj.get("objectId") for obj in all_objects]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        raise TraceInvalidError("Object IDs must be unique")
    families = {}
    for split in ("development", "holdout"):
        for obj in fixture[split]:
            family = obj.get("objectFamilyId")
            if not isinstance(family, str) or not family:
                raise TraceInvalidError("Object family ID is required")
            if family in families and families[family] != split:
                raise TraceInvalidError("Object family crosses development/holdout split")
            families[family] = split
    coordinate_fingerprints = []
    for obj in all_objects:
        if not isinstance(obj.get("points"), list) or any(
            not isinstance(point, list) or len(point) not in {3, 4}
            for point in obj["points"]
        ):
            raise TraceInvalidError("Benchmark points are invalid")
        coordinate_fingerprints.append(tuple(sorted(
            tuple(point[1:]) for point in obj["points"]
        )))
    if len(set(coordinate_fingerprints)) != len(coordinate_fingerprints):
        raise TraceInvalidError("Object geometry appears in more than one fixture partition")

    rows = {"development": [], "holdout": []}
    per_class = defaultdict(lambda: {"objects": 0, "legacyMatchedEdges": 0,
                                    "candidateMatchedEdges": 0,
                                    "truthEdges": 0, "regressions": 0,
                                    "improvements": 0})
    for split in ("development", "holdout"):
        for obj in fixture[split]:
            label = obj.get("class")
            if not isinstance(label, str) or not label:
                raise TraceInvalidError("Object class is invalid")
            result = experiment(obj["points"])
            all_rows = result["allRowIndexes"]
            truth = obj.get("truth")
            if (not isinstance(truth, list) or len(truth) != len(all_rows)
                    or any(type(item) is not int for item in truth)
                    or sorted(truth) != all_rows):
                raise TraceInvalidError("Truth does not preserve this object's rows")
            scores = {name: _score(result[name]["rowIndexes"], truth)
                      for name in ("sourceOrder", "legacyNearest", "candidateUncrossed")}
            row = {"objectId": obj["objectId"], "objectFamilyId": obj["objectFamilyId"],
                   "class": label,
                   "truthRowIndexes": truth,
                   "sourceRowIndexes": result["sourceOrder"]["rowIndexes"],
                   "legacyRowIndexes": result["legacyNearest"]["rowIndexes"],
                   "candidateRowIndexes": result["candidateUncrossed"]["rowIndexes"],
                   "legacyCrossings": result["legacyNearest"]["selfCrossings"],
                   "candidateCrossings": result["candidateUncrossed"]["selfCrossings"],
                   "candidateIncomplete": result["candidateIncomplete"],
                   "scores": scores}
            rows[split].append(row)
            if split == "holdout":
                summary = per_class[label]
                summary["objects"] += 1
                summary["legacyMatchedEdges"] += scores["legacyNearest"]["matchedEdges"]
                summary["candidateMatchedEdges"] += scores["candidateUncrossed"]["matchedEdges"]
                summary["truthEdges"] += scores["legacyNearest"]["truthEdges"]
                before = scores["legacyNearest"]["matchedEdges"]
                after = scores["candidateUncrossed"]["matchedEdges"]
                summary["regressions"] += after < before
                summary["improvements"] += after > before
    return {"fixtureVersion": fixture.get("fixtureVersion"),
            "algorithmVersion": "geoai-trace-experiment-v1",
            "reviewOnly": True, "evidence": "synthetic_only_not_domain_validated",
            "objects": rows, "holdoutByClass": dict(sorted(per_class.items()))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline synthetic tracing benchmark")
    parser.add_argument("--fixture", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.fixture.stat().st_size > 1024 * 1024:
        parser.error("Fixture exceeds 1 MiB")
    report = benchmark(json.loads(args.fixture.read_text(encoding="utf-8")))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
