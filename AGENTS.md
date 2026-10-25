# AutoCAD Assistance GEO AI

## Current GEOAI-039 handoff (2026-10-25)

The owner reports a passed **synthetic user scenario** on the installed
product `15374b5c856958fdf67c5efdce68db81e05ac92f` plus the separate
operational package `71ab84cba999bcf2fd105b69917cdd1e8907671f`:
import, preview, mapping, calculation, DXF download and opening, and
reopening the project. The owner's remarks field was not filled in; record
remarks as unspecified until clarified. This is user acceptance of that
exact pair and scenario only, not of arbitrary real surveys.

GEOAI-039 remains PARTIAL. The restored VM111 disk was checked offline
without booting its OS, and the guest application dump and Proxmox VM backup
run independently. A `TASK OK` VM archive is a VM-level backup only unless
the matching recent successful application dump is independently verified.
Missing/failed dumps must be visible and must not be reported as a completed
coordinated application backup. Finish an isolated boot/recovery check with
the copied NetBird identity removed, and enforce/verify this backup pairing
before full 039 sign-off. Current feature/PR CI has passed; see
`harness/build/039-release-acceptance.md`. GEOAI-040 stays BLOCKED.
Do not merge PR #6, enable app/TLS boot autostart or expand access.

## VM110 user-pilot handoff (2026-10-25)

The owner's current authorization installed the exact product
`15374b5c856958fdf67c5efdce68db81e05ac92f` and the separately
versioned operational package `71ab84cba999bcf2fd105b69917cdd1e8907671f`
on VM110. Both `geoai-pilot` and `geoai-pilot-tls` are running but disabled
for boot; private HTTPS is `https://geoai.froglight.ru` on NetBird IP
`100.104.46.7`. The original `79528bb` archive, old overlay, config and
primary state remain available for rollback. Do not deploy the PR HEAD.
Direct SSH access is `ssh geoai-pilot`. The root-only owner password is at
`/etc/geoai-pilot/private/owner-password`; never print it in chat or Git.
Proxmox PVE1 now has VM110-only daily `backup-fast-nfs` and weekly
`backup-weekly-nfs` jobs with keep-last 7/4. A guest timer copies application
state before those jobs, retaining at most two local copies. The first VM
archive `vzdump-qemu-110-2026_10_25-18_40_45.vma.zst` succeeded; offline
restore to VM111 succeeded. VM111 is stopped, has no network device and no
autostart. The app-state restore also passed SQLite integrity checks.
Small synthetic HTTPS auth/import/preview/mapping/job/DXF checks passed on the
installed pair. The owner's bounded synthetic user acceptance is now recorded
above; remaining operational recovery and dump-pairing gates keep 039 PARTIAL.
The saved 100,000-point fixture is one measured case, not universal support.
No real data or PR merge occurred. See `PLANS.md` and `harness/build-log.md`
for exact status; certificate renewal still needs manual DNS-01 before
2027-01-23.

## Closed-pilot preparation handoff (2026-10-25)

The selected release remains exact commit
`79528bb9f6070e458724886a915f9d035cdfd110`, not the later
development HEAD. Read `harness/build/039-pilot-preparation.md`,
`harness/build/039-deployment-plan.md` and
`harness/pilot/combined-manifest.json` before GEOAI-039/040 work.
A separately versioned `pilot_ops/` overlay contains the operational
ASGI adapter; never describe it as part of the 79528bb product archive.
The overlay/product/P6 rollback combination passed synthetic loopback
HTTPS checks, but target Caddy/NetBird and load remain unmeasured.
A separate Debian 13 VM 110 `GEOAI` on PVE1 was created by the owner,
with reported DHCP IP `192.168.1.162`, 2 vCPU, 4 GiB RAM and 60 GiB
disk. VM109/CT108 remain separate. VM110 has no NetBird/TLS proxy or
Proxmox backup schedule; the IP is not confirmed stable. TCP/22 is
reachable from Windows, but no trusted host key is recorded, so no
login or independent inventory check was performed.
New empty pilot state needs no
production migration. Project SQLite uses user_version 8, auth SQLite
uses 1; staging manifest schemaVersion 5 is unrelated. The ASGI
overlay is implemented; private HTTPS details, target measurements and
owner sign-off remain gates. Do not launch, merge, change network,
secrets, working data or running services under this preparation scope.

