# GEOAI-020 — durable web jobs, result downloads and retry

Status: ACCEPTED at `91aeb53ad410abdc071498a4d22e561db3684dbe`. Base: accepted GEOAI-019 feature commit
`897cf600e916207fa2a8f6a9797e3bc8729fe642`. Dependencies
014–019 passed local and GitHub feature/PR checks. P3 deadline is
2026-10-25T05:01:04Z.

## Scope and job contract

Bind authenticated project revisions to the existing 014 bounded
single-worker coordinator. Opt-in configuration supplies an explicit
jobs root; no worker starts in legacy/no-auth app mode. Parse the
immutable source and the revision's accepted mapping/context through
the shared survey service, submit mapped rows to 014's child process,
and persist job request/source/algorithm provenance in ProjectStore.
Keep the 014 queue of four, 120-second compute timeout, 25 MiB result
bound, two retries and one active child. No geometry changes.

Expose owner-scoped job submit, list/status, cancel and retry routes.
Both submit and retry require a client-owned canonical UUID
`Idempotency-Key`; a unique SQLite claim binds the key to owner,
revision, exact request digest and resulting job ID before queue
admission is visible. A retry with the same key/body returns the same
job; a changed body conflicts. Coordinator admission failure must not
leave accepted project metadata or an untracked worker job. Preserve
the key and job state across restart. Report stable error codes for
capacity, timeout, interruption, cancellation, invalid request and
result storage failure. Do not automatically retry unknown outcomes.

Poll status to reconcile coordinator state with project metadata and
copy a successful DXF into the versioned result store only after
bounded no-follow read and checksum acceptance. Owner-checked download
must never expose an unaccepted or foreign result. A restart may mark
an in-flight job interrupted, but the job ID, request and failure remain
visible for explicit retry. 018 cleanup still touches only expired
temporary uploads, never active jobs or immutable sources/results.

Extend the same-origin screen with a selected revision, submit button,
status/error display, cancel/retry controls, bounded polling while
active, and a download link only after result acceptance. Restore
project job history after reload; disable action buttons while pending.
Keep CSRF in memory, render untrusted errors as text and make no
automatic job submissions or retries.

No production worker/deployment, real survey, credential provisioning,
Telegram/statistics DB migration, external queue, new package or system
install. Candidate files: the 014 coordinator's atomic admission hook,
ProjectStore schema/owner submission methods, a bridge service, job
router, existing result router/app factory, local web assets, focused
tests and project memory.

## Acceptance and checks

1. One owner can start a job from a saved revision; the result uses the
   accepted source/mapping/context and downloads as a verified DXF.
   Foreign/unknown IDs return identical 404s; missing session/CSRF
   rejects before body parsing.
2. Same idempotency key and body creates one job across concurrent
   calls and restart; same key with different intent returns 409.
   Queue/admission/DB failure leaves no accepted orphan. Double-click
   in the browser creates at most one job.
3. Status, cancellation, explicit retry, error code and version/result
   association survive reload/restart. An interrupted job does not
   silently rerun. Result publication waits for the accepted bytes;
   tampering, symlinks and quota failures cannot produce a download.
4. Run focused job/API/UI tests, current isolated regression/API sets,
   `pip check`, `git diff --check`, and exact GitHub feature/PR CI.
   Actual command: `GEOAI_PYTHON=/home/geoai/dev-data/geoai-autonomy/p0-007b/clean-venv/bin/python
   GEOAI_TEST_REPORT_ROOT=/home/geoai/dev-data/geoai-autonomy/p3-020/final-gate
   bash scripts/geoai-ci-checks.sh`.

Budget: 90 minutes, initial attempt plus at most two repair cycles,
one writable worktree and one compute worker, zero external executor
spend. Stop on an unaccepted dependency, missing access/domain
decision, unexpected edits, lost isolation, exhausted time/repair
budget or unauthorized production action; record HEAD, diff, checks
and exact blocker.

## Implementation and local evidence

- One opt-in coordinator binds an immutable accepted TXT/CSV revision to
  the 014 child process. New schema v5 stores a unique client UUID
  claim and job provenance in one SQLite transaction before admission.
  Matching retries return the same ID across concurrent requests and
  restart; a changed request returns 409. Coordinator admission failure
  rolls back its temporary request/state directory.
- Authenticated owner routes expose submit, list, status, cancel,
  explicit retry and accepted-result download. The screen restores
  history after reload, polls only active jobs, disables pending
  actions and displays a DXF link only after versioned publication.
  Result bytes pass a bounded no-follow read and coordinator SHA-256
  check before ProjectStore copies and hashes them.
- Focused tests cover real DXF generation, concurrent key claim,
  replay/conflict, cancellation/retry, restart, owner boundary,
  admission rollback, tampered result and prior resource migrations.
  The full local gate is recorded under
  `/home/geoai/dev-data/geoai-autonomy/p3-020/accepted-gate.log`.
- A disposable browser fixture on localhost showed one accepted job
  and one key claim after a double click; it reached `succeeded`,
  revealed the DXF link and retained both history and link on reload.
  Its server and SSH tunnel were stopped. No real survey or production
  identity was used.
- GitHub `GEO AI checks` push run 40151146814 and draft PR #6 run
  40151149754 passed at the exact commit. Full branch bundle SHA-256
  `3301fc0570f992407ad168f77b7612b3388757a1dcdb957c43762f049582055e`
  matched on VM and Windows. No production migration, cleanup or
  deployment ran.
