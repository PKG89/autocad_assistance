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

## GEOAI-011 — accepted locally; package complete

- Frozen task SHA-256 `a2da4daf381c3e0a601627b3bc9ea309ad6da7cbb9235c48fddaf726756563f5`
  and external test SHA-256 `a9112bd5b6d839a88c6f3aa3d64ee14c326c5f9462faa246fbf366a6f2606c40`.
  Negative gate on clean handoff `072fbf1f2ac6be23193c826cb7ba4483e1f7a4cc`
  failed as expected. Symphony dispatched Issue #5; one Cursor worker created
  the common DXF service, Telegram/API adapters and focused tests without
  changing geometry/KML algorithms or templates.
- Initial independent gate passed eight focused, seven frozen, 10 regression
  and six API tests at digest
  `1c7d4daf017b9d9d825264747681949108d2823048cc2dc264d8cd776dba31bb`.
  Codex review independently reproduced fabricated `None` comments in DXF,
  noted missing TIN `scale_value` passthrough and a broad ValueError handler.
  Broker returned exact-digest feedback for one Cursor repair. An independent
  synthetic probe then found only the real comment, with no `None` text.
- Repaired digest `4d04c236e2fbd8645b9f597f6135ace044e558c6b997509840d1cc8904407580`
  passed 11 focused, seven frozen, 10 regression and six API tests, plus
  pip, diff, scope and unsafe-path checks. Codex recomputed file hashes and
  reviewed all five changed files. Accepted product commit
  `b78b1f591244f04c6652c9fe857b93d282f134ec` is clean, stored in bare
  branch `codex/geoai-011` and verified bundle
  `geoai-011-accepted.bundle` (SHA-256
  `178eafc32fc314f2e1e88fe3875e3d8cb6530cfa00821fa9aba1b1593e323cb6`).
  Controller: ACCEPTED, two Cursor attempts, one repair return, 181.24
  task-active seconds and 1803.72 package-active seconds. GitHub Issue #5
  closed. The total active package time stayed under two hours.
- Git after completion: accepted 008/009/010/011 product branches are local
  in the separate bare store; no external code remote/push, merge, main,
  production/deployment, .env, source survey or CI change. Original
  `codex/geo-ai-start` checkout retains only its inherited uncommitted
  `.github/workflows/cicd.yml` edit. Symphony dispatcher and protected broker
  were stopped after the queue emptied; the package-specific user `@reboot`
  crontab was removed (entry saved in control directory). Reboot recovery was
  not tested. Independent Proxmox host-key comparison remains unperformed.
- Next: treat 008–011 as the local accepted development baseline. Define a
  separate scope for inherited CI repair, authentication/ownership, resource
  retention/quotas and deployment. GEOAI-007A/007B have no recorded criteria.

## GEOAI-007A — local evidence reconciled; P0 prepared

- 2026-10-25 (Europe/Moscow). Read current `AGENTS.md`, `PLANS.md`,
  this journal and the inherited workflow before changing phase documents.
  The new roadmap's IDs 012–040 were absent from the VM plan; they were
  recorded as PROPOSED, not queued. Specs 007A and 007B now live under
  `harness/build/`. No Symphony/Cursor worker was started.
- Original checkout: `/home/geoai/projects/autocad_assistance`,
  `codex/geo-ai-start` at documentation commit
  `e9a8c5f2fe922056e851320ee3936e79a38292df` before these P0
  documentation edits. The only inherited dirty file was and remains
  `.github/workflows/cicd.yml`; it was not modified for P0. No Git remote
  is configured there. Final handoff checkout
  `/home/geoai/dev-data/geoai-autonomy/workspaces/handoff-final` was clean
  at local branch `codex/geoai-current-final`.
- Bare store `codex/geoai-current` points to
  `bbf6f660985db3e519b06deec52e7ef39b9678a3`. Accepted 008
  `aec7fda`, 009 `10cd7ff`, 010 `5c5915f` and 011 `b78b1f5`
  all passed `merge-base --is-ancestor` against that HEAD. The edge
  `b78b1f5 → bbf6f66` is a documentation commit recording completion.
