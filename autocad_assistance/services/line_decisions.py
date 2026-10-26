"""Owner-scoped, versioned choices over immutable A/B line proposals."""

from __future__ import annotations

import json

from autocad_assistance.services.line_candidates import (
    LineCandidateInvalidError, build_line_candidates,
)
from autocad_assistance.services.project_store import (
    LineDecisionRecord, ProjectNotFoundError, ProjectStore,
)


class LineDecisionInvalidError(ValueError):
    """The chosen proposal does not match the current immutable revision."""


def decision_view(record: LineDecisionRecord) -> dict:
    snapshot = json.loads(record.snapshot_json)
    return {
        "eventId": record.event_id, "revisionId": record.revision_id,
        "groupCode": record.group_code, "version": record.version,
        "requestId": record.request_id, "action": record.action,
        "snapshot": snapshot, "authorId": record.author_id,
        "createdAt": record.created_at.replace(" ", "T") + "Z",
    }


def history(store: ProjectStore, owner_id: str, project_id: str, revision_id: str,
            *, page: int = 1, page_size: int = 50) -> dict:
    store.assert_project_owner(owner_id, project_id)
    revision = store.assert_revision_owner(owner_id, revision_id)
    if revision.project_id != project_id:
        raise ProjectNotFoundError(revision_id)
    events = store.list_line_decisions_for(owner_id, revision_id,
                                           offset=(page - 1) * page_size, limit=page_size)
    latest = store.latest_line_decisions_for(owner_id, revision_id)
    total = store.count_line_decisions_for(owner_id, revision_id)
    return {"projectId": project_id, "revisionId": revision_id,
            "events": [decision_view(event) for event in events],
            "latest": [decision_view(event) for event in latest],
            "pagination": {"page": page, "pageSize": page_size,
                           "totalItems": total, "hasMore": page * page_size < total}}


def record_decision(
    store: ProjectStore, owner_id: str, project_id: str, revision_id: str,
    group_code: str, *, expected_version: int, request_id: str, action: str,
    source_sha256: str, settings_sha256: str, candidate_version: str,
) -> dict:
    comparison = build_line_candidates(store, owner_id, project_id, revision_id)
    if (comparison["sourceSha256"], comparison["settingsSha256"], comparison["candidateVersion"]) != (
        source_sha256, settings_sha256, candidate_version,
    ):
        raise LineDecisionInvalidError("Candidate provenance changed; reload comparison")
    group = next((item for item in comparison["groups"] if item["groupCode"] == group_code), None)
    if group is None:
        raise ProjectNotFoundError(group_code)
    if action in {"A", "B"} and group["status"] != "proposals":
        raise LineDecisionInvalidError("Group has no eligible A/B proposals")
    if action not in {"A", "B", "skip", "manual"}:
        raise LineDecisionInvalidError("Unknown decision action")
    snapshot = {
        "projectId": project_id, "revisionId": revision_id,
        "sourceSha256": source_sha256, "settingsSha256": settings_sha256,
        "generatorVersion": comparison["generatorVersion"],
        "candidateVersion": candidate_version, "group": group,
    }
    event = store.record_line_decision_for(
        owner_id, revision_id, group_code, expected_version=expected_version,
        request_id=request_id, action=action, snapshot=snapshot,
    )
    return decision_view(event)


def decision_snapshot_for_job(
    store: ProjectStore, owner_id: str, project_id: str, revision_id: str,
) -> tuple[dict[str, list[int]], list[dict]]:
    latest = {event.group_code: event for event in store.latest_line_decisions_for(owner_id, revision_id)}
    if not latest:
        return {}, []
    comparison = build_line_candidates(store, owner_id, project_id, revision_id)
    groups = {group["groupCode"]: group for group in comparison["groups"]}
    orders: dict[str, list[int]] = {}
    provenance: list[dict] = []
    for code, event in sorted(latest.items()):
        snapshot = json.loads(event.snapshot_json)
        if (snapshot.get("sourceSha256") != comparison["sourceSha256"]
                or snapshot.get("settingsSha256") != comparison["settingsSha256"]
                or snapshot.get("candidateVersion") != comparison["candidateVersion"]
                or snapshot.get("generatorVersion") != comparison["generatorVersion"]
                or snapshot.get("group") != groups.get(code)):
            raise LineCandidateInvalidError("Saved decision candidate snapshot is stale")
        provenance.append({"groupCode": code, "version": event.version,
                           "eventId": event.event_id, "action": event.action})
        if event.action in {"A", "B"}:
            group = groups[code]
            if group["status"] != "proposals":
                raise LineCandidateInvalidError("Saved line group is ineligible")
            candidate = next(item for item in group["candidates"] if item["label"] == event.action)
            orders[code] = candidate["rowIndexes"]
    return orders, provenance
