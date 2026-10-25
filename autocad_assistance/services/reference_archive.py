"""Private archive of supplied DXF references with explicit rights assertions."""

from __future__ import annotations

from io import BytesIO
import json
from typing import Mapping

import ezdxf.recover

from autocad_assistance.services.project_store import (
    MAX_REFERENCE_DXF_BYTES, ProjectStore, ReferenceRecord,
)


MAX_REFERENCE_ENTITIES = 100_000
PERMITTED_USES = frozenset({"comparison", "evaluation", "training"})
REQUIRED_TEXT = {
    "fieldProvenance": 2048,
    "referenceProvenance": 2048,
    "rightsHolder": 200,
    "permissionEvidence": 4096,
}


class ReferenceInvalidError(ValueError):
    """Reference bytes or provenance are not acceptable for private archiving."""


class ReferenceLimitError(ValueError):
    """Reference bytes or geometry exceed archive bounds."""


def validate_metadata(metadata: Mapping[str, object]) -> dict:
    if not isinstance(metadata, Mapping):
        raise ReferenceInvalidError("Reference metadata is invalid")
    allowed = set(REQUIRED_TEXT) | {"permittedUses", "notes"}
    if set(metadata) - allowed:
        raise ReferenceInvalidError("Unknown reference metadata fields")
    result = {}
    for field, limit in REQUIRED_TEXT.items():
        value = metadata.get(field)
        if (not isinstance(value, str) or not value.strip() or len(value) > limit
                or any(ord(char) < 32 for char in value)):
            raise ReferenceInvalidError(f"{field} is required and bounded")
        result[field] = value.strip()
    uses = metadata.get("permittedUses")
    if (not isinstance(uses, list) or not 1 <= len(uses) <= len(PERMITTED_USES)
            or any(not isinstance(item, str) or item not in PERMITTED_USES for item in uses)
            or len(set(uses)) != len(uses)):
        raise ReferenceInvalidError("Explicit permittedUses are required")
    result["permittedUses"] = sorted(uses)
    notes = metadata.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 2048 or any(ord(char) < 32 for char in notes):
        raise ReferenceInvalidError("Reference notes are invalid")
    result["notes"] = notes.strip()
    return result


def validate_reference_dxf(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not raw:
        raise ReferenceInvalidError("Reference DXF is empty")
    if len(raw) > MAX_REFERENCE_DXF_BYTES:
        raise ReferenceLimitError("Reference DXF exceeds 25 MiB")
    try:
        drawing, audit = ezdxf.recover.read(BytesIO(raw))
        if audit.has_errors:
            raise ReferenceInvalidError("Reference DXF audit failed")
        count = 0
        for _ in drawing.modelspace():
            count += 1
            if count > MAX_REFERENCE_ENTITIES:
                raise ReferenceLimitError("Reference DXF has too many entities")
        if count == 0:
            raise ReferenceInvalidError("Reference DXF has no model-space entities")
        return {"dxfVersion": drawing.dxfversion, "modelSpaceEntities": count,
                "validator": "ezdxf-recover-v1"}
    except (ReferenceInvalidError, ReferenceLimitError):
        raise
    except Exception as exc:
        raise ReferenceInvalidError("Reference DXF is invalid") from exc


def _corrections(store: ProjectStore, owner_id: str, revision_id: str) -> dict:
    decisions = store.latest_line_decisions_for(owner_id, revision_id)
    edit = store.latest_line_edit_for(owner_id, revision_id)
    return {
        "decisions": [{"eventId": event.event_id, "groupCode": event.group_code,
                       "version": event.version, "action": event.action}
                      for event in decisions],
        "lineEdit": {"eventId": edit.event_id, "version": edit.version,
                     "modelSha256": edit.model_sha256} if edit else None,
    }


def reference_view(record: ReferenceRecord) -> dict:
    return {
        "entryId": record.entry_id, "projectId": record.project_id,
        "revisionId": record.revision_id, "sourceSha256": record.source_sha256,
        "referenceSha256": record.reference_sha256,
        "referenceSize": record.reference_size,
        "metadata": json.loads(record.metadata_json),
        "corrections": json.loads(record.corrections_json),
        "validation": json.loads(record.validation_json),
        "permissionStatus": "user_asserted_unverified",
        "authorId": record.author_id,
        "createdAt": record.created_at.replace(" ", "T") + "Z",
    }


def create_reference(
    store: ProjectStore, owner_id: str, revision_id: str, request_id: str,
    raw: bytes, metadata: Mapping[str, object],
) -> dict:
    revision = store.assert_revision_owner(owner_id, revision_id)
    store.read_source_for(owner_id, revision.project_id, revision_id)
    accepted_metadata = validate_metadata(metadata)
    validation = validate_reference_dxf(raw)
    from hashlib import sha256
    prior = store.lookup_reference_for(
        owner_id, revision_id, request_id,
        reference_sha256=sha256(raw).hexdigest(), metadata=accepted_metadata,
    )
    if prior is not None:
        return reference_view(prior)
    corrections = _corrections(store, owner_id, revision_id)
    record = store.create_reference_for(
        owner_id, revision_id, request_id, raw,
        metadata=accepted_metadata, corrections=corrections,
        validation=validation,
    )
    return reference_view(record)


def list_references(store: ProjectStore, owner_id: str, project_id: str,
                    *, page: int = 1, page_size: int = 20) -> dict:
    entries, total = store.list_references_for(owner_id, project_id, page=page, page_size=page_size)
    return {"projectId": project_id, "data": [reference_view(entry) for entry in entries],
            "pagination": {"page": page, "pageSize": page_size,
                           "totalItems": total, "hasMore": page * page_size < total}}