- `geoai-current-final.bundle` has SHA-256
  `08e4fe4a7e5140f338aa30cce54938fa8bd39d8332af63fc7423a0a206c73384`;
  `git bundle verify` succeeded and `bundle list-heads` named that exact
  HEAD. Accepted 008/009/010/011 bundles also passed `bundle verify`;
  their SHA-256 values matched the prior journal. Existing verified
  preservation evidence was sufficient; no restoration or repeat product
  commit was performed.
- The inherited workflow was copied without changing it to
  `/home/geoai/dev-data/geoai-autonomy/p0-007a/cicd.inherited.yml`.
  Both original and copy have SHA-256
  `204ea3260ff123aa118b704cf8d468c70222f9a4f9a41ad5a928992d927b4808`.
  Its separate binary diff has SHA-256
  `301ede3d6fa0e1665844c5a592a70d16a208218433fd11495031157937c6c479`.
  An independent off-VM copy remains unconfirmed.
- GitHub repository metadata reports `main` as default branch. Its branch
  protection/rulesets were not established by that metadata. The inherited
  workflow runs direct unittest discovery, while both isolation bootstraps
  require absolute VM-only report roots. This is concrete 007B scope.
- Verification for 007A: Git ancestry, bundle SHA/head/verify, workflow
  copy hash and `git diff --check` passed. Product tests were not rerun;
  stage 011's latest independent gate remains 11 focused, seven frozen,
  10 regression and six API tests plus pip/diff/scope checks. No push, PR,
  CI edit, deployment or production-data access occurred.
- Next: 007B is SPECIFIED, NOT QUEUED. Freeze a separately approved CI file
  scope and local tests; then perform the clean-runner positive/negative
  checks. Full 007B closure requires an authorized push and actual successful
  remote CI run. P1 begins with 012 after P0 dependency decisions.
- After writing the P0 memory/specs, `git diff --check` passed. Original
  checkout remains on `codex/geo-ai-start` at `e9a8c5f` with modified
  `.github/workflows/cicd.yml`, `AGENTS.md`, `PLANS.md` and
  `harness/build-log.md`, plus untracked `harness/build/007a-local-record.md`
  and `harness/build/007b-ci-github.md`. P0 documentation is deliberately
  uncommitted; no local commit was authorized for this new package.

## P0 continuous authorization and run preflight

- On 2026-10-25 (Europe/Moscow), the owner explicitly authorized scoped
  workflow/CI edits, local commits, adding the exact GitHub origin if absent,
  tested push only to `codex/geoai-current`, and a draft PR. No main/master
  push, force-push, merge/rebase, production deployment/migration or real-data
  use. This supersedes the prior per-package stop and P0 document-only scope;
  AGENTS.md and PLANS.md were updated accordingly.
- Preflight: source checkout remained `codex/geo-ai-start` at `e9a8c5f`
  with the inherited workflow edit plus prepared P0 docs; final handoff
  worktree was clean on `codex/geoai-current-final`. No origin was configured
  in the source checkout. No Symphony/broker/Cursor worker was running.
- Direct P0 run manifest: `/home/geoai/dev-data/geoai-autonomy/p0-run-manifest.json`,
  start 2026-10-25T00:01:51Z, deadline 04:01:51Z, 90 minutes per task,
  maximum two repair cycles, one writable tree/worker, zero external executor
  spend. The prior controller's 30-minute/two-hour 008–011 budget remains
  historical and was not reset or reused.
- Next: commit only P0 documentation on the source branch, leaving the
  inherited workflow edit untouched; bring the same docs into the accepted
  code branch, then execute 007B.

## GEOAI-007B — local CI gate passed; remote gate pending

