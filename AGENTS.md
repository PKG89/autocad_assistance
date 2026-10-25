# AutoCAD Assistance GEO AI

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
59 focused, 10 isolated regression and six isolated API tests, with zero
blocked operations. A temporary failing test made the runner fail; direct
regression discovery still failed as required. The separate feature/PR
workflow has read-only contents permission and no production jobs; the
existing production workflow is unchanged. GitHub push and draft PR #6
both produced successful CI runs at the exact code SHA. The branch and
inherited workflow also have verified copies on Windows outside VM109.
P0 is complete; the next task is GEOAI-012 after a frozen spec.

GEOAI-012 is accepted at `608a8e3`. Its local gate passed: 68 focused,
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
local run passed 75 focused, 10 isolated regression and six isolated API
tests with zero blocked operations, plus pip and diff checks. GitHub
push run 40146687136 and PR run 40146689779 both succeeded. GEOAI-014
is READY under `harness/build/014-bounded-jobs.md`. The
P1 deadline is 2026-10-25T04:12:17Z, with one worker and no external
executor spend.

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
