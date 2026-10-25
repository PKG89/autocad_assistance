# GEOAI-039 — acceptance of the bounded GEO AI web release

Status: PARTIAL after disposable acceptance. Frozen source HEAD `75b02ebe31322723f87ec3483dab8d70465dc0ed`;
release candidate `79528bb9f6070e458724886a915f9d035cdfd110` is its ancestor.
Accepted dependencies 018, 021, 022 and selected P0–P6, 029 passed their
exact feature/PR checks. The candidate precedes the offline 030 experiment
and 036 API and is the exact approved feature set for this acceptance.

## Scope and exclusions

Release functions: survey import/preview/mapping, bounded jobs and DXF,
private projects/auth/ownership, storage quotas and cleanup, browser plan
viewer, A/B candidates and recorded decisions, reversible derived-geometry
edits, private reference archive, exact DXF comparison and read-only
object-code catalog. Preserve Telegram/shared DXF behavior.

Exclude experimental 030, unaccepted 031–035, and 037–038. GEOAI-036 is
accepted as a readiness report but is outside this chosen release; its
acceptance does not approve a training dataset. GEOAI-040 publication
requires separate authorization. No real user data or production systems.

Allowed files: this spec, a release/materials checklist, `PLANS.md`,
`AGENTS.md`, `harness/build-log.md`, and a small acceptance test only if a
specific missing check is found. No product algorithm, DB migration,
deployment workflow or system service changes.

## Exact checks

1. Verify candidate ancestry, clean source checkout, matching Python 3.13
   package lock, successful deterministic build and archive/file checksums.
   Run the test suite on a separate extracted copy of that same Git
   archive: a focused Telegram import writes `bot_shutdown.log`, so
   executing tests inside the checksum-verified staged release would
   invalidate it. Re-verify the staged release after all checks.
2. On candidate code with disposable synthetic data, pass the current
   focused, isolated regression and API gates. Exercise HTTPS owner
   creation/login, project/upload/preview/mapping/job/DXF, plan and accepted
   line workflow; anonymous/foreign resource access must fail.
3. Test upload, queue/compute and storage limits. Inspect negative cases
   for path traversal and unsupported/oversized files. Keep one worker.
4. Build and activate an older accepted, schema-compatible P6 release for
   code rollback. Verify HTTPS health and saved synthetic data remain
   readable. Stop server, create an offline backup, restore to a fresh
   root, verify checksums/SQLite and synthetic owner/result. Reject a
   corrupted backup without mutating an existing stage. Record the
   rollback command sequence and its prerequisites.
5. Record measured runtime and memory for a fixed synthetic workload,
   check logs for credentials/request bodies, and verify that all server
   processes stop. `git diff --check` and exact feature/PR CI are required
   for the documentation commit.

## Budget and stop conditions

Manifest: `/home/geoai/dev-data/geoai-autonomy/p11-039-run-manifest.json`.
One worker and one writable feature worktree, 90 minutes/task, four-hour
package ceiling, at most two repairs, $0 external executor spend. Stop
on unexpected edits, lost test isolation, failed dependency, insufficient
resources, data-rights uncertainty, budget exhaustion, or any production
action. A failed criterion leaves 039 PARTIAL/BLOCKED with exact evidence.

## Disposable acceptance result (2026-10-25)

- Dependency gate passed. The exact candidate is an ancestor of source
  HEAD and had successful push/PR CI 40158200653/40158204850.
  Rebuilt Git archive SHA-256
  `cada7fb4f2919fe321cffbe74beeec499bc60e833e33f36a94f404560f91ce81`
  matched. Python 3.13.5, staging-manifest schemaVersion 5 (not the
  SQLite database version), and package-lock SHA-256
  `d8d2cf3756f29f64246f133f694ee61aa9711f8eb8e95c4fd2039734d381c351`
  matched. 030 and 036 code are absent from the candidate.
- The first test run wrote a Telegram shutdown log into a staged
  release; immutable verification caught it. Tests were moved to a
  separate extracted copy of the same archive. An owner-seeding import
  later wrote three `__pycache__` files; exactly these files were
  removed and the staged manifest reverified. All subsequent Python
  runs disabled bytecode writes. The final stage stayed immutable
  throughout HTTPS and backup tests. No product code was changed.