- Source P0 documents were committed separately as `eac98fad0e410eeee46e974e5ce928333fc30aeb`;
  the inherited workflow remained the only dirty source file. The same
  documents were committed atop accepted code branch `codex/geoai-current`
  as `14121661a928d3d1b57185aa3b5703d4ebe7faf4`. No 008–011 product
  commit was replayed. A stale local tracking ref briefly created a
  `codex/geoai-current` branch at `072fbf1`; it had no unique work, was
  refreshed from the verified bare ref at `bbf6f66`, and then used.
- Added a separate `.github/workflows/geoai-ci.yml` for push to
  `codex/geoai-current`, PR to `main`, and manual checks. It grants only
  `contents: read` and has no registry login, image publication,
  deployment or production secrets. The existing
  `.github/workflows/cicd.yml` was not changed on the code branch, so
  feature/PR events cannot trigger its main/master-only production jobs.
  The inherited source edit remains separately preserved by 007A.
- Both bootstrap scripts now use an explicit
  `GEOAI_TEST_REPORT_ROOT` (with a portable temporary default), require
  the output directory below that resolved external root and reject an
  output path in the checkout. The runner also rejects a report root inside
  the checkout before creating files. The VM's existing verify script passes its
  former report roots explicitly. A new runner finds all focused
  `test_*.py` files except the two guarded suites, then calls both
  bootstraps; `requirements-test.txt` records existing runtime
  dependencies and `httpx==0.28.1`.
- A fresh user-local venv installed `requirements-test.txt` and passed
  pip check, 58 focused tests, 10 isolated regression tests and six isolated
  API tests. Both guarded suites reported zero blocked network, dotenv,
  write or process operations. A temporary intentionally failing test
  made the entire runner exit 1; direct regression discovery also exited
  1 with its isolation error. The temporary probe was removed. Shell
  syntax and `git diff --check` passed. Evidence logs:
  `/home/geoai/dev-data/geoai-autonomy/p0-007b/`.
- Read-only GitHub checks: remote `main` and HEAD are `36f49b2`;
  `codex/geoai-current` did not exist remotely before first push. Public
  branch metadata reports `main` `protected=false`; no rules were
  changed. The code worktree's `origin` points to the local bare store,
  not GitHub, and must not be replaced. First external push still requires
  an exact target/auth check. No production workflow was run.
- Current status: LOCALLY VERIFIED only. Next: review exact staged diff,
  make a scoped local 007B commit, push only that verified code branch to
  `PKG89/autocad_assistance`, create a draft PR, inspect real CI, and
  repair up to two times within the P0 budget. Do not mark 007B complete
  before a successful remote run.

## GEOAI-007B — remote gate passed; P0 complete

- Exact reviewed local CI commit `49dea8abd8d1a6705a842bdcf80e7672a9135c91`
  was pushed only to GitHub `PKG89/autocad_assistance` feature ref
  `codex/geoai-current`. The VM code worktree's `origin` remains its
  separate local bare store and was not replaced. GitHub authentication
  was unavailable to VM Git; no token was copied there. A branch bundle
  was moved to Windows, combined with the public GitHub base history in
  a temporary bare repository, and pushed using the existing Windows
  `gh` authorization. No commits were recreated. Bundle SHA-256:
  `24f2085d85717549c2d7d3af0482c440132819d6a7937f9e37967754bb099cbd`.
- Draft PR #6: `https://github.com/PKG89/autocad_assistance/pull/6`,
  head `49dea8a`, base `main`. GitHub Actions push run 40145553092
  and pull_request run 40145565460 both completed successfully at the
  exact head SHA. Only `GEO AI checks` ran; the production workflow
  did not run. GitHub branch metadata reported `main protected=false`
  and the active branch-rules query returned no rules. No branch rules
  were changed.
- Independent Windows copies now exist for both the accepted P0 bundle
  (SHA above) and inherited uncommitted workflow (SHA-256
  `204ea3260ff123aa118b704cf8d468c70222f9a4f9a41ad5a928992d927b4808`).
  The workflow's VM copy has the same hash. GEOAI-007A is fully accounted
  for locally and off VM. No production, real survey data, main push,
  force-push, merge or deployment occurred.
