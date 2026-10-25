# GEOAI-036 — explicit dataset-readiness audit without data export

Status: READY from accepted GEOAI-025, 027 and 028; base
`8e30d74e3ba31505b0f8f1a9e065cb1e43cdfd2c`.
P10 manifest deadline 2026-10-25T07:37:48Z; task ceiling 90 minutes,
one initial attempt plus at most two repairs, one writable worktree,
one compute worker and $0 external executor. P7 030/031 remain blocked
by independent real references and class criteria, so this is an
independent task.

## Scope

Add a read-only, owner-scoped readiness report over GEOAI-027 private
reference archive metadata. It may count entries and inspect sealed
metadata, but must not export source/DXF bytes, permission evidence,
personal names or raw correction histories. A user assertion of rights
(`user_asserted_unverified`) is never equivalent to independent
permission verification. No entry is training-ready merely because it
was uploaded or selected for `training`/`evaluation` use.

Report exact, machine-readable blockers and actionable missing
evidence: independent rights review for the requested use; explicit
whole-object family IDs covering versions; independently checked
reference labels and class tags; a disjoint whole-object validation
split; class priorities and baseline/metric criteria; byte-integrity
verification before any actual dataset creation. Preserve source and
archive immutability. If there are no real examples, state that the
catalog cannot establish coverage and request owner-approved examples
per priority class rather than inventing a sample count or threshold.

Limit the audit to 20 projects and 100 entries per request, bound
metadata parsing, and return an explicit limit/incomplete status for
larger stores. No corpus writer, model training, scheduling, automatic
use of archives, rights judgement, new dependency or production action.

Allowed files: read-only service, authenticated API adapter/wiring,
synthetic tests, this spec and shared memory. No schema migration or
modification of reference records.

## Acceptance and commands

1. Empty owner and synthetic archive cases return deterministic
   `ready=false` with concrete blockers. A `training` assertion alone
   never clears rights or split/label blockers.
2. Foreign owner cannot inspect another owner's counts; no raw source,
   DXF, rights text or author identifiers appear in the response.
   Tampered metadata and audit limits fail closed/incomplete.
3. Focused `python -m unittest -v tests.test_dataset_readiness`, full
   `scripts/geoai-ci-checks.sh` in clean venv/outside report root,
   `git diff --check`, verified synthetic localhost HTTPS smoke and
   exact feature/PR CI pass.

GEOAI-036 can be accepted as a readiness assessment with `ready=false`
and a concrete evidence request. GEOAI-037/038 cannot start until the
missing rights, independent object examples and criteria are supplied
and a later audit actually passes. Stop on budget, unexpected edits,
lost isolation, real data use or production action.