- The final isolated gate passed 151 focused, 10 regression and six
  API tests, `pip check`, with zero blocked operations. The fixed
  synthetic import/job smoke completed in 2.441 seconds. Focused
  negative tests covered queue capacity and a single worker (9),
  storage/retention limits (6), upload/path protections (7) and
  ownership (3). Browser plan JSON, A/B decisions, line edits,
  reference archive, DXF comparison and 75 catalog codes passed
  verified HTTPS. The plan correctly reported three unsupported
  LWPOLYLINE bulges from the chosen fixture.
- Anonymous project/plan/catalog/comparison access returned 401;
  the configured stage permits one provisioned owner. Cross-owner
  rejection was exercised in focused tests with separate auth roots.
  Sampled server high-water memory after the main workflow was
  331,564 kB. This is a small synthetic fixture, not a production
  load measurement. Stage logs were empty; no credential or request
  body was written there.
- Active-service backup refused. Offline backup contained 339 files;
  manifest SHA-256
  `b6580c757fc332649e5a8b072f36a337b5a7298e24d32ab310d7a670bc1f461e`.
  Switching to compatible P6 commit `1ea061c1afb4b75b0aba06ae67d402b0a3e815a6`
  preserved HTTPS health and synthetic source/DXF SHA-256. Restore to
  a fresh root passed release-integrity and owner/result HTTPS checks.
  A corrupted backup was rejected before target creation. All test
  servers stopped.

Final 039 sign-off still needs a named target/environment, acceptable
capacity/error thresholds, monitoring and on-call owner, reviewed
migration/no-migration decision, and release-owner approval. These
cannot be inferred from the disposable test. GEOAI-040 remains blocked.
The proposed separate-VM pilot and no-migration decision for new empty
state are in `harness/build/039-pilot-preparation.md`; their target
measurements and owner decisions remain open. Project SQLite is
user_version 8 and auth SQLite is user_version 1.

## Exact corrected pair: owner scenario and current sign-off (2026-10-25)

The current installed pilot is product
`15374b5c856958fdf67c5efdce68db81e05ac92f` plus the separate
operational package `71ab84cba999bcf2fd105b69917cdd1e8907671f`.
This section supersedes the historical pending-owner statement above.
The owner reports that the synthetic user scenario passed: import,
preview, mapping, calculation, DXF download and opening, and reopening
the project. The remarks placeholder was not completed; remarks are
**unspecified**, not confirmed absent. This accepts only that installed
pair and scenario. It does not establish quality for real surveys or
all possible 100,000-point inputs.

The direct target checks in `039-vm110-pilot-execution.md` covered the
saved 100,000-point synthetic fixture, resource bounds, private HTTPS,
owner/anonymous/foreign access, persistence, checksums and app-state
recovery. The selected release excludes experimental 030 and incomplete
031–035/037–038. On PR #6 head
`183c974965df3df219a74e7a5f8587f0dd36127f`, both GitHub `tests`
checks completed with `success` (Actions runs 40209218399 and
40209213596). This CI result applies to that exact PR head; a later
documentation commit requires its own CI result.

**Overall GEOAI-039: PARTIAL, not closed.** The first Proxmox VM110 archive
restored its 60 GiB disk into stopped, network-disconnected VM111, but the
guest OS was never booted. An application-state copy separately restored
with SQLite integrity checks. These are distinct recovery checks, not a
booted end-to-end VM recovery. The guest dump timer and Proxmox jobs run
at separate times without a hard dependency. `TASK OK` for a VM backup
therefore counts only as a VM archive. A coordinated application backup
requires a successful, verified, recent dump matched to that VM run. A
missed/failed dump must produce an observable failure and cannot be counted
as a successful coordinated copy even when the VM archive succeeds.

Remaining acceptance checks:

1. In isolation, boot a restored VM with the copied NetBird identity
   removed and no route to the working network; verify app/state start,
   synthetic owner/project/DXF, then stop the test VM. Preserve the
   offline VM111 evidence and do not expose two identical VPN identities.
2. Add and verify a VM110-specific dump/VM-backup pairing check or hard
   pre-backup gate. Record dump identifier, validity/timestamp, VM archive
   identifier and task result together; fail closed for a skipped or
   failed dump, and make the failure visible to an operator. Test both
   success and failure paths without changing other VM backup jobs.
3. Resolve the unspecified owner remarks before recording them as `none`
   or as tracked findings. The bounded synthetic user acceptance itself is
   recorded above and does not need to be repeated.

GEOAI-040 remains blocked. PR merge, boot autostart, public or wider VPN
access, and real-data use are not authorized by this user check.
