"""Read-only A/B sequences for accepted line codes in an immutable survey."""

from __future__ import annotations

import csv
import json
import math

from autocad_assistance.dxf_generator.polylines import (
    order_polyline_pairs, polyline_group_key,
)
from autocad_assistance.services.project_store import ProjectNotFoundError, ProjectStore
from autocad_assistance.services.survey_contract import SurveyContext, build_survey_dataset


CANDIDATE_VERSION = "geoai-line-candidates-v1"
MAX_GROUPS = 200
MAX_GROUP_POINTS = 500
MAX_TOTAL_POINTS = 5_000


class LineCandidateLimitError(ValueError):
    """Bounded comparison would exceed its configured budget."""


class LineCandidateInvalidError(ValueError):
    """Revision source or settings cannot produce a safe comparison."""


def _candidate(records, *, label: str, survey_indexes: tuple[int, ...]) -> dict:
    vertices = [{
        "pointId": record.point_id,
        "rowIndex": record.source_row_index,
        "xyz": [record.x_text, record.y_text, record.z_text],
    } for record in records]
    try:
        length = math.fsum(math.hypot(float(right.x - left.x), float(right.y - left.y))
                           for left, right in zip(records, records[1:]))
    except (OverflowError, ValueError) as exc:
        raise LineCandidateInvalidError("Candidate length is not finite") from exc
    if not math.isfinite(length):
        raise LineCandidateInvalidError("Candidate length is not finite")
    order = tuple(record.source_row_index for record in records)
    return {
        "label": label, "pointIds": [record.point_id for record in records],
        "rowIndexes": list(order), "vertices": vertices,
        "segmentCount": len(records) - 1, "length2D": length,
        "reorderedPositions": sum(a != b for a, b in zip(order, survey_indexes)),
        "reasons": ["RECORDED_SURVEY_ORDER" if label == "A" else "EXISTING_ANCHORED_NEAREST_NEIGHBOR"],
    }


def build_line_candidates(store: ProjectStore, owner_id: str, project_id: str, revision_id: str) -> dict:
    """Compare orders without changing revisions, jobs, decisions or DXF."""

    store.assert_project_owner(owner_id, project_id)
    revision = store.assert_revision_owner(owner_id, revision_id)
    if revision.project_id != project_id:
        raise ProjectNotFoundError(revision_id)
    if revision.source_format not in {"txt", "csv"}:
        raise LineCandidateInvalidError("Only mapped TXT/CSV revisions have line candidates")
    raw = store.read_source_for(owner_id, project_id, revision_id)
    try:
        settings = json.loads(revision.settings_json)
        mapping = settings["renderSettings"]["mapping"]
        if not isinstance(mapping, dict):
            raise ValueError("Mapping is invalid")
        context = SurveyContext(
            coordinate_system=settings.get("coordinateSystem"),
            horizontal_unit=settings.get("horizontalUnit"),
            vertical_unit=settings.get("verticalUnit"),
            scale_factor=settings["scaleFactor"],
        )
        dataset = build_survey_dataset(raw, mapping, context=context)
    except (KeyError, TypeError, ValueError, OverflowError, csv.Error) as exc:
        raise LineCandidateInvalidError("Revision settings or source are invalid") from exc

    groups: dict[str, list] = {}
    total = 0
    for record in dataset.records:
        key = polyline_group_key(record.code)
        if key is None:
            continue
        if key not in groups and len(groups) >= MAX_GROUPS:
            raise LineCandidateLimitError("Too many line groups")
        group = groups.setdefault(key, [])
        group.append(record)
        total += 1
        if len(group) > MAX_GROUP_POINTS or total > MAX_TOTAL_POINTS:
            raise LineCandidateLimitError("Too many line points")

    results = []
    for code, records in groups.items():
        ids = [record.point_id.strip() for record in records]
        reasons = []
        if len(records) < 2:
            reasons.append("TOO_FEW_POINTS")
        if not all(ids):
            reasons.append("EMPTY_POINT_ID")
        if len(set(ids)) != len(ids):
            reasons.append("DUPLICATE_POINT_ID")
        if reasons:
            results.append({"groupCode": code, "status": "needs_review",
                            "pointCount": len(records), "reasons": reasons, "candidates": []})
            continue
        ordered = sorted(records, key=lambda record: record.source_row_index)
        pairs = [(record.source_row_index,
                  (float(record.x), float(record.y), float(record.z), record))
                 for record in ordered]
        current = [entry[1][3] for entry in order_polyline_pairs(pairs)]
        survey_indexes = tuple(record.source_row_index for record in ordered)
        option_a = _candidate(ordered, label="A", survey_indexes=survey_indexes)
        option_b = _candidate(current, label="B", survey_indexes=survey_indexes)
        results.append({
            "groupCode": code, "status": "proposals", "pointCount": len(records),
            "sameOrder": option_a["rowIndexes"] == option_b["rowIndexes"],
            "reasons": ["REVIEW_REQUIRED"], "candidates": [option_a, option_b],
        })

    return {
        "projectId": project_id, "revisionId": revision_id,
        "sourceSha256": revision.source_sha256,
        "settingsSha256": revision.settings_sha256,
        "generatorVersion": revision.algorithm_version,
        "candidateVersion": CANDIDATE_VERSION,
        "coordinateSystem": context.coordinate_system,
        "horizontalUnit": context.horizontal_unit,
        "verticalUnit": context.vertical_unit,
        "groupCount": len(results), "eligiblePointCount": total,
        "groups": results,
    }
