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

## AUTONOMY-003 — pilot accepted

- Cursor CLI browser login succeeded on VM109; `agent status` confirmed the
  account. A real isolated read-only call returned the exact first heading of
  `AGENTS.md`, and the worktree stayed clean.
- Frozen pilot task/test hashes: `e52a9b15af468d9ffae57f29da74569043fef5603a033ca51dd0a39b910cb459`
  and `1a07e8254c8ce395dfab6f565fa8258d510bc66f2d895bec6d508cfad0b4e8b2`.
  The pre-implementation gate failed; Cursor's deliberately incomplete first
  pass also failed three frozen cases despite passing its focused test. Codex
  reviewed digest `c8c3214b9b159a6fdd49817ea6ca0851626260e659b06990e2eaf144a3dccaef`
  and sent specific repair feedback. The repaired digest
  `fc0b43d48c87b72a0afe7c2f477b8d7e4c3dac971f12941686c5fb7f83f68038`
  passed four focused, four frozen, 10 regression and six API tests.
- Stop/resume killed the old Cursor process, preserved 112.69 seconds of
  active package time and one repair return, and refused duplicate or post-
  acceptance resumes. Accepted local commit:
  `08bdbad32799ad48cb6f8df3eaad37d562fb7aa9`. Separate bare branch
  `codex/geoai-pilot` and verified `pilot-accepted.bundle` hold it. No pilot
  product code was merged or published.

## GEOAI-008 — accepted locally

- Cursor implemented the independent TXT/CSV parser and Telegram adapter on
  isolated `codex/geoai-008` from `76bfca4671647a7462687f1e3f16d639042a0cd0`.
  The frozen task/test hashes were
  `bee33f75df02d96b9be2f6ec5728a85cd532da0ff02276b090c2d273abe34120`
  and `37d27bf2a28f3d6bb3afc2f971859e9850e9d7f1a6382c6b128b894114862e3f`.
- First protected gate rejected an out-of-scope build-log edit. Codex also
  reproduced unhandled codec/decode exceptions and returned both findings.
  Cursor removed the edit and added explicit `SurveyParseError` handling/tests.
  A second gate had a false positive from pre-existing trailing spaces in the
  tracked Telegram file; `git diff --check` found no new whitespace. The gate
  was corrected to scan changed tracked lines and whole new files. Frozen
  task, external cases, file scope and revision digest were unchanged. The
  corrected gate passed without another Cursor run or counter reset.
- Accepted digest `da7c0387c8cc9ddf3eed2b7197e5ae3701712960633bc68a92662948ba30299c`:
  13 focused, six frozen, 10 regression and six API tests passed in the
  networkless sandbox; pip check, diff check and scope checks passed.
  Accepted local commit `aec7fdad107cc1e4382b97f2d3218129e80dbccc`
  is clean, stored under bare branch `codex/geoai-008` and verified in
  `/home/geoai/dev-data/geoai-autonomy/geoai-008-accepted.bundle` (SHA-256
  `b37acace553105970aa8f85e473c52b0192ac693b513cfac6398543c8e63b024`).
  GitHub Issue #2 was closed with local-only status noted. No push, merge,
  deployment, `.env` or survey data change occurred.
- GitHub Issues token on VM109 is geoai-owned mode 0600; authenticated GET
  `/user` and Issue #2 returned 200, as did an idempotent write of its
  existing `geoai-planned` label. The token value was not logged or copied.
- Next: complete protected Symphony dispatch and service survival check;
  freeze GEOAI-009 acceptance, then start #3 from the accepted 008 commit.
  Issues #3–#5 are not queue-labeled. The inherited CI edit remains
  uncommitted in the original checkout; independent Proxmox host-key
  comparison and reboot persistence remain unresolved.

## GEOAI-009 — protected dispatch started

- Frozen task SHA-256 `4c6938d69c6596c17952cca0f39cbfd6d4b2c13936468e035a6ba97b5d9e3eac`
  and external test SHA-256 `c5f1cf2d1deae2d3991e47d87f7246a08de65db691c43453f599b65783b66a1c`;
  the untouched 008-based worktree failed the new frozen preview cases as
  expected. Exact base is local handoff `88aa9948faa58863cc290094894ffecfaa33afb1`.
- Protected broker and Symphony dispatcher are detached processes on VM109.
  A first dispatch exposed a Codex CLI approval-policy schema mismatch; the
  workflow was corrected to `never` with workspace-write sandbox. The next
  Symphony dispatch succeeded: Codex wrote one broker request, broker
  verified Issue #3 and launched Cursor supervisor PID 11597. Controller
  reported RUNNING, attempt 1, repair returns 0, intact frozen hashes.
  The broker removed `geoai-queue` while Cursor works. Codex app-server is
  launched through a wrapper that removes the GitHub token from its env.
