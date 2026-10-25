"""Owner-scoped bridge from immutable survey revisions to bounded DXF jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Mapping

from autocad_assistance.services.calculation_jobs import (
    CalculationJobManager, JobNotFoundError, JobSnapshot, JobStateError,
)
from autocad_assistance.services.project_store import (
    DuplicateSubmissionError, ProjectIntegrityError, ProjectStore,
    ProjectStoreError, ResourceQuotaExceededError,
)
from autocad_assistance.services.survey_contract import (
    SurveyContext, build_survey_dataset, drawing_factor_for_plan_denominator,
)
from autocad_assistance.services.line_decisions import decision_snapshot_for_job


@dataclass(frozen=True)
class JobView:
    job_id: str
    revision_id: str
    status: str
    attempt: int
    retry_of: str | None
    error_code: str | None
    result_ready: bool
    created_at: float
    updated_at: float


class ProjectJobBridge:
    def __init__(self, store: ProjectStore, manager: CalculationJobManager) -> None:
        self.store = store
        self.manager = manager

    def submit(
        self, owner_id: str, revision_id: str, request_id: str,
        *, tin_settings: Mapping[str, object],
    ) -> JobView:
        revision = self.store.assert_revision_owner(owner_id, revision_id)
        raw = self.store.read_source_for(owner_id, revision.project_id, revision_id)
        settings = json.loads(revision.settings_json)
        mapping = settings.get("renderSettings", {}).get("mapping")
        if not isinstance(mapping, dict) or revision.source_format not in {"txt", "csv"}:
            raise JobStateError("Revision lacks an accepted TXT/CSV mapping")
        context = SurveyContext(
            coordinate_system=settings.get("coordinateSystem"),
            horizontal_unit=settings.get("horizontalUnit"),
            vertical_unit=settings.get("verticalUnit"),
            scale_factor=settings["scaleFactor"],
        )
        dataset = build_survey_dataset(raw, mapping, context=context)
        line_orders, decision_versions = decision_snapshot_for_job(
            self.store, owner_id, revision.project_id, revision_id,
        )
        request_settings = {
            "revisionId": revision_id,
            "sourceSha256": revision.source_sha256,
            "algorithmVersion": revision.algorithm_version,
            "mapping": mapping,
            "scaleFactor": str(context.scale_factor),
            "tinSettings": dict(tin_settings),
            "lineOrders": line_orders,
            "lineDecisions": decision_versions,
        }
        existing_id = self.store.lookup_job_submission_for(
            owner_id, revision_id, request_id, request_settings=request_settings,
        )
        if existing_id is not None:
            return self.get(owner_id, existing_id)

        def admit(job_id: str) -> None:
            self.store.register_job_submission_for(
                owner_id, revision_id, job_id, request_id,
                request_settings=request_settings,
            )

        try:
            snapshot = self.manager.submit(
                dataset.mapped_rows,
                scale_factor=drawing_factor_for_plan_denominator(context.scale_factor),
                tin_settings=tin_settings,
                line_orders=line_orders,
                on_admit=admit,
            )
        except DuplicateSubmissionError as duplicate:
            return self.get(owner_id, duplicate.job_id)
        return self.get(owner_id, snapshot.job_id)

    def retry(self, owner_id: str, old_job_id: str, request_id: str) -> JobView:
        old = self.store.assert_job_owner(owner_id, old_job_id)
        request_settings = dict(json.loads(old.request_json))
        request_settings["retryOf"] = old_job_id
        existing_id = self.store.lookup_job_submission_for(
            owner_id, old.revision_id, request_id, request_settings=request_settings,
        )
        if existing_id is not None:
            return self.get(owner_id, existing_id)

        def admit(job_id: str) -> None:
            self.store.register_job_submission_for(
                owner_id, old.revision_id, job_id, request_id,
                request_settings=request_settings, retry_of=old_job_id,
            )

        try:
            snapshot = self.manager.retry(old_job_id, on_admit=admit)
        except DuplicateSubmissionError as duplicate:
            return self.get(owner_id, duplicate.job_id)
        return self.get(owner_id, snapshot.job_id)

    def cancel(self, owner_id: str, job_id: str) -> JobView:
        self.store.assert_job_owner(owner_id, job_id)
        self.manager.cancel(job_id)
        return self.get(owner_id, job_id)

    def get(self, owner_id: str, job_id: str) -> JobView:
        job = self.store.assert_job_owner(owner_id, job_id)
        try:
            snapshot: JobSnapshot = self.manager.get(job_id)
        except JobNotFoundError:
            if job.result_sha256 is None and job.status != "failed":
                job = self.store.update_job_status(job_id, "failed")
            when = datetime.fromisoformat(job.created_at).replace(tzinfo=timezone.utc).timestamp()
            return JobView(
                job_id=job_id, revision_id=job.revision_id,
                status="succeeded" if job.result_sha256 is not None else "failed",
                attempt=1, retry_of=job.retry_of,
                error_code=None if job.result_sha256 is not None else "COORDINATOR_RECORD_MISSING",
                result_ready=job.result_sha256 is not None,
                created_at=when, updated_at=when,
            )
        if job.result_sha256 is not None:
            return JobView(
                job_id=job_id, revision_id=job.revision_id,
                status="succeeded", attempt=snapshot.attempt, retry_of=snapshot.retry_of,
                error_code=None, result_ready=True,
                created_at=snapshot.created_at, updated_at=snapshot.updated_at,
            )
        if job.status != snapshot.status:
            job = self.store.update_job_status(job_id, snapshot.status)
        error_code = snapshot.error_code
        if snapshot.status == "succeeded" and job.result_sha256 is None:
            try:
                result = self.manager.read_result(job_id)
                job = self.store.publish_result_for(owner_id, job_id, result)
            except ResourceQuotaExceededError:
                error_code = "RESULT_QUOTA_EXCEEDED"
            except ProjectStoreError:
                job = self.store.assert_job_owner(owner_id, job_id)
                if job.result_sha256 is None:
                    error_code = "RESULT_UNAVAILABLE"
            except (OSError, ProjectIntegrityError, JobStateError):
                error_code = "RESULT_UNAVAILABLE"
        return JobView(
            job_id=job_id, revision_id=job.revision_id, status=snapshot.status,
            attempt=snapshot.attempt, retry_of=snapshot.retry_of,
            error_code=error_code, result_ready=job.result_sha256 is not None,
            created_at=snapshot.created_at, updated_at=snapshot.updated_at,
        )
