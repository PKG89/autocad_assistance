# GEOAI-022 — reproducible disposable staging, recovery and rollback

Status: READY. Base: accepted GEOAI-021 feature commit
`eecaad8e7ccef59a609a8d2ad3929071efb1de7e`; all P1–P3 and
021 dependencies passed local and exact GitHub feature/PR CI. P4
deadline: 2026-10-25T05:35:44Z.

## Environment and scope

VM109 has no Docker; do not install it or change system services.
Use the already verified clean Python 3.13 environment, an exact
package-version lock and a release archive from a clean Git commit.
Place all staging releases, config, synthetic auth/project/uploads/jobs,
TLS key, logs and backups only under an explicit disposable root in
`/home/geoai/dev-data/geoai-autonomy/p4-022/`. Bind the test server
only to loopback HTTPS. No production secret, survey, Telegram poll,
Compose deployment, GHCR publication, system package or daemon change.

Add a standard-library staging tool with explicit commands to build
and verify a release, activate an exact release ID, run from a
synthetic-only config, check health, create an offline integrity-checked
backup, and restore to a fresh root. Refuse unknown/symlinked roots,
dirty source checkouts, mismatched Python packages, active service
backups, invalid archives, tampered files and in-place restore. Copy
the SQLite files and immutable source/result tree only while the
local staging service is stopped; record checksums and permissions.

Demonstrate code rollback by changing the selected release ID and
state rollback by restoring a verified backup in a fresh root. Both
before/after app versions must use compatible schema v5. Verify the
restored app health and synthetic owner/project/result via HTTPS, and
that a deliberately corrupted backup is rejected without changing the
current stage. Logs must omit request bodies, passwords, tokens and
the synthetic credential. The release manifest records commit, code
archive SHA-256, Python/package lock and accepted state schema.

Candidate files: `scripts/geoai_staging.py`, optional small runner,
`harness/staging/requirements.lock`, focused staging tests, this spec
and shared memory. Keep the existing app/Telegram/database migration
code intact unless a focused test proves a root cause. No production
deployment or publication is authorized.

## Acceptance and bounds

1. Rebuilding the same clean commit with the same verified runtime
   produces the same code archive checksum; mismatch refuses startup.
2. The disposable HTTPS app serves `/health`, requires owner auth for
   project routes, and stores synthetic data only in its configured
   root; safe logs contain no credentials or request bodies.
3. Offline backup and fresh-root restore preserve SQLite records,
   source/result bytes, ownership and checksums; tampering is rejected.
   Activation switches exact release IDs; rollback of a compatible
   release and data snapshot passes health and a synthetic result read.
4. Focused staging and current isolated regression/API suites,
   `pip check`, `git diff --check` and exact GitHub feature/PR CI pass.

Actual full gate: `GEOAI_PYTHON=/home/geoai/dev-data/geoai-autonomy/p0-007b/clean-venv/bin/python GEOAI_TEST_REPORT_ROOT=/home/geoai/dev-data/geoai-autonomy/p4-022/final-gate bash scripts/geoai-ci-checks.sh`.

Budget: 90 minutes, initial attempt plus at most two repairs, one
writable worktree and one compute worker; four-hour P4 package ceiling
and $0 external executor spend. Stop on lost isolation, unexpected
edits, missing access/credential/domain decision, exhausted time or
repair budget, an unaccepted dependency, or any production action.
Record HEAD, diff, checks and exact blocker before pausing.