- P0 is accepted after the successful remote CI gate. Next: freeze
  GEOAI-012 scope and tests in `harness/build/`, move it from PROPOSED
  to READY, then implement it on the accepted feature branch.

## P1 / GEOAI-012 — specification frozen

- GitHub push and PR checks for P0 documentation head `6e1a751` both
  passed (runs 40145686582 and 40145691264). P0 remains accepted.
- Codebase graph is available but this repository is not indexed; targeted
  filesystem search identified the existing parser, mapping, DXF service,
  API and Telegram adapters. No broad repository audit was repeated.
- P1 manifest starts 2026-10-25T00:12:17Z, deadline 04:12:17Z, 90
  minutes per task, at most two repairs, one writable tree/compute worker,
  zero external executor spend. See protected dev-data manifest.
- GEOAI-012 is READY at base `6e1a751` with explicit scope, non-goals,
  acceptance and checks in `harness/build/012-survey-model.md`.
  No geodetic unit, CRS or tolerance will be inferred.

## GEOAI-012 — local gate passed

- Based on accepted feature HEAD `6e1a75154e4ac1cac4ce439a32569a735f9f1dd0`.
  Added framework-independent `SurveyDataset`, `SurveyRecord`,
  `SurveyContext` and structured warnings. The accepted parser now
  records physical source-line numbers additively; the existing mapping
  algorithm is reused. Original text and raw cells remain unchanged
  beside finite Decimal XYZ; the model never transforms coordinates,
  infers EPSG/units or applies drawing scale to measurements.
- API mapping and DXF use the contract. Mapping returns additive warnings
  with row index for duplicates/empty IDs and explicit unknown CRS/units.
  Telegram keeps its accepted mapping step (including a blank Z pending
  generation), saves a source digest/line numbers and checks the common
  contract before DXF. Existing DXF and KML geometry code is unchanged.
- Final fresh-venv gate: 67 focused tests, 10 isolated regression tests,
  six isolated API tests, pip check and `git diff --check` passed.
  Both bootstraps reported zero blocked network, dotenv, write and process
  operations. Tests cover swapped axes, raw precision/provenance, duplicate
  and empty IDs, unknown/local CRS, missing or nonfinite Z, precision
  underflow, current Telegram scale and invalid API scale. Evidence:
  `/home/geoai/dev-data/geoai-autonomy/p1-012-final-gate.log`.
- Scope review found only parser/model, HTTP/Telegram adapters, state-key
  cleanup, focused tests and task memory. No real survey, production DB,
  .env, deployment or geometry/template change. Current status:
  LOCAL ACCEPTED, remote CI pending. Next: commit exact reviewed files,
  push only `codex/geoai-current`, inspect CI and then prepare 013.

## Three-task checkpoint: 007A, 007B, 012

- GEOAI-012 product/memory commit
  `608a8e3ff84178470dbad6663fcca27fef5508b9` was pushed only to
  `codex/geoai-current`; GitHub push run 40146181250 and draft PR #6
  run 40146183772 both succeeded at that exact SHA. Bundle SHA-256
  `34f6cb015e3b01e27d00935044879102b260a0f5b04b3cc809728afc60754475`
  was verified on VM109 and copied to Windows. No production workflow
  run occurred. 007A, 007B and 012 are ACCEPTED.
- Before preparing 013, the active code worktree on VM109 was clean on
  `codex/geoai-current` at `608a8e3`; its `origin` remains the local
  bare store. GitHub draft PR #6 tracks the same feature branch. P1
  manifest remains within its 2026-10-25T04:12:17Z deadline; no external
  executor spend or second worker.
- GEOAI-013 is READY on the accepted 012 dependency. Its technical
  size/row/point limits and narrow file/security scope are frozen in
  `harness/build/013-upload-guard.md` before code edits. Continue with
  013; 014 stays PROPOSED.

