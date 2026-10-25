"""Explicit, versioned line topology edits over immutable survey row IDs."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Mapping
from uuid import UUID

from autocad_assistance.services.line_candidates import build_line_candidates
from autocad_assistance.services.line_decisions import decision_snapshot_for_job
from autocad_assistance.services.project_store import (
    LineEditConflictError, LineEditRecord, ProjectNotFoundError, ProjectStore,
)


MAX_LINES = 500


class LineEditInvalidError(ValueError):
    """Requested edit does not preserve an explicit, valid line model."""


def _hash(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _base_model(store: ProjectStore, owner_id: str, project_id: str, revision_id: str) -> dict:
    comparison = build_line_candidates(store, owner_id, project_id, revision_id)
    accepted_orders, decisions = decision_snapshot_for_job(store, owner_id, project_id, revision_id)
    lines = []
    source_rows = []
    editable_codes = []
    for group in comparison["groups"]:
        if group["status"] != "proposals":
            continue
        code = group["groupCode"]
        editable_codes.append(code)
        b_order = group["candidates"][1]["rowIndexes"]
        order = accepted_orders.get(code, b_order)
        source_rows.extend(group["candidates"][0]["rowIndexes"])
        lines.append({"lineId": f"{code}:0", "groupCode": code,
                      "rowIndexes": order, "origin": "accepted" if code in accepted_orders else "legacy"})
    return {
        "revisionId": revision_id, "sourceSha256": comparison["sourceSha256"],
        "settingsSha256": comparison["settingsSha256"],
        "candidateVersion": comparison["candidateVersion"],
        "decisionFingerprint": _hash(decisions),
        "editableGroupCodes": editable_codes,
        "sourceRowIndexes": sorted(source_rows),
        "lines": lines,
    }


def _record_view(record: LineEditRecord, *, include_model: bool = False) -> dict:
    model = json.loads(record.model_json)
    view = {"eventId": record.event_id, "revisionId": record.revision_id,
            "version": record.version, "requestId": record.request_id,
            "operation": json.loads(record.operation_json)["operation"],
            "modelSha256": _hash(model), "authorId": record.author_id,
            "createdAt": record.created_at.replace(" ", "T") + "Z"}
    if include_model:
        view["model"] = model
    return view


def current_model(store: ProjectStore, owner_id: str, project_id: str, revision_id: str) -> dict:
    base = _base_model(store, owner_id, project_id, revision_id)
    latest = store.latest_line_edit_for(owner_id, revision_id)
    try:
        model = json.loads(latest.model_json) if latest is not None else base
        _validate(model)
        stale = any(model[key] != base[key] for key in (
            "revisionId", "sourceSha256", "settingsSha256", "candidateVersion", "decisionFingerprint",
            "editableGroupCodes", "sourceRowIndexes",
        ))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise LineEditInvalidError("Saved line model is invalid") from exc
    return {"projectId": project_id, "revisionId": revision_id,
            "version": latest.version if latest else 0,
            "model": model, "modelSha256": _hash(model), "staleDecisions": stale,
            "latestEvent": _record_view(latest) if latest else None}


def _line(lines: list[dict], line_id: str) -> dict:
    found = next((line for line in lines if line["lineId"] == line_id), None)
    if found is None:
        raise LineEditInvalidError("Line ID is absent from current model")
    return found


def _validate(model: dict) -> None:
    lines = model["lines"]
    if len(lines) > MAX_LINES or len({line["lineId"] for line in lines}) != len(lines):
        raise LineEditInvalidError("Line count or IDs are invalid")
    codes = set(model["editableGroupCodes"])
    expected = model["sourceRowIndexes"]
    seen = []
    for line in lines:
        rows = line["rowIndexes"]
        if (line["groupCode"] not in codes or not isinstance(rows, list) or not rows or len(rows) > 500
                or any(type(index) is not int for index in rows)):
            raise LineEditInvalidError("Line code or rows are invalid")
        seen.extend(rows)
    if len(seen) != len(expected) or sorted(seen) != expected:
        raise LineEditInvalidError("Edit must conserve unique source rows")


def _apply(model: dict, operation: Mapping[str, object], store: ProjectStore,
           owner_id: str, revision_id: str, base: dict) -> dict:
    result = deepcopy(model)
    lines = result["lines"]
    kind = operation.get("type")
    if kind == "reorder":
        line = _line(lines, operation.get("lineId"))
        order = operation.get("rowIndexes")
        if not isinstance(order, list) or len(order) != len(line["rowIndexes"]) or sorted(order) != sorted(line["rowIndexes"]):
            raise LineEditInvalidError("Reorder must permute exactly the existing vertices")
        line["rowIndexes"] = order
        line["origin"] = "edited"
    elif kind == "split":
        line = _line(lines, operation.get("lineId"))
        at = operation.get("at")
        new_id = operation.get("newLineId")
        try:
            if str(UUID(str(new_id))) != new_id:
                raise ValueError()
        except (ValueError, TypeError) as exc:
            raise LineEditInvalidError("New line ID must be a canonical UUID") from exc
        if type(at) is not int or not 1 <= at < len(line["rowIndexes"]) or any(
            item["lineId"] == new_id for item in lines
        ):
            raise LineEditInvalidError("Split position or new line ID is invalid")
        tail = line["rowIndexes"][at:]
        line["rowIndexes"] = line["rowIndexes"][:at]
        line["origin"] = "edited"
        lines.insert(lines.index(line) + 1, {"lineId": new_id, "groupCode": line["groupCode"],
                                             "rowIndexes": tail, "origin": "edited"})
    elif kind == "join":
        first = _line(lines, operation.get("firstLineId"))
        second = _line(lines, operation.get("secondLineId"))
        code = operation.get("groupCode")
        if first is second or code not in result["editableGroupCodes"]:
            raise LineEditInvalidError("Join requires distinct lines and an existing target code")
        first["rowIndexes"] = first["rowIndexes"] + second["rowIndexes"]
        first["groupCode"] = code
        first["origin"] = "edited"
        lines.remove(second)
    elif kind == "move":
        source = _line(lines, operation.get("fromLineId"))
        target = _line(lines, operation.get("toLineId"))
        row_index = operation.get("rowIndex")
        position = operation.get("position")
        if (source is target or type(row_index) is not int or row_index not in source["rowIndexes"]
                or type(position) is not int or not 0 <= position <= len(target["rowIndexes"])):
            raise LineEditInvalidError("Move source, vertex or destination is invalid")
        source["rowIndexes"].remove(row_index)
        target["rowIndexes"].insert(position, row_index)
        target["origin"] = "edited"
        if source["rowIndexes"]:
            source["origin"] = "edited"
        else:
            lines.remove(source)
    elif kind == "undo":
        target = operation.get("targetVersion")
        if type(target) is not int or not 0 <= target < operation.get("expectedVersion", 0):
            raise LineEditInvalidError("Undo target version is invalid")
        result = deepcopy(base) if target == 0 else json.loads(
            store.line_edit_version_for(owner_id, revision_id, target).model_json)
        if result["decisionFingerprint"] != base["decisionFingerprint"]:
            raise LineEditConflictError("Undo target uses stale decisions")
    elif kind == "reset":
        result = deepcopy(base)
    else:
        raise LineEditInvalidError("Unknown line edit operation")
    _validate(result)
    return result


def apply_edit(store: ProjectStore, owner_id: str, project_id: str, revision_id: str,
               *, expected_version: int, request_id: str,
               operation: Mapping[str, object]) -> dict:
    store.assert_project_owner(owner_id, project_id)
    revision = store.assert_revision_owner(owner_id, revision_id)
    if revision.project_id != project_id:
        raise ProjectNotFoundError(revision_id)
    command = dict(operation)
    if command.get("type") == "undo":
        command["expectedVersion"] = expected_version
    replay = store.find_line_edit_request_for(owner_id, revision_id, request_id,
        expected_version=expected_version, operation=command)
    if replay is not None:
        return _record_view(replay, include_model=True)
    base = _base_model(store, owner_id, project_id, revision_id)
    latest = store.latest_line_edit_for(owner_id, revision_id)
    current_version = latest.version if latest else 0
    if current_version != expected_version:
        raise LineEditConflictError("Line model changed; reload edits")
    model = json.loads(latest.model_json) if latest else base
    if command.get("type") != "reset" and model["decisionFingerprint"] != base["decisionFingerprint"]:
        raise LineEditConflictError("Decisions changed; reset line model explicitly")
    updated = _apply(model, command, store, owner_id, revision_id, base)
    event = store.record_line_edit_for(owner_id, revision_id, request_id,
        expected_version=expected_version, operation=command, model=updated)
    return _record_view(event, include_model=True)


def history(store: ProjectStore, owner_id: str, project_id: str, revision_id: str,
            *, page: int = 1, page_size: int = 50) -> dict:
    store.assert_project_owner(owner_id, project_id)
    revision = store.assert_revision_owner(owner_id, revision_id)
    if revision.project_id != project_id:
        raise ProjectNotFoundError(revision_id)
    events, total = store.list_line_edit_events_for(owner_id, revision_id, page=page, page_size=page_size)
    return {"projectId": project_id, "revisionId": revision_id,
            "events": [_record_view(event) for event in events],
            "pagination": {"page": page, "pageSize": page_size, "totalItems": total,
                           "hasMore": page * page_size < total}}


def version_view(store: ProjectStore, owner_id: str, project_id: str,
                 revision_id: str, version: int) -> dict:
    store.assert_project_owner(owner_id, project_id)
    revision = store.assert_revision_owner(owner_id, revision_id)
    if revision.project_id != project_id:
        raise ProjectNotFoundError(revision_id)
    if version == 0:
        model = _base_model(store, owner_id, project_id, revision_id)
        return {"version": 0, "model": model, "modelSha256": _hash(model)}
    return _record_view(store.line_edit_version_for(owner_id, revision_id, version), include_model=True)


def job_snapshot(store: ProjectStore, owner_id: str, project_id: str,
                 revision_id: str) -> tuple[dict | None, dict | None]:
    latest = store.latest_line_edit_for(owner_id, revision_id)
    if latest is None:
        return None, None
    state = current_model(store, owner_id, project_id, revision_id)
    if state["staleDecisions"]:
        raise LineEditConflictError("Line edits use stale decisions; reset explicitly")
    segments = [{"groupCode": line["groupCode"], "rowIndexes": line["rowIndexes"]}
                for line in state["model"]["lines"]]
    line_model = {"segments": segments,
                  "sourceRowIndexes": state["model"]["sourceRowIndexes"],
                  "editableGroupCodes": state["model"]["editableGroupCodes"]}
    provenance = {"version": latest.version, "eventId": latest.event_id,
                  "modelSha256": state["modelSha256"]}
    return line_model, provenance
