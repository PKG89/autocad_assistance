# AutoCAD Assistance GEO AI

## Purpose and architecture

Build a geodetic platform for field-survey processing, DXF plans, situation,
terrain, a future web UI, and reuse of topographer-confirmed decisions.

Preserve and reuse `bot/`, `dxf_generator/`, `kml_generator/`, `templates/`,
and existing DXF/KML algorithms. Do not rewrite them without a scoped reason.
Telegram and HTTP are adapters around framework-independent services.

## Branch and approval rules

Work only on `codex/geo-ai-start`; never switch to `main`.

Allowed without additional approval:

- Read and edit this repository on the current feature branch.
- Create or update tests and phase/build context.
- Use `.venv`; install only previously approved Python dependencies there.
- Run unit, regression, API, lint, and static checks.
- Write task reports only under `/home/geoai/dev-data/`.

Always require explicit approval for commit, push, merge, rebase, remotes,
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
7. Stop. Do not begin the next GEOAI task automatically.

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
and no extra agents unless they provide necessary value and are permitted.

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

GEOAI-007C baseline confirmation and commit preparation completed on
2026-10-24 (Europe/Moscow). Regression 10/10 and API 6/6 passed; pip and diff
checks passed. HEAD remains `36f49b2a2ee5a412a1e5a2c5e8fdc275fcafb3be`;
changes are uncommitted, index empty, no remote configured.
Next candidate: GEOAI-007A, then 007B, then 008 through 011. The scope and
acceptance criteria for 007A/007B are not yet recorded in this checkout;
recover their task definitions before implementation. Follow the existing
one-phase stop rule and approval rules above.

Use isolated bootstrap runners via `scripts/geoai-verify.sh`. Direct unittest
discovery is incompatible with the regression isolation guard. The inherited
CI workflow still uses direct discovery and needs a separately approved fix.
The local passing baseline does not establish CI or deployment readiness.