## GEOAI-013 — local gate passed; remote gate pending

- Base: accepted 012 at `608a8e3`, followed by documentation checkpoint
  `7a5ce8b`. One writable feature worktree on `codex/geoai-current`;
  original checkout and inherited CI edit were not touched.
- Preserved 10 MiB HTTP upload limit and added 100,000 usable survey rows,
  150,000 physical lines, 64 columns, 4,096 characters per field,
  100,000 KML coordinate tuples and 200,000 XML elements. Rejects binary,
  disguised, malformed and over-limit files before accepting the upload;
  failed uploads remove their partial file/directory. User names are
  metadata; server UUIDs define stored paths.
- Preview, mapping and DXF use a single bounded, no-follow descriptor read
  of an exact UUID-named regular file. Tests cover symlinks, a path swap
  after open, unique IDs, control/bidi names, malformed KML, XML DTD,
  row/line/column/field/coordinate limits and stable API errors.
- Local gate at `/home/geoai/dev-data/geoai-autonomy/p1-013-final.log`:
  74 focused, 10 isolated regression and six isolated API tests passed;
  both isolated suites reported zero blocked network, dotenv, write and
  process operations. `pip check` and `git diff --check` passed. No real
  survey, production DB, `.env`, deployment or geometry change.
- GitHub feature/PR checks are pending. Next: commit exact reviewed files,
  push only `codex/geoai-current`, inspect both CI runs, then freeze 014.

## GEOAI-013 — remote gate passed; GEOAI-014 ready

- Exact reviewed commit `66b8dcc3c651c08baf5d14be2370d0d73ea0f773`
  was pushed only to `codex/geoai-current`; VM `origin` remains the local
  bare store. Verified branch bundle SHA-256:
  `c4ba7adea57a515ddd24fbbdbdead8ff880237fc16f7322ba23a3b914147663e`;
  matching off-VM copy exists on Windows.
- GitHub `GEO AI checks` push run 40146687136 and draft PR #6 run
  40146689779 both succeeded at that exact SHA. Only the feature/PR
  check workflow ran; no production workflow or deployment.
- Dependency 013 is ACCEPTED. Next: use the frozen 014 specification for
  one bounded compute worker, queue, timeout, cancellation, retry and
  crash recovery. P1 manifest remains active and within its deadline.

## GEOAI-014 — local gate passed; remote gate pending

- Base: accepted 013 at `66b8dcc`, followed by frozen-scope documentation
  commit `7c13d6c`. One writable feature worktree, no second worker,
  system install, external queue, production data or deployment.
- Added a framework-independent local DXF job coordinator and disposable
  child entry point. Linux file lock guarantees one coordinator per jobs
  root. Queue holds at most four waiting jobs, with one child process,
  120-second wall timeout, 25 MiB result cap, 32 MiB serialized request
  cap and two explicit retries. Child memory is capped at 1.5 GiB and
  dies with its parent on Linux. States/input live under UUID paths;
  completed DXF is published atomically after validation.
- Cancellation terminates work and clears temporary renderer files;
  interrupted jobs are failed with `INTERRUPTED` on restart for explicit
  retry. Results survive restart and are read through bounded no-follow
  descriptors. The synchronous HTTP/Telegram DXF paths and geometry
  engine were not changed; web job routes remain for GEOAI-020.
- Local gate at `/home/geoai/dev-data/geoai-autonomy/p1-014-accepted.log`:
  83 focused, 10 isolated regression and six isolated API tests passed;
  zero blocked network, dotenv, write and process operations in both
  isolated suites. `pip check` and `git diff --check` passed. Negative
  tests cover full queue, cancellation, timeout, crash, invalid result,
  retry ceiling, missing/nonfinite height, symlinked result and restart.
- Next: commit exact reviewed files, push only `codex/geoai-current`,
  inspect push and PR checks, then make the three-task P1 checkpoint
  (012–014) before freezing 015.

