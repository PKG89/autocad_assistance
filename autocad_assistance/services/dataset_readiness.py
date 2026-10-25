"""Private metadata-only audit; never exports or activates archive examples."""

from __future__ import annotations

import json

from autocad_assistance.services.project_store import ProjectStore


MAX_AUDIT_PROJECTS = 20
MAX_AUDIT_ARCHIVES = 100
MAX_METADATA_BYTES = 16 * 1024


class DatasetReadinessError(ValueError):
    """Archive metadata cannot be safely summarized."""


def _block(code: str, needed: str) -> dict:
    return {"code": code, "needed": needed}


def audit_owner(store: ProjectStore, owner_id: str) -> dict:
    """Report evidence gaps without reading raw source/reference bytes."""
    projects = store.list_projects_for(owner_id)
    if len(projects) > MAX_AUDIT_PROJECTS:
        return {
            "auditVersion": "geoai-dataset-readiness-v1", "complete": False,
            "readyForTraining": False, "readyForEvaluation": False,
            "projectCount": len(projects), "archiveCount": None,
            "blockers": [_block("AUDIT_PROJECT_LIMIT",
                "Reduce audit scope or review project limits before dataset use")],
        }

    total_archives = 0
    training_assertions = 0
    evaluation_assertions = 0
    with_corrections = 0
    for project in projects:
        page = 1
        expected_total = None
        seen_ids = set()
        while True:
            entries, total = store.list_references_for(owner_id, project.project_id,
                                                        page=page, page_size=50)
            if expected_total is None:
                expected_total = total
            if total != expected_total:
                raise DatasetReadinessError("Archive changed during audit")
            if total_archives + total > MAX_AUDIT_ARCHIVES:
                return {
                    "auditVersion": "geoai-dataset-readiness-v1", "complete": False,
                    "readyForTraining": False, "readyForEvaluation": False,
                    "projectCount": len(projects), "archiveCount": total_archives + total,
                    "blockers": [_block("AUDIT_ARCHIVE_LIMIT",
                        "Review archive limits and audit smaller owner-approved groups")],
                }
            for record in entries:
                if record.entry_id in seen_ids:
                    raise DatasetReadinessError("Archive pagination changed during audit")
                seen_ids.add(record.entry_id)
                if len(record.metadata_json.encode("utf-8")) > MAX_METADATA_BYTES:
                    raise DatasetReadinessError("Archive metadata is too large")
                try:
                    metadata = json.loads(record.metadata_json)
                    corrections = json.loads(record.corrections_json)
                    uses = metadata["permittedUses"]
                    if (not isinstance(uses, list) or any(
                        use not in {"training", "evaluation", "comparison"} for use in uses
                    ) or not isinstance(corrections, dict)):
                        raise ValueError("Archive metadata shape is invalid")
                except (ValueError, TypeError, KeyError) as exc:
                    raise DatasetReadinessError("Archive metadata is invalid") from exc
                training_assertions += "training" in uses
                evaluation_assertions += "evaluation" in uses
                with_corrections += bool(corrections.get("decisions") or corrections.get("lineEdit"))
            if page * 50 >= total:
                if len(seen_ids) != total:
                    raise DatasetReadinessError("Archive pagination changed during audit")
                total_archives += total
                break
            page += 1

    blockers = []
    if total_archives == 0:
        blockers.append(_block("NO_REFERENCES",
            "Supply owner-approved field files and independently correct DXF references"))
    if training_assertions == 0:
        blockers.append(_block("TRAINING_USE_NOT_ASSERTED",
            "Explicitly authorize training use for each proposed reference"))
    if evaluation_assertions == 0:
        blockers.append(_block("EVALUATION_USE_NOT_ASSERTED",
            "Explicitly authorize evaluation use for independent references"))
    blockers.extend([
        _block("RIGHTS_UNVERIFIED", "Record independent review of the rights holder and permission evidence"),
        _block("OBJECT_FAMILY_ID_MISSING",
               "Identify each surveyed object and keep all its revisions in one split"),
        _block("REFERENCE_REVIEW_MISSING",
               "Have an independent topographer verify reference DXF and correction labels"),
        _block("CLASS_COVERAGE_UNKNOWN",
               "Set priority classes and supply approved object families for each class"),
        _block("INDEPENDENT_SPLIT_MISSING",
               "Reserve disjoint whole-object training and validation families"),
        _block("METRIC_CRITERIA_MISSING",
               "Approve baseline, per-class measures and acceptable regression criteria"),
        _block("BYTE_INTEGRITY_PENDING",
               "Verify all source and reference bytes immediately before creating a dataset"),
    ])
    return {
        "auditVersion": "geoai-dataset-readiness-v1", "complete": True,
        "readyForTraining": False, "readyForEvaluation": False,
        "schemaCapability": "user_assertions_only_no_independent_verification",
        "projectCount": len(projects), "archiveCount": total_archives,
        "trainingUseAssertions": training_assertions,
        "evaluationUseAssertions": evaluation_assertions,
        "archivesWithCorrectionSnapshot": with_corrections,
        "blockers": blockers,
        "exampleRequest": {
            "priorityClasses": "Owner and topographer must define",
            "families": "Independent approved objects per priority class, with all revisions kept together",
            "references": "Original field source, independently checked correct DXF and labelled corrections",
            "permissions": "Verified rights for each selected use; user assertions alone do not qualify",
        },
    }
