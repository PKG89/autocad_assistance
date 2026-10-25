# GEOAI-014 — bounded calculation jobs

Status: READY. Base: accepted GEOAI-013 feature commit
`66b8dcc3c651c08baf5d14be2370d0d73ea0f773`. Dependency 013 passed
local and GitHub push/PR checks.

## Bounded scope and resource profile

Add a framework-independent local job coordinator for the existing shared
DXF engine. Accept only validated mapped survey rows and explicit rendering
settings. At most one child compute process may run and at most four jobs
may wait. Each job has a 120-second wall timeout, 25 MiB output cap and
one initial attempt plus at most two explicit retries. A job ID is server
generated. Input, parameters, state and result live under an isolated
server-owned jobs root; no Telegram bot database or production path.

The coordinator must return immediately on submit. Cancellation removes a
waiting job or terminates a running child and frees the slot. Timeout or
worker crash produces a stable terminal state and frees the slot. On
coordinator restart, completed jobs remain inspectable, and interrupted
queued/running jobs are marked failed with a recovery code; retry is an
explicit action. A result is published atomically only after successful
render and output-size check. No automatic unbounded retry.

Candidate files: `services/calculation_jobs.py`, a dedicated worker entry
point under `services/`, focused service tests, and task memory. Add an
HTTP route only if needed to demonstrate nonblocking integration without
preempting GEOAI-020's job UI/API. Preserve existing synchronous DXF API
and Telegram behavior in this task. No geometry, coordinate, unit or CRS
changes; no external queue, network service, deployment or system packages.

## Acceptance and checks

1. Submit/status/cancel/retry are deterministic and bounded; fifth pending
   submission is rejected with a stable capacity error. Running process
   count never exceeds one.
2. A slow calculation does not block the caller or API health endpoint;
   cancellation and timeout terminate the child and release its slot.
3. Child crash or malformed/missing output leaves no successful result.
   Restart reports interrupted work explicitly; accepted results survive.
4. Explicit retry uses the same stored source and settings, with at most
   two retries. Distinct job IDs, path confinement and atomic state/result
   writes are tested. No real survey or production data.
5. Run focused tests, current isolated regression/API suites, negative
   failure and cleanup checks, `pip check`, and `git diff --check`.

Budget: 90 minutes for 014, one attempt plus at most two repair cycles.
P1 ceiling four hours (2026-10-25T04:12:17Z), one writable worktree,
one compute worker and zero external executor spend. Stop on lost test
isolation, unexpected edits, untrusted path access, exhausted resources or
a missing domain decision; record the exact blocker and Git state.