## Three-task checkpoint: GEOAI-012, 013 and 014

- GEOAI-014 exact reviewed commit
  `0ad1e0a7955adde286d23cefa2731d17c70ac57b` was pushed only to
  `codex/geoai-current`. GitHub `GEO AI checks` push run 40147083698
  and draft PR #6 run 40147086595 both succeeded at that SHA. The
  production workflow did not run. Verified VM/Windows bundle SHA-256:
  `c590db274824cfc775e0d4b48b514ca3868ff0d5b04bfeb5df80213b31beaa02`.
- 012, 013 and 014 are ACCEPTED; P1 manifest completed at
  2026-10-25T00:33:23Z, before its 04:12:17Z deadline. VM code worktree
  was clean at `0ad1e0a`; original checkout and inherited workflow edit
  remain untouched. No second worker, external executor spend,
  production data, main push, merge or deployment.
- P2 manifest starts 2026-10-25T00:33:23Z, deadline 04:33:23Z,
  90 minutes per task, at most two repairs, one writable tree/worker,
  zero external executor spend. GEOAI-015 is READY on accepted 012–014;
  its service-only storage scope and checks are frozen in
  `harness/build/015-project-storage.md`. GEOAI-016/017 stay PROPOSED.

## Test-count audit (2026-10-25)

- Recounted the raw `Ran N tests` groups before the isolated regression
  summary, excluding the separate 10-test regression group. Correct focused
  counts are 58 for 007B, 67 for 012, 74 for 013 and 83 for 014. Earlier
  narrative counts included that first regression group once; pass/fail
  outcomes, test commands and CI results are unchanged.

## GEOAI-015 — local gate passed; remote gate pending

- Base: accepted 014 at `0ad1e0a`, followed by P1 checkpoint and frozen
  015 scope at `c9b3deb`. One writable feature worktree; no Telegram
  database, public project route, authentication shortcut, system package,
  deployment or real survey data was used.
- Added a separate SQLite metadata store and server-UUID file tree.
  Revisions preserve exact accepted TXT/CSV/KML source bytes, SHA-256,
  explicit CRS/units/scale context, settings, parent/sequence and caller
  supplied algorithm version. Jobs preserve exact canonical request JSON
  and digest; accepted DXF results record size/digest and source/job link.
  Sources are capped at 10 MiB, results at 25 MiB, and each settings
  document at 64 KiB. Reads use bounded no-follow descriptors and reject
  tampered bytes/metadata. File writes precede SQLite acceptance; failed
  writes roll back metadata and clean only the current attempt's file.
- The real 014 child worker produced a DXF that was snapshotted to its
  revision and verified after restart. Negative tests cover duplicate
  publication, wrong status, unknown IDs, symlinks, parent swap,
  post-write failure, altered source/settings/request metadata and
  oversized settings. No coordinate or geometry behavior changed.
- Final local gate at
  `/home/geoai/dev-data/geoai-autonomy/p2-015-final.log`:
  92 focused, 10 isolated regression and six isolated API tests passed;
  both isolated suites reported zero blocked network, dotenv, write and
  process operations. `pip check` and `git diff --check` passed.
- GitHub feature/PR CI is pending. Next: commit exact reviewed files,
  push only `codex/geoai-current`, inspect CI, then freeze 016.

## GEOAI-015 — first remote CI repair

- Product/storage commit `cab810546ad069909a65c34b5416621a43000efd`
  was pushed only to `codex/geoai-current`. Its draft PR run
  40147551712 succeeded, but push run 40147546493 failed in the existing
  014 cancellation test. The test observed `cancelled` before the worker
  thread removed a transient renderer directory; VM timing had hidden
  the race. No storage test or isolated regression/API test failed.
