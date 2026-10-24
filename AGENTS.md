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

Always require explicit approval for push, merge, rebase, remotes,
`main`, `.github/workflows/`, CI/CD, production access, Proxmox, firewall,
VLAN/networking, Docker daemon configuration, secrets, `.env`, database
migrations, reset, clean, data deletion, system packages, or `sudo`.

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
7. Stop unless the approved autonomous controller has independently accepted
   and preserved the result. For the approved 008–011 package, it may then
   dispatch the next task in order. Never expand the package automatically.

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
and no extra agents except the single approved Cursor executor managed by
the autonomous controller.

## Skill usage

Use skills only when materially useful: `review` after significant changes,
`review-security` for auth/upload/API security, `docker-compose-ops` only for
an approved dev Compose task, `linux-server-ops` for authorized VM diagnostics,
and `networking-diagnostics` for an actual network fault.

Do not automatically enable `autopilot`, `loop`, `babysit`, or `split-to-prs`.
Do not install new skills without explicit approval.

## Shared project memory and current handoff

Execution checkout: Linux VM109, `/home/geoai/projects/autocad_assistance`.
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
preserved. GEOAI-007A/007B specifications are absent; they are outside the
approved autonomous package.

Use isolated bootstrap runners via `scripts/geoai-verify.sh`. Direct unittest
discovery is incompatible with the regression isolation guard. The inherited
CI workflow still uses direct discovery and needs a separately approved fix.
The local passing baseline does not establish CI or deployment readiness.

## Approved autonomous package (2026-10-25, Europe/Moscow)

The owner authorized local commits, user-local official tool installation, an
isolated pilot and sequential GEOAI-008–011 execution, with Codex accepting
Cursor's implementation. This overrides the earlier one-phase stop rule only
for this agreed package. GEOAI-007A/007B have no recorded acceptance criteria
and are not in this package. Production deployment, publishing code, merge to
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

Current handoff (2026-10-25, Europe/Moscow): Cursor Agent CLI is authenticated
and has completed real isolated work. The disposable pilot passed a deliberate
negative gate, Codex review/feedback, Cursor repair, independent recheck,
stop/resume and preservation. Accepted pilot commit is
`08bdbad32799ad48cb6f8df3eaad37d562fb7aa9` in the separate bare Git
store and verified bundle. GEOAI-008 was then implemented by Cursor and
accepted as `aec7fdad107cc1e4382b97f2d3218129e80dbccc` after 13 focused,
six frozen, 10 regression and six API tests passed. This commit is local only;
the separate bare store and verified bundle preserve it. GitHub Issue #2 is
closed with that limitation recorded. GEOAI-009 (#3) is next and must start
from the accepted 008 commit. Issues #3–#5 still carry `geoai-planned` only.
The repository-scoped GitHub Issues token on VM109 passed authenticated read
and idempotent write probes. Symphony WORKFLOW remains a draft until the
protected dispatch/broker and disconnect-survival checks pass; do not add
`geoai-queue` or report the autonomous service RUNNING before those gates.