- Current Git: original checkout `codex/geo-ai-start` keeps inherited
  `.github/workflows/cicd.yml` edit untouched. Product worktree is
  `codex/geoai-009` from the local accepted 008 lineage. No code push,
  merge, deployment, or source-data modification occurred.
- Next: wait for Cursor and protected gate, inspect exact diff and report,
  return specific feedback if needed, accept and preserve 009 only after
  independent PASS. Then prepare and run 010 from the accepted 009 commit.
  Automatic process restart after VM reboot, independent Proxmox host-key
  comparison, and inherited CI discovery are unresolved.

## GEOAI-009 — accepted locally

- Cursor's first two attempts were stopped after 603.55 and 222.34 seconds
  of analysis without file edits. The initial stop exposed a leaked GNU
  `timeout` child process group; it was terminated and the controller stop
  logic was fixed. A process-group regression probe passed. Existing `.venv`
  was mounted read-only in the Cursor sandbox; Cursor model switched to the
  locally available Codex 5.3 Low Fast through the Cursor CLI. Third attempt
  produced code and tests. These operational stops did not consume repair
  returns, and active-time counters were preserved.
- First independent gate passed 11 focused, five frozen, 10 regression and
  six API tests at digest `4466fbde9ade2ab2245c9bc22a1e1d640ff1e47d65b5ab6d274029cdf764759e`.
  Codex review reproduced an unhandled `csv.Error` on an oversized field.
  Protected broker transitioned the exact revision to REWORK_REQUIRED and
  launched one Cursor repair. The repaired revision
  `a941392bffa076503c3f103e77e4920f3599a55fe3658abf996a61aeea83638d`
  passed 12 focused, five frozen, 10 regression and six API tests, plus
  scope, whitespace, pip and diff checks. Codex reviewed exact file hashes.
- Accepted local product commit `10cd7ff75cc44eacfd38d2df937605f82f64a688`
  is clean and stored in bare branch `codex/geoai-009` and verified bundle
  `geoai-009-accepted.bundle` (SHA-256
  `aed66f5e5495edfb3500d9917f495d1d08ea8855295f0039005f8c3d3c2166c0`).
  Controller: ACCEPTED, four Cursor attempts, one repair return, 951.12
  task-active seconds and 1493.66 package-active seconds. GitHub Issue #3
  closed. No code push, merge, deployment, .env, survey-source, or inherited
  CI change occurred.
- User crontab includes `@reboot` launcher for broker and dispatcher. Actual
  reboot recovery is untested; login linger remains denied. Original branch
  retains inherited uncommitted CI edit. Independent Proxmox host-key
  comparison and inherited direct-discovery CI are unresolved.
- Next: freeze 010 task and tests against accepted 009, verify negative gate,
  then queue #4. #5 remains unqueued until accepted 010.

## GEOAI-010 — accepted locally

- Frozen task SHA-256 `cc318eef33dad33d78b2be5d56349c631e1d2032ecb98ddc74e06fbaffd34a1a`
  and external test SHA-256 `2e5ecefb98cba6464219791aa9aa2e8b7d4a675e0d5f281b93d9c536b5f1b547`.
  Negative gate on clean local handoff `935857e9d650b8c28d4b5b385e9f75241dbb86c5`
  failed as expected. Symphony dispatched Issue #4 to protected broker and
  one Cursor worker. Cursor implementation changed only the mapping service,
  API upload adapter and two focused test files.
- Independent PASS digest `89b894342fd623b3aa8e813fec59745ae32eb5c05c2d3880c7f70a16ae0a9bfd`:
  22 focused, six frozen, 10 regression and six API tests, plus pip, diff,
  scope and unsafe-path checks. Codex recomputed changed-file hashes and
  digest and reviewed the actual candidate. A stale workflow path briefly
  caused false blocked reports and a nested `bwrap` denial in Codex's sandbox;
  the workflow was corrected to inspect the protected host gate and exact
  GEOAI-010 worktree. No additional Cursor run or repair return occurred.
- Accepted local commit `5c5915fbb3e6df07a1a7b2d1d3a73d8a02750564`
  is clean, stored in bare branch `codex/geoai-010` and verified bundle
  `geoai-010-accepted.bundle` (SHA-256
  `88952f5a9407220126e27de79327af7b66316c05176f222adfde399a5084c809`).
  Controller: ACCEPTED, one Cursor attempt, zero returns, 128.82 task-active
  seconds and 1622.48 package-active seconds. GitHub Issue #4 closed.
  No code push, merge, deployment, .env, survey-source or CI change occurred.
- Next: freeze 011 service/API/Telegram and DXF/TIN acceptance from accepted
  010, verify negative gate, then queue #5. Original branch retains inherited
  uncommitted CI edit. Reboot recovery and independent Proxmox host-key check
  remain unverified; inherited CI still uses direct discovery.
