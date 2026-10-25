"""Offline, review-only line tracing experiment over immutable row IDs."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Sequence

from autocad_assistance.dxf_generator.polylines import order_polyline_pairs


MAX_POINTS = 100
MAX_CONTEXT_LINES = 10
MAX_CONTEXT_POINTS = 100
MAX_UNCROSSINGS = 100


class TraceInvalidError(ValueError):
    """Input cannot represent one finite, unambiguous synthetic line."""


class TraceLimitError(ValueError):
    """Experimental tracing work exceeds a fixed bound."""


@dataclass(frozen=True)
class TracePoint:
    row_index: int
    x: float
    y: float
    z: float = 0.0


def _point(value: Sequence[object]) -> TracePoint:
    if not isinstance(value, (tuple, list)) or len(value) not in {3, 4}:
        raise TraceInvalidError("Point must contain row ID and XY or XYZ")
    row = value[0]
    if type(row) is not int or row < 1:
        raise TraceInvalidError("Row ID must be a positive integer")
    try:
        x, y = float(value[1]), float(value[2])
        z = float(value[3]) if len(value) == 4 else 0.0
    except (TypeError, ValueError, OverflowError) as exc:
        raise TraceInvalidError("Point coordinate is invalid") from exc
    if not all(math.isfinite(number) for number in (x, y, z)):
        raise TraceInvalidError("Point coordinate is not finite")
    return TracePoint(row, x, y, z)


def _validate(values: Sequence[Sequence[object]]) -> list[TracePoint]:
    if not isinstance(values, (tuple, list)) or len(values) < 2:
        raise TraceInvalidError("Line needs at least two points")
    if len(values) > MAX_POINTS:
        raise TraceLimitError("Line has too many points")
    points = [_point(value) for value in values]
    if len({point.row_index for point in points}) != len(points):
        raise TraceInvalidError("Row IDs must be unique")
    return sorted(points, key=lambda point: point.row_index)


def _orientation(a: TracePoint, b: TracePoint, c: TracePoint) -> float:
    value = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
    if not math.isfinite(value):
        raise TraceInvalidError("Geometry arithmetic is not finite")
    return value


def _crosses(a: TracePoint, b: TracePoint, c: TracePoint, d: TracePoint) -> bool:
    first = _orientation(a, b, c) * _orientation(a, b, d)
    second = _orientation(c, d, a) * _orientation(c, d, b)
    if not math.isfinite(first) or not math.isfinite(second):
        raise TraceInvalidError("Geometry arithmetic is not finite")
    return first < 0 and second < 0


def _self_crossings(order: list[TracePoint]) -> int:
    return sum(_crosses(order[i], order[i + 1], order[j], order[j + 1])
               for i in range(len(order) - 1)
               for j in range(i + 2, len(order) - 1))


def _uncross(order: list[TracePoint]) -> tuple[list[TracePoint], int, bool]:
    candidate = list(order)
    changes = 0
    while changes < MAX_UNCROSSINGS:
        found = False
        for i in range(len(candidate) - 1):
            for j in range(i + 2, len(candidate) - 1):
                if _crosses(candidate[i], candidate[i + 1], candidate[j], candidate[j + 1]):
                    candidate[i + 1:j + 1] = reversed(candidate[i + 1:j + 1])
                    changes += 1
                    found = True
                    break
            if found:
                break
        if not found:
            return candidate, changes, False
    return candidate, changes, _self_crossings(candidate) > 0


def _context_lines(lines: Sequence[Sequence[Sequence[object]]]) -> list[list[TracePoint]]:
    if not isinstance(lines, (tuple, list)) or len(lines) > MAX_CONTEXT_LINES:
        raise TraceLimitError("Too many surrounding lines")
    converted = []
    for line in lines:
        if not isinstance(line, (tuple, list)) or len(line) > MAX_CONTEXT_POINTS:
            raise TraceLimitError("Surrounding line is too large")
        if len(line) < 2:
            raise TraceInvalidError("Surrounding line needs two points")
        converted.append([_point(value) for value in line])
    return converted


def _diagnostics(order: list[TracePoint], context: list[list[TracePoint]]) -> dict:
    edges = []
    for left, right in zip(order, order[1:]):
        length = math.hypot(right.x - left.x, right.y - left.y)
        if not math.isfinite(length):
            raise TraceInvalidError("Line length is not finite")
        edges.append((left, right, length))
    positive = [length for _, _, length in edges if length > 0]
    typical = median(positive) if positive else None
    gaps = []
    for left, right, length in edges:
        ratio = length / typical if typical else None
        if ratio is not None and not math.isfinite(ratio):
            raise TraceInvalidError("Gap ratio is not finite")
        gaps.append({"fromRow": left.row_index, "toRow": right.row_index,
                     "length2D": length, "ratioToMedian": ratio})
    gaps.sort(key=lambda gap: (-gap["length2D"], gap["fromRow"], gap["toRow"]))
    reversals = 0
    for left, middle, right in zip(order, order[1:], order[2:]):
        dot = (middle.x - left.x) * (right.x - middle.x) + (
            middle.y - left.y) * (right.y - middle.y)
        if not math.isfinite(dot):
            raise TraceInvalidError("Turn arithmetic is not finite")
        reversals += dot < 0
    nearby = sum(_crosses(left, right, outer_left, outer_right)
                 for left, right, _ in edges for line in context
                 for outer_left, outer_right in zip(line, line[1:]))
    try:
        total_length = math.fsum(length for _, _, length in edges)
    except OverflowError as exc:
        raise TraceInvalidError("Line length is not finite") from exc
    if not math.isfinite(total_length):
        raise TraceInvalidError("Line length is not finite")
    return {"rowIndexes": [point.row_index for point in order],
            "length2D": total_length,
            "selfCrossings": _self_crossings(order), "turnReversals": reversals,
            "environmentCrossings": nearby, "rankedGaps": gaps[:10]}


def experiment(values: Sequence[Sequence[object]],
               context_lines: Sequence[Sequence[Sequence[object]]] = ()) -> dict:
    """Return source, current baseline and experimental suggestions without writes."""
    points = _validate(values)
    context = _context_lines(context_lines)
    baseline_pairs = order_polyline_pairs([
        (point.row_index, (point.x, point.y, point.z, point)) for point in points
    ])
    baseline = [item[1][3] for item in baseline_pairs]
    candidate, reversals, incomplete = _uncross(baseline)
    return {
        "version": "geoai-trace-experiment-v1", "reviewOnly": True,
        "allRowIndexes": [point.row_index for point in points],
        "uncrossingReversals": reversals, "candidateIncomplete": incomplete,
        "sourceOrder": _diagnostics(points, context),
        "legacyNearest": _diagnostics(baseline, context),
        "candidateUncrossed": _diagnostics(candidate, context),
    }
