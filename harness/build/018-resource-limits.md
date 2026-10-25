# GEOAI-018 — bounded resources and explicit expired-upload cleanup

Status: READY. Base: accepted GEOAI-017 feature commit
`f3bee9c22daeacc4217b21286338f5ee48058bdd`. Dependencies 014–017
passed local and GitHub feature/PR checks. P3 manifest:
`/home/geoai/dev-data/geoai-autonomy/p3-run-manifest.json`.

## Scope and policy

Add explicit, injectable per-owner limits to the separate project store:
20 projects, 100 active uploads, 500 revisions, 500 jobs and 512 MiB
of accepted upload/source/result bytes by default. These are conservative
development caps, not a product entitlement. Enforce counts and total
bytes inside SQLite write transactions; reject an over-limit operation
without accepted metadata or a file orphan. Protected upload API returns
one stable quota error, with its newly written file removed safely.

Version-3 project metadata records each upload's creation time, optional
expiration and cleanup state. Retention is opt-in through an explicit
positive `upload_retention_days` setting; absent configuration means no
expiration and no automatic deletion. A bounded maintenance command
lists candidates by default and requires `--apply` plus explicit project
and upload roots to remove expired uploads. It must use no-follow
directory descriptors, never traverse a symlink, and leave a retryable
record if file cleanup fails. Immutable project revisions and accepted
DXF results are never purged by this task. Copying a source into a
revision remains independent of the temporary upload's lifetime.

No production cleanup run, real data deletion, deployment, bot/statistics
DB change, scheduler, new daemon, geometry change, new package or system
install. Candidate files: `services/project_store.py`, a narrow upload
cleanup service/CLI, `api/app.py`, `api/uploads.py`, focused tests and
project memory. Existing no-auth regression mode remains intact.

## Acceptance and checks

1. Tiny injected limits reject the next upload, project, revision, job
   and result across restart and concurrent writers. Rejected uploads
   leave neither owner row nor file; the response has a stable error.
2. With no retention setting, no upload expires. With a configured age,
   only expired, active uploads are candidates. Dry-run changes nothing.
   Apply removes only exact UUID-named upload files through no-follow
   descriptors and retires metadata; symlink/path failures are retryable.
3. Existing version-2 owners migrate without a guess about historical
   creation time or deletion eligibility. Project revisions/results stay
   readable after their source upload expires and is removed.
4. Run `python -m unittest tests.test_resource_limits -v`, then
   `GEOAI_PYTHON=/home/geoai/dev-data/geoai-autonomy/p0-007b/clean-venv/bin/python
   GEOAI_TEST_REPORT_ROOT=/home/geoai/dev-data/geoai-autonomy/p3-018/final-gate
   bash scripts/geoai-ci-checks.sh`, plus negative no-follow/rollback
   checks, `pip check`, `git diff --check` and GitHub feature/PR CI.

Budget: 90 minutes for 018, one attempt plus at most two repair cycles.
P3 deadline 2026-10-25T05:01:04Z, one writable worktree/compute worker,
zero external executor spend. Stop on policy ambiguity that changes real
data, unexpected edits, lost isolation, access bypass, exhausted limits
or an unauthorized production operation; record exact blocker and Git.
