"""Bounded, offline line alternatives from explicit synthetic annotations.

No raw field code is treated as a confirmed boundary. No result is written
to a project, job or DXF; the no-end alternatives always require review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence
import unicodedata

from autocad_assistance.services.field_code_profile import (
    PROFILE_SHA256, PROFILE_VERSION, load_profile, parse_code,
)
from autocad_assistance.services.survey_contract import SurveyDataset, SurveyRecord


TRACE_VERSION = "geoai-coded-trace-candidates-v1"
ANNOTATION_VERSION = "geoai-trace-annotation-v1"
MAX_OBJECTS = 200
MAX_OBJECT_POINTS = 500
MAX_TOTAL_POINTS = 5_000
Mode = Literal["explicit_end", "no_end_review"]


class CodedTraceInvalid(ValueError):
    """Inputs are outside the bounded synthetic tracing contract."""


class CodedTraceLimit(ValueError):
    """The bounded candidate report would exceed its resource budget."""


@dataclass(frozen=True)
class TraceAnnotation:
    row_index: int
    object_id: str | None
    receiver_id: str | None = None
    order_key: int | None = None
    action: Literal["start", "continue", "end"] | None = None


def _label(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 128 or not value.strip() or value != value.strip():
        raise CodedTraceInvalid("Object and receiver IDs must be exact nonempty text of at most 128 characters")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise CodedTraceInvalid("Object or receiver ID contains a control character")
    return value


def _vertex(record: SurveyRecord) -> dict:
    return {"pointId": record.point_id, "rowIndex": record.source_row_index,
            "xyz": [record.x_text, record.y_text, record.z_text],
            "rawCode": record.code}


def _edge(left: SurveyRecord, right: SurveyRecord, *, object_id: str,
          mode: Mode, candidate: str, reason: str) -> dict:
    return {"objectId": object_id, "from": _vertex(left), "to": _vertex(right),
            "profileVersion": PROFILE_VERSION, "profileSha256": PROFILE_SHA256,
            "mode": mode, "candidate": candidate, "reason": reason}


def _duplicates(records: list[tuple[SurveyRecord, TraceAnnotation]]) -> list[str]:
    ids = [record.point_id for record, _ in records]
    reasons = []
    if any(not item.strip() for item in ids):
        reasons.append("EMPTY_POINT_ID")
    if len(set(ids)) != len(ids):
        reasons.append("DUPLICATE_POINT_ID")
    return reasons


def _explicit(object_id: str, records: list[tuple[SurveyRecord, TraceAnnotation]]) -> dict:
    reasons = _duplicates(records)
    keys = [annotation.order_key for _, annotation in records]
    if any(type(key) is not int or key < 0 or key > 1_000_000_000 for key in keys):
        reasons.append("ORDER_KEY_MISSING_OR_INVALID")
    elif len(set(keys)) != len(keys):
        reasons.append("DUPLICATE_ORDER_KEY")
    if any(annotation.action not in {"start", "continue", "end"}
           for _, annotation in records):
        reasons.append("ACTION_MISSING_OR_INVALID")
    if reasons:
        return {"objectId": object_id, "status": "needs_review",
                "reasons": reasons, "candidates": []}

    ordered = sorted(records, key=lambda pair: pair[1].order_key)
    edges = []
    active: SurveyRecord | None = None
    chains = 0
    for record, annotation in ordered:
        action = annotation.action
        if action == "start":
            if active is not None:
                reasons.append("REPEATED_START")
                break
            active = record
            chains += 1
        elif active is None:
            reasons.append("ORPHAN_END" if action == "end" else "ORPHAN_CONTINUE")
            break
        else:
            edges.append(_edge(active, record, object_id=object_id,
                               mode="explicit_end", candidate="confirmed",
                               reason="EXPLICIT_ANNOTATION_ACTION_AND_ORDER"))
            active = None if action == "end" else record
    if not reasons and active is not None:
        reasons.append("UNFINISHED_CHAIN")
    if reasons:
        return {"objectId": object_id, "status": "needs_review",
                "reasons": reasons, "candidates": []}
    return {"objectId": object_id, "status": "explicit_candidate",
            "reasons": ["SYNTHETIC_ANNOTATIONS_ONLY"],
            "candidates": [{"label": "confirmed", "chainCount": chains, "edges": edges}]}


def _no_end(object_id: str, records: list[tuple[SurveyRecord, TraceAnnotation]]) -> dict:
    reasons = _duplicates(records)
    if reasons:
        return {"objectId": object_id, "status": "needs_review",
                "reasons": reasons, "candidates": []}
    ordered = sorted(records, key=lambda pair: pair[0].source_row_index)
    source = [record for record, _ in ordered]
    all_edges = [_edge(left, right, object_id=object_id,
                       mode="no_end_review", candidate="source_order",
                       reason="RECORDED_SOURCE_ROW_ORDER_REVIEW_ONLY")
                 for left, right in zip(source, source[1:])]
    candidates = [{"label": "source_order", "edges": all_edges}]
    if all(annotation.receiver_id is not None for _, annotation in ordered):
        by_receiver: dict[str, list[SurveyRecord]] = {}
        for record, annotation in ordered:
            by_receiver.setdefault(annotation.receiver_id, []).append(record)
        receiver_edges = []
        for receiver_id in sorted(by_receiver):
            chain = by_receiver[receiver_id]
            receiver_edges.extend(
                _edge(left, right, object_id=object_id,
                      mode="no_end_review", candidate="per_receiver",
                      reason="SAME_RECEIVER_SOURCE_ROW_ORDER_REVIEW_ONLY")
                for left, right in zip(chain, chain[1:])
            )
        candidates.append({"label": "per_receiver", "edges": receiver_edges})
    else:
        reasons.append("RECEIVER_ID_MISSING")
    return {"objectId": object_id, "status": "needs_review",
            "reasons": ["END_NOT_OBSERVED", *reasons], "candidates": candidates}


def build_coded_trace_candidates(dataset: SurveyDataset,
                                 annotations: Sequence[TraceAnnotation],
                                 *, mode: Mode) -> dict:
    """Build explainable alternatives without mutating source or choosing a DXF."""
    if mode not in ("explicit_end", "no_end_review"):
        raise CodedTraceInvalid("Tracing mode is unsupported")
    if len(dataset.records) > MAX_TOTAL_POINTS or len(annotations) > MAX_TOTAL_POINTS:
        raise CodedTraceLimit("Too many survey or annotated points")
    by_row = {record.source_row_index: record for record in dataset.records}
    if len(by_row) != len(dataset.records):
        raise CodedTraceInvalid("Survey row indices are not unique")
    groups: dict[str, list[tuple[SurveyRecord, TraceAnnotation]]] = {}
    diagnostics = []
    code_diagnostics = []
    seen_rows = set()
    profile = load_profile()
    for annotation in annotations:
        if not isinstance(annotation, TraceAnnotation):
            raise CodedTraceInvalid("Annotation has the wrong shape")
        row = annotation.row_index
        if type(row) is not int or row not in by_row or row in seen_rows:
            raise CodedTraceInvalid("Annotation row is missing or repeated")
        if mode == "no_end_review" and (annotation.action is not None or annotation.order_key is not None):
            raise CodedTraceInvalid("No-end mode does not accept boundary actions or order keys")
        seen_rows.add(row)
        record = by_row[row]
        parsed = parse_code(profile, record.code)
        if parsed["diagnostics"]:
            code_diagnostics.append({"rowIndex": row,
                                     "rawCode": record.code,
                                     "diagnostics": parsed["diagnostics"]})
        object_id = _label(annotation.object_id)
        _label(annotation.receiver_id)
        if object_id is None:
            diagnostics.append({"code": "OBJECT_ID_MISSING", "rowIndex": row})
            continue
        if object_id not in groups and len(groups) >= MAX_OBJECTS:
            raise CodedTraceLimit("Too many line objects")
        group = groups.setdefault(object_id, [])
        group.append((record, annotation))
        if len(group) > MAX_OBJECT_POINTS:
            raise CodedTraceLimit("Too many points in one line object")
    results = []
    for object_id, records in groups.items():
        result = (_explicit(object_id, records) if mode == "explicit_end"
                  else _no_end(object_id, records))
        result["annotations"] = [
            {"rowIndex": record.source_row_index, "receiverId": annotation.receiver_id,
             "orderKey": annotation.order_key, "action": annotation.action}
            for record, annotation in sorted(records, key=lambda pair: pair[0].source_row_index)
        ]
        results.append(result)
    return {"traceVersion": TRACE_VERSION, "profileVersion": PROFILE_VERSION,
            "profileSha256": PROFILE_SHA256,
            "annotationVersion": ANNOTATION_VERSION,
            "annotationSource": "caller-supplied-synthetic",
            "sourceSha256": dataset.source_sha256,
            "mode": mode, "objectCount": len(results),
            "annotatedPointCount": len(annotations), "diagnostics": diagnostics,
            "codeDiagnostics": code_diagnostics,
            "groups": results}
