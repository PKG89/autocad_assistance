# Build log

Keep one concise entry per task. Do not paste full command output.

## HARNESS-001

- Working state: `codex/geo-ai-start` at
  `36f49b2a2ee5a412a1e5a2c5e8fdc275fcafb3be`, with recovered and GEOAI-006/007
  changes still uncommitted.
- Changes: repository rules, roadmap, reusable prompts, phase specifications,
  context/review directories, and deterministic preflight/verification scripts.
- Verification: shell syntax and read-only preflight passed; `git diff --check`
  passed; application, tests, requirements, and CI aggregate hashes are unchanged;
  no secret patterns were found in harness files.
- Unresolved: changes remain uncommitted; repository has no Git remote.

## GEOAI-007C - baseline confirmed; commit preparation complete

- Date: 2026-10-24 (Europe/Moscow); VM109 checkout verified.
- Commands: bash scripts/geoai-preflight.sh; bash scripts/geoai-verify.sh.
  Both exit 0. pip check and git diff --check passed.
- Regression: 10 discovered/run/passed, 0 failures/errors/skips. API:
  6 discovered/run/passed, 0 failures/errors/skips. Both runners recorded
  network=0, dotenv=0, write=0, process=0 blocked operations during tests.
- Integrity: SHA-256 of 40 application/test/dependency/script/workflow files
  unchanged before/after verification and final documentation edits.
- Changes for this phase: AGENTS.md, PLANS.md, this log, new
  harness/build/007c-baseline.md, and .gitignore. Scoped ignore exception
  makes phase Markdown versionable; ordinary build output stays ignored.
- Evidence and commit candidate manifests:
  /home/geoai/dev-data/geoai-007c/20261024T204452Z/.
- Git: codex/geo-ai-start at 36f49b2a2ee5a412a1e5a2c5e8fdc275fcafb3be;
  previous working changes retained; no staged files, commit, push or remote.
- Limits: inherited .github/workflows/cicd.yml invokes direct unittest
  discovery, which conflicts with require_isolation(); CI was not executed
  or changed. Workflow inclusion/fix requires explicit approval. Existing
  PTB per_message=False and Git CRLF normalization warnings remain.
  API is an unauthenticated local development baseline; ownership, quotas,
  retention and content inspection are not implemented. Isolation is Python
  guards/mocks, not an OS sandbox. Baseline passing is not a full code/security
  review or a claim that every boundary case is tested.
- Next: recover GEOAI-007A scope/acceptance criteria and execute it as the
  next approved phase; then 007B -> 008 -> 009 -> 010 -> 011. 007A/007B
  specifications were absent at handoff; no later phase was started.

## AUTONOMY-001 — setup in progress

- VM109: Debian 13.7, 2 CPU, 3.8 GiB RAM, 53 GiB available disk.
- Restorable pre-commit snapshot: `/home/geoai/dev-data/geoai-autonomy/baseline-20261024T205926Z/`
  (33 changed/untracked files, archive and bundle verified).
- Baseline: preflight and verify exit 0; 10/10 regression, 6/6 API tests,
  pip check and git diff --check passed.
- Local commit `c33340366ee4016a7e2d2576bb9c46931875db16` saves 32
  baseline files; inherited `.github/workflows/cicd.yml` edit remains
  uncommitted. Verified `verified-baseline.bundle` and bare store
  `baseline.git` point to the same commit. No Git remote/push/deployment.
- Installed under `/home/geoai/.local/opt/geoai-autonomy/`: Symphony v0.0.3,
  Codex CLI 0.164.0 plus code-mode host, Cursor Agent 2026.10.22-27dcf5f,
  and user-local bubblewrap 0.12.0. Official release hashes or HTTPS package
  source verified.
- Codex device login completed; a real read-only file tool call returned
  the exact sentinel. Cursor CLI remains unauthenticated after one failed
  browser login; a second login is pending. No Cursor code run yet.
- Bubblewrap probe: worker sees and writes its workspace, but cannot see
  `.ssh` or the controller's verified bundle. Pilot acceptance stored outside
  worktree; pre-implementation run failed as expected (missing module), no
  PASS. User-level detached-process probe survived SSH disconnect;
  `loginctl enable-linger geoai` was denied, so boot persistence is unresolved.
- GitHub ownership verified (`PKG89` admin). Issues #2–#5 created with
  `geoai-planned`; none has queue label. Full pilot and autonomous service
  are not yet running. Independent Proxmox host-key check remains unperformed;
  SSH used the pinned key at owner's latest instruction.
- Next: complete Cursor auth, run full pilot with Codex/Cursor and negative
  gate, build/verify the protected controller, then queue GEOAI-008.

## AUTONOMY-002 — pilot auth block preserved

- Date: 2026-10-25 (Europe/Moscow). The second Cursor browser login also
  returned `Sign-in failed. Please try again.` Cursor Agent CLI on VM109 has
  no authenticated user API key; the owner is checking Windows sign-in.
- The protected pilot controller was updated to persist `BLOCKED` with reason
  `Cursor user API key missing` before launching a worker. `resume` returned
  `BLOCKED_AUTH`; a second `resume` refused the persisted block. `status`
  reports zero attempts/returns, zero active time and no live process;
  `logs` and `stop` safely report no active attempt. `unblock-auth` refuses
  while the key is absent.
- Sandbox probe passed again. The pilot checkout remains clean on
  `codex/geoai-pilot`. Frozen task and acceptance SHA-256 values are
  `e52a9b15af468d9ffae57f29da74569043fef5603a033ca51dd0a39b910cb459`
  and `1a07e8254c8ce395dfab6f565fa8258d510bc66f2d895bec6d508cfad0b4e8b2`.
- No Cursor implementation, accepted pilot, GitHub queue label, Symphony
  service, push or deployment occurred. The draft workflow remains inactive.
  A repository-scoped GitHub Issues credential is still needed on VM109 for
  dispatch; the Windows `gh` token was not copied. User-session linger after
  reboot remains unresolved, although a detached process survived SSH exit.
- Next: verify VM109 Cursor CLI with a real call after login or a user API
  key is installed; clear the auth block, run the pilot, verify preservation
  and stop/resume, then activate bounded issue dispatch and start GEOAI-008.
