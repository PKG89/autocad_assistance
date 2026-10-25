"""Bounded, exact DXF inventory and diagnostic comparison.

No coordinate tolerance or geodetic acceptance decision is implied by an
exact mismatch. Unsupported entities remain visible in the report.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from io import BytesIO
import json
import math
from typing import Any

import ezdxf.recover


MAX_DXF_BYTES = 25 * 1024 * 1024
MAX_ENTITIES = 100_000
MAX_VERTICES = 500_000
MAX_TEXT_CHARS = 1024
MAX_EXAMPLES = 100
LINE_TYPES = frozenset({"LINE", "LWPOLYLINE", "POLYLINE", "3DFACE"})


class DxfCompareInvalidError(ValueError):
    """DXF content cannot be compared safely."""


class DxfCompareLimitError(ValueError):
    """DXF exceeds diagnostic bounds."""


def _number(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DxfCompareInvalidError("DXF number is invalid") from exc
    if not math.isfinite(number):
        raise DxfCompareInvalidError("DXF number is not finite")
    return 0.0 if number == 0 else number


def _point(value: Any) -> tuple[float, float, float]:
    try:
        return (_number(value[0]), _number(value[1]),
                _number(value[2]) if len(value) > 2 else 0.0)
    except (IndexError, TypeError) as exc:
        raise DxfCompareInvalidError("DXF vertex is invalid") from exc


def _text(value: object, *, limit: int = MAX_TEXT_CHARS) -> str:
    if not isinstance(value, str) or len(value) > limit or any(
        ord(char) < 32 and char not in "\n\t" for char in value
    ):
        raise DxfCompareInvalidError("DXF text is invalid or too long")
    return value


def _key(item: dict) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def inventory(raw: bytes) -> dict:
    """Extract supported model-space records without expanding block contents."""
    if not isinstance(raw, bytes) or not raw:
        raise DxfCompareInvalidError("DXF is empty")
    if len(raw) > MAX_DXF_BYTES:
        raise DxfCompareLimitError("DXF exceeds 25 MiB")
    try:
        drawing, audit = ezdxf.recover.read(BytesIO(raw))
        if audit.has_errors:
            raise DxfCompareInvalidError("DXF audit failed")
    except DxfCompareInvalidError:
        raise
    except Exception as exc:
        raise DxfCompareInvalidError("DXF is invalid") from exc

    records: list[dict] = []
    by_type: Counter[str] = Counter()
    by_layer: Counter[str] = Counter()
    unsupported: Counter[str] = Counter()
    vertices = 0
    entities = 0

    def points(values: Any) -> list[tuple[float, float, float]]:
        nonlocal vertices
        output = []
        for value in values:
            vertices += 1
            if vertices > MAX_VERTICES:
                raise DxfCompareLimitError("DXF has too many vertices")
            output.append(_point(value))
        return output

    try:
        for entity in drawing.modelspace():
            entities += 1
            if entities > MAX_ENTITIES:
                raise DxfCompareLimitError("DXF has too many model-space entities")
            kind = entity.dxftype()
            layer = _text(entity.dxf.get("layer", "0"), limit=256)
            by_type[kind] += 1
            by_layer[layer] += 1
            record: dict[str, Any] = {"type": kind, "layer": layer}
            if kind == "POINT":
                record["point"] = _point(entity.dxf.location)
            elif kind == "LINE":
                endpoints = points((entity.dxf.start, entity.dxf.end))
                record["points"] = sorted(endpoints)
            elif kind == "LWPOLYLINE":
                if entity.has_arc:
                    unsupported["LWPOLYLINE_BULGE"] += 1
                    continue
                elevation = _number(entity.dxf.get("elevation", 0))
                record["points"] = points((x, y, elevation) for x, y in entity.get_points("xy"))
                record["closed"] = bool(entity.closed)
            elif kind == "POLYLINE":
                if entity.has_arc or entity.dxf.get("flags", 0) & (2 | 4 | 16 | 64):
                    unsupported["POLYLINE_CURVE_OR_MESH"] += 1
                    continue
                record["points"] = points(vertex.dxf.location for vertex in entity.vertices)
                record["closed"] = bool(entity.is_closed)
            elif kind == "3DFACE":
                shape = points(entity.dxf.get(f"vtx{i}") for i in range(4))
                record["points"] = shape[:3] if shape[2] == shape[3] else shape
            elif kind == "INSERT":
                if entity.attribs:
                    unsupported["INSERT_WITH_ATTRIBS"] += 1
                    continue
                record["point"] = _point(entity.dxf.insert)
                record["name"] = _text(entity.dxf.name, limit=256)
                record["rotation"] = _number(entity.dxf.get("rotation", 0)) % 360
                record["scale"] = [_number(entity.dxf.get(axis, 1))
                                   for axis in ("xscale", "yscale", "zscale")]
                unsupported["BLOCK_CONTENTS_NOT_COMPARED"] += 1
            elif kind in {"TEXT", "MTEXT"}:
                record["point"] = _point(entity.dxf.insert)
                record["text"] = _text(entity.plain_text() if kind == "MTEXT" else entity.dxf.text)
                rotation = entity.get_rotation() if kind == "MTEXT" else entity.dxf.get("rotation", 0)
                record["rotation"] = _number(rotation) % 360
            else:
                unsupported[kind] += 1
                continue
            records.append(record)
    except (DxfCompareLimitError, DxfCompareInvalidError):
        raise
    except Exception as exc:
        raise DxfCompareInvalidError("DXF model space is invalid") from exc
    return {
        "records": records, "totalEntities": entities, "supportedEntities": len(records),
        "vertices": vertices, "byType": dict(sorted(by_type.items())),
        "byLayer": dict(sorted(by_layer.items())),
        "unsupported": dict(sorted(unsupported.items())),
    }


def _pair_key(record: dict) -> tuple:
    kind = record["type"]
    if kind in {"INSERT", "TEXT", "MTEXT", "POINT"}:
        return (kind, tuple(record["point"]))
    if kind in LINE_TYPES:
        return (kind, tuple(record["points"][0]) if record["points"] else None)
    return (kind, None)


def _example(record: dict) -> dict:
    view = dict(record)
    if "points" in view:
        shape = view["points"]
        view["pointCount"] = len(shape)
        if len(shape) > 16:
            view["points"] = shape[:8] + shape[-8:]
            view["pointsTruncated"] = True
    return view


def compare_dxf(reference_raw: bytes, result_raw: bytes) -> dict:
    """Compare supported records exactly; leave unsupported content explicit."""
    reference = inventory(reference_raw)
    result = inventory(result_raw)
    ref_records = reference.pop("records")
    out_records = result.pop("records")
    ref_groups: dict[str, list[dict]] = defaultdict(list)
    out_groups: dict[str, list[dict]] = defaultdict(list)
    for record in ref_records:
        ref_groups[_key(record)].append(record)
    for record in out_records:
        out_groups[_key(record)].append(record)
    exact = 0
    for key in ref_groups.keys() & out_groups.keys():
        matched = min(len(ref_groups[key]), len(out_groups[key]))
        exact += matched
        del ref_groups[key][:matched]
        del out_groups[key][:matched]

    remaining_reference = [record for group in ref_groups.values() for record in group]
    remaining_result = [record for group in out_groups.values() for record in group]
    by_anchor_ref: dict[tuple, list[dict]] = defaultdict(list)
    by_anchor_out: dict[tuple, list[dict]] = defaultdict(list)
    for record in remaining_reference:
        by_anchor_ref[_pair_key(record)].append(record)
    for record in remaining_result:
        by_anchor_out[_pair_key(record)].append(record)

    metrics = Counter({key: 0 for key in (
        "exactMatches", "pairedDiscrepancies", "missing", "extra",
        "wrongBlockNames", "wrongRotations", "wrongScales",
        "wrongLayers", "wrongLabels", "wrongLines",
    )})
    metrics["exactMatches"] = exact
    examples: dict[str, list[dict]] = {key: [] for key in metrics if key != "exactMatches"}

    def note(category: str, expected: dict | None, actual: dict | None) -> None:
        metrics[category] += 1
        if len(examples[category]) < MAX_EXAMPLES:
            examples[category].append({"expected": _example(expected) if expected else None,
                                       "actual": _example(actual) if actual else None})

    for anchor in sorted(by_anchor_ref.keys() | by_anchor_out.keys(), key=str):
        expected = sorted(by_anchor_ref[anchor], key=_key)
        actual = sorted(by_anchor_out[anchor], key=_key)
        paired = min(len(expected), len(actual))
        for left, right in zip(expected[:paired], actual[:paired]):
            note("pairedDiscrepancies", left, right)
            if left["layer"] != right["layer"]:
                note("wrongLayers", left, right)
            kind = left["type"]
            if kind == "INSERT":
                if left["name"] != right["name"]:
                    note("wrongBlockNames", left, right)
                if left["rotation"] != right["rotation"]:
                    note("wrongRotations", left, right)
                if left["scale"] != right["scale"]:
                    note("wrongScales", left, right)
            elif kind in {"TEXT", "MTEXT"}:
                if left["text"] != right["text"]:
                    note("wrongLabels", left, right)
                if left["rotation"] != right["rotation"]:
                    note("wrongRotations", left, right)
            elif kind in LINE_TYPES and (
                left["points"] != right["points"] or left.get("closed") != right.get("closed")
            ):
                note("wrongLines", left, right)
        for left in expected[paired:]:
            note("missing", left, None)
        for right in actual[paired:]:
            note("extra", None, right)

    return {
        "version": "exact-dxf-v1", "comparisonMode": "exact_numeric_no_geodetic_tolerance",
        "complete": not reference["unsupported"] and not result["unsupported"],
        "reference": reference, "result": result,
        "metrics": dict(metrics), "examples": examples,
    }