## Purpose and architecture

Build a geodetic platform for field-survey processing, DXF plans, situation,
terrain, a future web UI, and reuse of topographer-confirmed decisions.

Preserve and reuse `bot/`, `dxf_generator/`, `kml_generator/`, `templates/`,
and existing DXF/KML algorithms. Do not rewrite them without a scoped reason.
Telegram and HTTP are adapters around framework-independent services.

## Branch and approval rules

Work on `codex/geo-ai-start` or isolated `codex/geoai-*` pilot/issue branches; never switch to `main`.

Allowed without additional approval:

- Read and edit this repository on the approved feature/pilot branches.
- For the approved autonomous package, make local commits and isolated copies,
  install user-local official tools, run the dispatcher pilot and GEOAI-008–011.
- Create or update tests and phase/build context.
- Use `.venv`; install only previously approved Python dependencies there.
- Run unit, regression, API, lint, and static checks.
- Write task reports only under `/home/geoai/dev-data/`.

The owner's 2026-10-25 continuous-roadmap authorization below explicitly
permits scoped workflow/CI edits, adding the exact GitHub origin if absent,
feature push and draft PR. Other remotes, main/master push, force-push,
merge, rebase, branch-rule changes, production deployment/access,
Proxmox, firewall, VLAN/networking, Docker daemon configuration, secrets,
`.env`, production database/migrations, reset, clean, data deletion,
system packages and `sudo` remain outside this authorization.

Never read or copy production secrets or `.env`; run the production Telegram
bot or database; send survey data to external services without approval;
deploy automatically; or alter measured coordinates to satisfy a test.

## Development workflow

For each approved task:

1. Run a read-only preflight and limit scope.
2. Inspect only relevant existing functions.
3. Define acceptance criteria or a focused test first.
4. Make the smallest change.
5. Run focused tests, then the regression baseline.
6. Run `git diff --check` and report changed files and limitations.
7. Record the exact accepted revision and make a scoped local commit. For
   the authorized roadmap, continue to the next dependency-ready task
   after updating shared memory and checking the remaining run budget.
   After every three tasks, record a checkpoint and continue. Never treat
   a PROPOSED row as ready without a frozen task specification.

Use `scripts/geoai-preflight.sh` and `scripts/geoai-verify.sh` when applicable.
A task is done only when criteria and target tests pass, the regression result
is recorded, out-of-scope production files are unchanged, diff check passes,
and the handoff states remaining limitations.

## Resource and context limits

VM109 has 2 vCPU and about 4 GiB RAM. Use one process/worker, no xdist,
`OMP_NUM_THREADS=1`, and `OPENBLAS_NUM_THREADS=1`. Do not run concurrent heavy
jobs or install large ML frameworks without a separate decision.

Read `PLANS.md` and the approved `harness/build/` phase instead of re-auditing
the repository. Use focused search, one task at a time, short factual reports,
one writable worktree and one compute worker. Do not spawn extra agents.

## Skill usage

Use skills only when materially useful: `review` after significant changes,
`review-security` for auth/upload/API security, `docker-compose-ops` only for
an approved dev Compose task, `linux-server-ops` for authorized VM diagnostics,
and `networking-diagnostics` for an actual network fault.

Do not automatically enable `autopilot`, `loop`, `babysit`, or `split-to-prs`.
Do not install new skills without explicit approval.

## Shared project memory and current handoff

Active accepted-code checkout: Linux VM109,
`/home/geoai/dev-data/geoai-autonomy/workspaces/handoff-final`, branch
`codex/geoai-current`. The original
`/home/geoai/projects/autocad_assistance` checkout stays on
`codex/geo-ai-start` and retains the inherited CI edit.
Keep shared rules/context here, phase status and sequence in `PLANS.md`, and
verified results, Git state, limitations, and the next step in
`harness/build-log.md`. Read all three before continuing; update them after a
phase. Keep raw evidence and task reports under `/home/geoai/dev-data/`.