- Changed the 014 coordinator to remove transient directories and discard
  any candidate result before publishing a terminal cancellation/failure
  state. The targeted cancellation test passed ten consecutive VM runs;
  the full clean-venv gate passed again with 92 focused, 10 isolated
  regression and six isolated API tests, zero blocked operations, pip and
  diff checks. Evidence:
  `/home/geoai/dev-data/geoai-autonomy/p2-015-repair1.log`.
- One of two allowed 015 repair cycles is used. Next: commit the reviewed
  race fix and journal, push the exact new feature HEAD, require both
  GitHub push and PR runs to pass before accepting 015.

## GEOAI-015 — remote gate passed; GEOAI-016 ready

- Exact repair HEAD `a0e82bc968884cd5d8a60bd522fea2bc3170f608`
  was pushed only to `codex/geoai-current`. GitHub `GEO AI checks`
  push run 40147682109 and draft PR #6 run 40147684816 both succeeded
  at that SHA. The previous product head `cab8105` remains in history;
  its push CI failure and PR success are recorded above. No production
  workflow or deployment ran.
- The verified branch bundle has SHA-256
  `3581de76a2121c66081b50d55cb8de3f7f99e5aeef9e9cd0e5f7c57cf65c6512`
  on VM and Windows. The VM worktree is clean at `a0e82bc`; its `origin`
  remains the local bare store. GEOAI-015 is ACCEPTED after one repair.
- P2 remains within its 2026-10-25T04:33:23Z deadline. GEOAI-016 is
  READY with service/API/session and confirmed Telegram-link scope frozen
  in `harness/build/016-owner-auth.md`; 017 stays PROPOSED.

## GEOAI-016 — local gate passed; remote gate pending

- Base: accepted 015 at `a0e82bc`, followed by frozen-scope
  documentation commit `aac535e`. The owner identity store is separate
  from both project data and Telegram statistics. No real owner password,
  session or Telegram link was provisioned; tests used disposable roots
  and synthetic credentials only.
- Local CLI provisions one owner with hidden password. Scrypt parameters
  are N=2^17, r=8, p=1 with one cross-process KDF lock. Per-username
  and global login attempts are bounded. SQLite stores a salted password
  digest and SHA-256 session verifier; the bearer token is cookie-only.
  Server-side idle and absolute expiry are 30 minutes and eight hours.
  Login rotates an old session; logout, revoke-all and confirmed Telegram
  linking revoke sessions.
- Auth routes require explicit auth root and exact trusted HTTPS origin.
  The `__Host-geoai_session` cookie has Secure, HttpOnly, SameSite=Strict
  and Path=/; mutations enforce Origin and CSRF, responses use no-store.
  One-time link codes expire after ten minutes and can be confirmed only
  by a private Telegram bot update from a configured admin ID. Bot
  registration is opt-in. Existing upload/preview/DXF routes remain
  unprotected pending 017; no private cabinet is claimed yet.
- Final local gate at
  `/home/geoai/dev-data/geoai-autonomy/p2-016-accepted.log`:
  104 focused, 10 isolated regression and six isolated API tests passed;
  both isolated suites reported zero blocked network, dotenv, write and
  process operations. `pip check` and `git diff --check` passed. Tests
  include brute-force bounds, session fixation/expiry/revocation,
  cross-origin/host rejection, CSRF, secure cookie flags, opt-in bot
  registration and one-time Telegram confirmation.
- GitHub feature/PR CI is pending. Next: commit exact reviewed files,
  push only `codex/geoai-current`, inspect both CI runs, then freeze 017.

## GEOAI-016 — remote gate passed; GEOAI-017 ready

- Exact reviewed commit `04522becb613dc06d4b19e4b579318315cac6775`
  was pushed only to `codex/geoai-current`. GitHub `GEO AI checks`
  push run 40148311053 and draft PR #6 run 40148314247 succeeded at
  that SHA. No production workflow or deployment ran.
- The verified branch bundle has SHA-256
  `7290edd0f7fd47b032b8cf50320416b26168fbff91f62edce3c7be0765bd07ca`
  on VM and Windows. Worktree was clean at `04522be`; the original
  checkout and inherited workflow edit were untouched. GEOAI-016 is
  ACCEPTED without a repair cycle or real credential provisioning.
