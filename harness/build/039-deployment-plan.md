# GEO AI — proposed controlled deployment of the accepted web release

Status: REVIEW ONLY. GEOAI-040, merge, production deployment, migration
and changes to working data remain unauthorized.

## Candidate and boundary

- Exact release commit: `79528bb9f6070e458724886a915f9d035cdfd110`.
- Contents: accepted P0–P6 and GEOAI-029. Current draft PR head is a
  later documentation/development branch and is **not** the release ID.
- Exclusions: experimental 030, unfinished 031–035 and 037–038.
  Accepted GEOAI-036 is outside this selected release and does not
  certify dataset readiness. No AI training or recommendation service.
- Runtime: Python 3.13 with exact `harness/staging/requirements.lock`.
  The verified Git archive and lock are the artifacts to promote;
  rebuilds must match checksums. Staging manifest schemaVersion 5 is
  not a database version: project SQLite uses user_version 8 and auth
  SQLite uses user_version 1.
- `scripts/geoai_staging.py` deliberately accepts synthetic mode and
  loopback HTTPS only. It is an acceptance/recovery tool, not a
  production deployment command. GEOAI-040 must specify and review
  the actual production runner before any publication.
- Verified archive SHA-256:
  `cada7fb4f2919fe321cffbe74beeec499bc60e833e33f36a94f404560f91ce81`.
  Package lock SHA-256:
  `d8d2cf3756f29f64246f133f694ee61aa9711f8eb8e95c4fd2039734d381c351`.
  Compatible test rollback commit:
  `1ea061c1afb4b75b0aba06ae67d402b0a3e815a6`.

## Approval inputs before GEOAI-040

The target-specific closed-pilot proposal, measured/proposed thresholds,
no-migration decision and operator sequence are in
`harness/build/039-pilot-preparation.md`. This proposal does not authorize
launch or a change to the running bot.

The proposed closed-pilot target is a new dedicated Debian 13 VM
(2 vCPU, 4 GiB RAM, 60 GiB disk), not VM109 or CT108. For its fresh
empty state, no working-data migration or production backup is needed.
Its exact VM ID, capacity, address and access still need owner approval.
Owner chooses the target host/environment, hostname and TLS source,
operator, access path, production secrets mechanism, data directories,
backup location/retention, maintenance window, monitoring recipient,
allowed downtime, and whether a migration is needed. Review the exact
commit, functions, schema, evidence and rollback threshold. Obtain
separate authorization for production publication and any migration.

## Proposed execution sequence after authorization

1. Record approved commit, archive SHA-256, package lock SHA-256,
   schema and operator in a release record. Verify a clean artifact and
   target capacity; deny mismatched hashes or dependencies.
2. For a fresh isolated pilot, verify empty pilot roots and never touch
   production data. Only if a later, separately approved migration is
   required: take a consistent source backup and verify a restore to a
   separate location before touching the source environment.
3. Prepare a new release directory with the exact archive and isolated
   runtime. Apply only reviewed environment settings and secrets.
   Do not copy synthetic credentials or test data.
4. If a migration is approved, run its reviewed dry run and backup
   compatibility check, then migrate during the window. If no migration
   is approved or required, do not change the schema.
5. Switch the release pointer atomically to the exact release ID.
   Perform HTTPS health and unauthenticated 401 checks, then a permitted
   owner smoke flow: login, project/import/preview/mapping, job/DXF,
   plan/decision/edit and catalog. Check worker, disk, latency/error
   monitoring and logs for secret leakage.
6. Release owner decides keep or rollback using agreed thresholds. For
   compatible schema, switch code pointer to the previous accepted
   release and verify health and saved data. If state must roll back,
   stop writes and restore the *verified* backup to a fresh root, then
   switch only after integrity and owner/result checks pass. Never
   overwrite the sole backup or perform an unreviewed reverse migration.
7. Record final exact commit, time, checks, observations and operator;
   retain the prior release and backup for the approved retention term.

## Test-environment evidence

GEOAI-039 executes the analogous sequence only on disposable synthetic
data and loopback HTTPS. Its result and any remaining gaps are recorded
in `harness/build/039-release-acceptance.md` and `harness/build-log.md`.
The synthetic checks passed, including fresh-root restore and code
rollback; production capacity, observability and migration status
remain open for owner review.