GEOAI-007C baseline confirmation completed on 2026-10-24 (Europe/Moscow).
Regression 10/10 and API 6/6 passed; pip and diff checks passed. The product
baseline was locally committed as `c33340366ee4016a7e2d2576bb9c46931875db16`.
The initial documentation handoff is `d56f0f4d31e340874e731805e79c52b135b122b6`;
use `git log -1` for later documentation-only state commits.
Both are recoverable from the verified bundle/bare store under
`/home/geoai/dev-data/geoai-autonomy/`. No Git remote is configured. The
inherited `.github/workflows/cicd.yml` edit remains uncommitted and must be
preserved. GEOAI-007A/007B specifications were absent at that point and
outside the approved autonomous package.

Use isolated bootstrap runners via `scripts/geoai-verify.sh`. Direct unittest
discovery is incompatible with the regression isolation guard. The inherited
CI workflow still uses direct discovery and needs a separately approved fix.
The local passing baseline does not establish CI or deployment readiness.

## Approved autonomous package (2026-10-25, Europe/Moscow)

The owner authorized local commits, user-local official tool installation, an
isolated pilot and sequential GEOAI-008–011 execution, with Codex accepting
Cursor's implementation. This overrides the earlier one-phase stop rule only
for this agreed package. GEOAI-007A/007B had no recorded acceptance criteria
for that package and were not included. Production deployment, publishing code, merge to
main, destructive data changes and sending survey data externally remain out
of scope. No `.env` or production secrets may be read or copied.

The controller must protect its workflow, state and frozen acceptance checks
outside disposable worktrees; allow only one Cursor worker; persist a 30-minute
per-task and two-hour package active-time budget across restarts; allow at
most two returns for repair; and mark exhausted/blocked work BLOCKED without
automatic retry. Codex must inspect the actual diff, run independent checks
and preserve an accepted commit in the separate local Git store before the
GitHub Issue is closed. Acceptance is bound to the checked file revision.

The VM109 SSH connection now uses the saved pinned host key per the owner's
latest instruction. The previously requested independent Proxmox-console
comparison has not been performed; record this as a remaining limitation.

Current handoff (2026-10-25, Europe/Moscow): the approved autonomous package
is COMPLETE locally. Pilot and GEOAI-008–011 passed protected acceptance,
Codex review, local commit preservation in the separate bare Git store, and
verified bundles. Accepted product commits: 008
`aec7fdad107cc1e4382b97f2d3218129e80dbccc`, 009
`10cd7ff75cc44eacfd38d2df937605f82f64a688`, 010
`5c5915fbb3e6df07a1a7b2d1d3a73d8a02750564`, 011
`b78b1f591244f04c6652c9fe857b93d282f134ec`. GitHub Issues #2–#5 are
closed. Exact digests, counts, repairs and bundle hashes are in
`harness/build-log.md`. No code was pushed, merged or deployed.

Symphony and the protected broker were stopped after the final Issue closed;
the package-specific `@reboot` crontab was removed, with its prior entry
saved under the protected control directory. Do not queue additional Issues
or restart the dispatcher without a new approved scope and frozen checks.
The original checkout still has the inherited uncommitted CI workflow edit.
Local passing tests do not establish CI/deployment readiness. Independent
Proxmox host-key comparison and actual reboot recovery were not performed.
The development API has no ownership/auth layer; deployment, retention and
resource quotas remain later work.

## P0 preparation handoff (2026-10-25, Europe/Moscow)

The new roadmap assigns GEOAI-007A/007B to P0 and proposes GEOAI-012–040;
these numbers were checked against `PLANS.md` and were unused. The roadmap
does not queue work. GEOAI-007A local evidence reconciliation is complete:
accepted commits are ancestors of `codex/geoai-current` at `bbf6f66`,
its final bundle passed verification, and the original inherited workflow
edit was saved byte-for-byte with SHA-256 outside the repository under
`/home/geoai/dev-data/geoai-autonomy/p0-007a/`. An off-VM copy is not
confirmed. No product tests were rerun for the evidence-only audit.