- P2 remains within the 2026-10-25T04:33:23Z deadline. GEOAI-017 is
  READY on accepted 015–016; its schema migration, upload ownership,
  per-request gate and download checks are frozen in
  `harness/build/017-resource-ownership.md`.

## GEOAI-017 — local gate passed; remote gate pending

- Base: accepted 016 `04522be` and 017 frozen-scope documentation
  `b01895f`. Only the accepted feature worktree changed. The original
  checkout and inherited workflow edit remain untouched.
- Project schema v2 adds an immutable owner UUID for newly created
  projects and uploads. Version-1 projects migrate with NULL owner;
  no identity is inferred or assigned to existing data. Scoped service
  methods check owner for project/revision/job/source/result operations.
- Opt-in authenticated API mode requires a separate project root.
  Its outer ASGI guard checks HTTPS host and a revocable session before
  request body parsing on resource routes; unsafe methods require exact
  Origin and CSRF. Upload registration failure removes the newly written
  file using no-follow directory descriptors. Preview, mapping and DXF
  recheck owner, format, size and SHA-256 before reading. New source and
  result downloads check owner and file integrity. Missing and foreign
  resources return the same 404 response.
- Local gate evidence: `/home/geoai/dev-data/geoai-autonomy/p2-017-final.log`
  and `p2-017/final-gate/`: 107 focused, 10 isolated regression and six
  isolated API tests passed; zero blocked network, dotenv, write or
  process operations; `pip check` and `git diff --check` passed.
  Focused negatives cover cross-owner/unknown/unowned IDs, anonymous
  and CSRF rejection before upload parsing, tampered and symlinked
  upload bytes, database registration rollback, source/result integrity,
  and version-1 migration.
- GitHub feature/PR CI is pending. Next: commit exact reviewed files,
  push only `codex/geoai-current`, inspect both runs and record their
  results before accepting 017. No real owner provisioning, deployment
  or production migration occurred.

## GEOAI-017 — remote gate passed; P2 checkpoint

- Exact reviewed product/documentation commit
  `f3bee9c22daeacc4217b21286338f5ee48058bdd` was pushed only to
  `codex/geoai-current`. GitHub `GEO AI checks` push run 40148828172
  and draft PR #6 run 40148831218 both succeeded at that SHA. No
  production workflow or deployment ran.
- Verified full branch bundle SHA-256 on VM and Windows:
  `2a2a03c078ef31e7972901fe8fb8d90c7a52be8f051bf0e5dc8c658683e3d3fb`.
  The VM worktree is clean at `f3bee9c`; its `origin` remains the local
  bare store. The original checkout and inherited workflow edit remain
  untouched. GEOAI-017 is ACCEPTED without a repair cycle.
- Three-task checkpoint: 015, 016 and 017 are accepted with local and
  GitHub feature/PR gates. P2 is COMPLETE before its
  2026-10-25T04:33:23Z deadline. No production data or real owner was
  migrated/provisioned. Next: freeze GEOAI-018 from this accepted base
  with a new P3 manifest, then implement 018–020 by dependencies.

## P3 preparation — GEOAI-018 ready

- Accepted base is `f3bee9c`; the P2 manifest is marked complete.
  New P3 manifest starts 2026-10-25T01:01:04Z and ends no later than
  2026-10-25T05:01:04Z with the same one-worker and zero external-spend
  bounds. No second executor was started.
- GEOAI-018 scope and acceptance are frozen in
  `harness/build/018-resource-limits.md`. Opt-in retention and explicit
  dry-run/apply maintenance avoid choosing a production deletion policy.
  Project revisions/results are excluded from cleanup. Dependencies
  014–017 are accepted; 018 is READY. Next: implement 018 in the same
  feature worktree, run the focused and full isolated gates, then push
  only the reviewed feature commit and inspect both CI events.