GEOAI-007B is specified in `harness/build/007b-ci-github.md`. Its former
direct-discovery and VM-path problems are being addressed under the
continuous-roadmap authorization below. Main-rule changes and deployment
remain separate.
Use `PLANS.md` for the proposed dependencies and status; use
`harness/build-log.md` for exact 007A hashes and current Git state.

Current P0 handoff: 007B is accepted at `49dea8a`. A clean venv passed
58 focused, 10 isolated regression and six isolated API tests, with zero
blocked operations. A temporary failing test made the runner fail; direct
regression discovery still failed as required. The separate feature/PR
workflow has read-only contents permission and no production jobs; the
existing production workflow is unchanged. GitHub push and draft PR #6
both produced successful CI runs at the exact code SHA. The branch and
inherited workflow also have verified copies on Windows outside VM109.
P0 is complete; the next task is GEOAI-012 after a frozen spec.

GEOAI-012 is accepted at `608a8e3`. Its local gate passed: 67 focused,
10 isolated regression and six isolated API tests, plus pip/diff checks.
The new shared model preserves raw XYZ, source provenance and explicit
unknown unit/CRS context; HTTP and Telegram DXF paths use it. No coordinate
transformation or unit inference is implemented. GitHub push and PR checks
succeeded at the exact accepted SHA. A three-task checkpoint covering
007A, 007B and 012 is recorded in the build log. Next task GEOAI-013
is READY under `harness/build/013-upload-guard.md`.

GEOAI-013 is accepted at `66b8dcc` on the feature worktree. Uploads now
reject binary/disguised content and bound rows, lines, columns, fields,
KML elements and coordinate tuples. Preview, mapping and DXF read one
UUID-named regular file through bounded no-follow descriptors. The final
local run passed 74 focused, 10 isolated regression and six isolated API
tests with zero blocked operations, plus pip and diff checks. GitHub
push run 40146687136 and PR run 40146689779 both succeeded. GEOAI-014
is READY under `harness/build/014-bounded-jobs.md`. The
P1 deadline is 2026-10-25T04:12:17Z, with one worker and no external
executor spend.

GEOAI-014 is accepted at `0ad1e0a`. The local DXF job coordinator uses one
Linux-locked compute process, four waiting slots, a 120-second timeout,
25 MiB result cap, 32 MiB request cap and at most two explicit retries.
It cancels/terminates child work, records interrupted jobs for explicit
retry after restart, and publishes results atomically. The final gate
passed 83 focused, 10 isolated regression and six isolated API tests,
with zero blocked operations, plus pip and diff checks. GitHub push run
40147083698 and PR run 40147086595 succeeded. P1 is complete; the
012–014 checkpoint is in the build log. GEOAI-015 is READY under
`harness/build/015-project-storage.md`. P2 deadline is
2026-10-25T04:33:23Z with one worker and zero external executor spend.

GEOAI-015 is accepted at `a0e82bc` after one CI repair. A separate SQLite project store preserves
immutable source revisions, exact settings/job parameters, hashes,
algorithm labels and verified DXF results under server UUID paths.
No project HTTP routes or Telegram database changes were made. The final
local run passed 92 focused, 10 isolated regression and six isolated API
tests, with zero blocked operations, plus pip and diff checks. GitHub
push run 40147682109 and PR run 40147684816 passed at that SHA.
GEOAI-016 is READY under `harness/build/016-owner-auth.md`; 017 remains
PROPOSED. The initial 015 push run exposed a cancellation cleanup race;
the repair and exact CI evidence are in the build log.

GEOAI-016 is accepted at `04522be`. An opt-in owner identity store uses
scrypt, one-time local provisioning, bounded login attempts, revocable
idle/absolute sessions, a Secure/HttpOnly/SameSite cookie, trusted HTTPS
origin and CSRF checks. The Telegram link requires a one-time code plus
a private bot update from a configured admin ID. No real credentials or
link were created; existing upload/DXF routes still await 017 ownership
gates. The final run passed 104 focused, 10 isolated regression and six
isolated API tests, zero blocked operations, pip and diff checks. GitHub
push run 40148311053 and PR run 40148314247 passed at that SHA.
GEOAI-017 scope is frozen under `harness/build/017-resource-ownership.md`.

GEOAI-017 is accepted at `f3bee9c`. Opt-in authenticated API mode requires
an explicit project root and checks an HTTPS owner session for every
resource request before body parsing; mutations require exact Origin
and CSRF. Schema v2 assigns UUID owners to new projects and uploads;
legacy v1 projects remain unowned and inaccessible through scoped reads.
Source/result downloads and upload preview/mapping/DXF verify ownership,
with identical 404 for foreign and missing IDs. The local gate passed
107 focused, 10 isolated regression and six isolated API tests with zero
blocked operations, plus pip and diff checks. GitHub push run 40148828172
and draft PR run 40148831218 succeeded at that SHA. P2 is complete.
The legacy no-auth app factory mode remains for the isolated
regression baseline; it is not a private cabinet deployment mode.
GEOAI-018 is accepted at `8ed5687` under `harness/build/018-resource-limits.md` from
accepted 017. P3 deadline is 2026-10-25T05:01:04Z with one writable
worktree/compute worker, 90 minutes per task, two repair cycles and
zero external executor spend. Retention remains opt-in and cleanup
must be explicit and limited to expired temporary uploads. The final
local gate passed 113 focused, 10 isolated regression and six isolated
API tests, zero blocked operations, pip and diff checks. Version-4
project metadata never assigns an expiry to migrated uploads with
unknown age. A persistent cleanup journal records apply outcomes.
The first 018 GitHub push/PR runs passed at `52b794f`; the journal
repair passed push run 40149469271 and PR run 40149474159 at `8ed5687`.
No real data cleanup or production migration ran. GEOAI-019 is accepted
at `897cf60` under `harness/build/019-import-screen.md` from this accepted
base. It uses the existing parser, authenticated project store and a
small same-origin browser screen; no new frontend runtime is required.
The final run passed 116 focused, 10 isolated regression and six isolated
API tests, zero blocked operations, pip and diff checks. A disposable
browser fixture confirmed login, session recovery, project creation,
CSV preview, mapping, context and one revision after a double click.
GitHub push run 40150237735 and PR run 40150241097 passed at that SHA.
No production deployment occurred. GEOAI-020 is READY under
`harness/build/020-jobs-results.md` from this accepted base. It uses
014's one bounded child process and requires an explicit jobs root;
submission/retry need a durable, client-owned idempotency key.

GEOAI-020 is accepted at `91aeb53` after local and GitHub feature/PR
checks. The opt-in jobs root starts one coordinator; schema v5 binds
owner, revision, exact request hash and client UUID to one job before
queue admission. Status, explicit cancel/retry and verified DXF results
are exposed to the authenticated cabinet. A disposable browser run
confirmed one job after a double click and preserved history after reload.
P3 is complete; P4's finite manifest and GEOAI-021 frozen scope are in
`/home/geoai/dev-data/geoai-autonomy/p4-run-manifest.json` and
`harness/build/021-web-mvp-acceptance.md`. No production worker or
deployment is authorized.

GEOAI-021 is accepted at `eecaad8` after local and GitHub feature/PR
checks. Its acceptance uses one fixed synthetic CSV through the
authenticated web API and offline Telegram handlers. It compares exact
measured rows and DXF model-space entities, including block scales,
layers, labels and TIN, then rejects a deliberately changed point.
The test exposed and corrected the web 1:500 render factor mismatch;
`harness/build/021-web-mvp-acceptance.md` records raw timing/memory
evidence. GEOAI-022 is READY under
`harness/build/022-staging-recovery.md`; VM109 has no Docker, so use
the verified Python runtime and only disposable synthetic staging
roots. No system package, production service or real data operation.

GEOAI-022 is locally verified at candidate `922dc0d`: a clean Git
archive and exact Python lock built disposable loopback HTTPS staging;
an authenticated synthetic import produced a DXF. Offline backup,
compatible 021 code rollback, and fresh-root restore preserved owner,
project, source and result checksums. A tampered backup and a backup
attempt during active service were rejected. The test server is stopped.
The repaired-commit gate passed 124 focused, 10 isolated regression
and six isolated API tests; exact GitHub feature/PR checks are pending.
See `harness/build/022-staging-recovery.md`; on acceptance,
close P4 and freeze GEOAI-023 from the accepted base. No production
deployment or real-data operation is authorized.

GEOAI-022 is accepted at `211cf18` after exact GitHub feature and
draft PR #6 checks passed. P4 is complete. GEOAI-023 is READY under
`harness/build/023-plan-viewer.md`; its P5 manifest is in
`/home/geoai/dev-data/geoai-autonomy/p5-run-manifest.json`. Preserve
owner-scoped result integrity and measured local XYZ while adding the
browser plan viewer. No production publication is authorized.

GEOAI-023 is locally verified from accepted 022: bounded DXF plan
JSON, owner-scoped `/api/v1/jobs/{job_id}/plan`, SVG layer/selection/
zoom/pan viewer and explicit unsupported geometry. The synthetic
HTTPS API and browser rendering both passed; large local XYZ remained
visible and unchanged. The final local gate passed 127 focused, 10
isolated regression and six isolated API tests; exact GitHub
feature/PR checks are pending. Details and numerical bounds are in
`harness/build/023-plan-viewer.md`. No production state was touched.

GEOAI-023 is accepted at `24dad9c` after exact GitHub push and draft
PR #6 checks passed. GEOAI-024 is READY under
`harness/build/024-line-candidates.md` from that base. It compares
recorded survey order with the existing nearest-neighbor line builder
for eligible code groups, returning explicit A/B candidates and
reasons without accepting either or changing measured XYZ/DXF. P5
bounds remain in `/home/geoai/dev-data/geoai-autonomy/p5-run-manifest.json`.

GEOAI-024 is accepted at `cbcd0f3`: A uses immutable survey-row order and
B reuses the existing line builder's anchored nearest-neighbor order.
The owner-scoped comparison carries provenance, point IDs/XYZ,
descriptive lengths and reasons; it cannot select or persist a
decision. The fixed zigzag, browser comparison, old/new DXF semantic
parity and 131 focused + 10 regression + six API tests passed. Exact
GitHub feature/PR runs 40154016183/40154019673 passed. GEOAI-025 is
READY from this base under `harness/build/025-decisions.md`: versioned,
owner-scoped decisions and immutable DXF-job snapshots. No production
data changed.

GEOAI-025 is accepted at `43fe740` from accepted 024: owner-scoped,
append-only line decisions (A/B/skip/manual), safe repeated requests,
version conflicts and page-limited history; new project jobs snapshot
accepted A/B row orders, while prior jobs and original measurements
remain unchanged. Synthetic HTTPS API/DXF and browser control checks
passed; final gate passed 133 focused + 10 isolated regression + six
API tests. Exact GitHub feature/PR runs 40154708051/40154711826
passed. P5 tasks 023–025 are accepted. GEOAI-026 is READY under
`harness/build/026-line-edits.md` and the P6 manifest. GEOAI-027
requires explicit reference provenance and data rights; no production
migration or deploy.

GEOAI-026 is accepted at `6285b1a` from accepted 025: an owner-scoped,
versioned line-edit model supports explicit reorder/split/join/move,
undo and reset, with unchanged source XYZ and code. New project jobs
snapshot the saved segments; stale A/B decisions require explicit
reset, and prior jobs remain fixed. Synthetic HTTPS DXF, browser,
breakline and 137 focused + 10 isolated regression + six API tests
passed. Exact GitHub push/PR runs 40155918471/40155921751 passed.
GEOAI-027 is READY under `harness/build/027-reference-archive.md`:
private immutable references with explicit provenance and permission
evidence, synthetic fixtures only for development. No production action.

GEOAI-026 integration correction is accepted: the web HTML
referenced `/app/line-edits.js` but the FastAPI static route was
missing. The route and focused regression test are added; the repeat
full gate passed 137 focused + 10 regression + six API tests. Exact
feature/PR CI passed at `5880fea3b9341ba371baa429fab9364cb87a1aac`
(push 40156349260, PR 40156351787). GEOAI-027 can proceed.

GEOAI-027 is accepted at `f618613` with schema v8 and private,
owner-scoped reference DXF archive. Five focused archive tests and the
full current gate (144 focused, 10 regression, six API) passed; verified
HTTPS synthetic upload/download and exact push/PR CI
40156949699/40156952551 passed. No real references or rights records
were supplied. GEOAI-028 is READY with a bounded exact diagnostic
comparison under `harness/build/028-dxf-comparison.md`.

GEOAI-028 is accepted at `1ea061c`: owner-only, read-only comparison of a
saved job DXF against a separately supplied archive reference. It
reports exact discrepancies and unsupported entities, without an
invented geodetic tolerance. Five focused comparison tests, 149 total
focused + 10 regression + six API, verified HTTPS and exact feature/PR
CI 40157505101/40157509671 passed. P6 checkpoint is complete: three
tasks accepted, feature worktree clean, original checkout unchanged.
Next candidate GEOAI-029 can derive a versioned dictionary from the
existing SinoKOD template and generator mappings without inventing
object semantics.
P7 manifest is active with one worker/worktree, at most two repairs
per task, 90 minutes per task and deadline 2026-10-25T07:20:40Z.
GEOAI-029 READY under `harness/build/029-object-catalog.md` from
committed SinoKOD and generator config, with ambiguity preserved.
GEOAI-029 is accepted at `79528bb`: immutable `object-code-v1` snapshot,
75 SinoKOD rows, source hashes, explicit block/line/special settings,
unmapped/ambiguous codes visible. Four catalog tests, 153 focused +
10 regression + six API, verified HTTPS and exact push/PR CI
40158200653/40158204850 passed. No new object taxonomy was invented.
GEOAI-030 may run an offline synthetic experiment, but real held-out
validation requires authorized reference objects and class criteria.
GEOAI-030 has a bounded offline synthetic experiment READY under
`harness/build/030-tracing-experiment.md`; its fixture is frozen by
whole object in `harness/fixtures/030-synthetic-objects.json`.
Keep the candidate out of production DXF/jobs. Full 030 acceptance
needs authorized real held-out references and class-level criteria.
GEOAI-030 synthetic local gate passed with a review-only 2-opt
uncrossing candidate: one held-out object improved 2/4 → 4/4 exact
edges and a valid crossing regressed 5/5 → 3/5. The candidate never
changes jobs or DXF. Three focused tests, 156 total focused, 10
regression and six API plus exact push/PR CI
40158735797/40158740954 passed. Full 030 and 031
remain blocked until authorized real objects and per-class criteria
are supplied. Continue only independent dependency-ready work.
P7 checkpoint recorded; 029 and the bounded 030 experiment are
accepted, while full 030/031 are blocked on domain evidence.
P10 manifest is active for independently ready GEOAI-036 with one
task, 90 minutes, at most two repairs and deadline
2026-10-25T07:37:48Z. Its read-only dataset-readiness report must
never treat user-asserted permission as independently verified or
export archive contents. GEOAI-037/038 require a passing later audit.
GEOAI-036 local implementation is a read-only, owner-scoped metadata
audit at `/api/v1/dataset-readiness`. Its full local gate passed 157
focused, 10 isolated regression and six API tests, `pip check`, zero
blocked operations and diff check. Verified HTTPS synthetic smoke
passed authentication, privacy and not-ready checks. User permission
assertions are not independent verification; both readiness flags remain
false. Exact feature push and PR CI 40159298332/40159301340
passed at `e5663fa`; GEOAI-036 is accepted. P10 037/038 remain
blocked pending real approved examples and a passing later audit.
P8 032 preflight found `surface.py` only draws breaklines, while
SciPy Delaunay triangulates the points without constraints. Do not
claim a constrained TIN until a suitable licensed implementation,
analytical/reference surfaces and specialist review are available.
P9 034/035 require owner-provided document forms and numerical rules.
An owner-provided completed real DXF was received for GEOAI-030 and
inspected read-only in private VM109 staging outside Git. The 202.6 MB
ASCII DXF is internally parseable and contains survey/terrain and plan
entities, but the original TXT/CSV is unavailable. Do not treat this
DXF alone as an independent source/reference pair or as permission for
training/publication. Full 030/031 still need source-to-object mapping,
approved comparison use, whole-object splits and class criteria.
Private exact XY inspection found that finished plan vertices almost
never coincide with `POINT` entities on major layers. Do not infer a
field-source mapping or any positional tolerance from this alone.
GEOAI-039 release review selects exact `79528bb` containing accepted
P0–P6 and 029 only; do not deploy the later development HEAD as this
release. Its disposable synthetic gate passed 151 focused, 10 isolated
regression and six API tests, verified HTTPS workflows, checksum-locked
build, offline backup, fresh-root restore and compatible code rollback.
The bounded VM110 synthetic session passed private HTTPS from the approved
desktop, 100 API requests, 20/20 small jobs, ~1 MiB/10k-point DXF, restart
persistence and a 136-file off-VM restore. A 100k-point, 10,000,026-byte
input was admitted but its DXF job failed at the exact product's 25 MiB
output file limit (`WORKER_FAILED`). GEOAI-039 remains PARTIAL: the owner
must choose a narrower verified pilot scope or a separately reviewed
release, then sign off. Both pilot units are stopped/disabled; SSH,
nftables and NetBird remain active. The root-only owner password is at
`/etc/geoai-pilot/private/owner-password` on VM110; never print it in
chat or Git. Do not treat VM109's temporary synthetic restore copy as the
approved long-term backup destination. 040 publication, merge and
production migration are not authorized. See
`harness/build/039-vm110-pilot-execution.md`,
`harness/build/039-release-acceptance.md` and
`harness/build/missing-materials.md`.
The owner chose a separate corrected candidate without shrinking the pilot
boundary. Product `15374b5c856958fdf67c5efdce68db81e05ac92f` is a
direct child of `79528bb`; compatible operational package
`71ab84cba999bcf2fd105b69917cdd1e8907671f` adds its archive to the
allowlist and enforces a 2.5 GiB systemd cap. The saved 100k synthetic
fixture passed on VM110 in 33.34 s with a 78,585,786-byte DXF and
925.7 MiB cgroup peak. This verifies that fixture only. Candidate state
was isolated, backed up and restored; the original config/overlay/unit
were restored afterward. Both pilot services are stopped and disabled.
GEOAI-039 remains PARTIAL pending owner acceptance and implementation of
the selected Proxmox backup schedules. See
`harness/build/039-100k-release-manifest.json` and the updated VM110 report.
Do not repeat synthetic 030 experiments without a new falsifiable
hypothesis; keep the current generator unchanged. Resume 030/031 or
037/038 only when the evidence gates in `PLANS.md` are met.

## Continuous roadmap authorization (2026-10-25, Europe/Moscow)

The owner authorized sequential P0, P1–P4 and later dependency-ready local
tasks without a pause at package boundaries. P11 publication, production
deployment and production migration still require separate authorization.
Within scoped tasks, source/tests/docs/queue and workflow/CI changes are
allowed; use portable isolated bootstraps, run focused plus full current
regression/API and negative checks, inspect diff, then make local commits.
Push only tested commits to `codex/geoai-current` in
`PKG89/autocad_assistance`; create/update only its draft PR. Before first
push, verify exact remote and workflow events cannot publish or deploy for
that feature push. Never push main/master, force-push, merge or rebase.

For a PROPOSED task, first verify dependencies, freeze base HEAD, allowed
files/non-goals, acceptance checks, actual commands, budget and stop
conditions in `harness/build/`; then mark READY. Do not invent geodetic
tolerances, document forms, data rights or access. Keep one executor, one
writable worktree and one compute worker, with at most two repair cycles per
task. Preserve time/spending limits in a manifest before a run. On a blocker,
record ID, HEAD, diff, checks and missing action, then continue only
independent authorized work. Update `PLANS.md` and
`harness/build-log.md` after each task and checkpoint every three tasks.
