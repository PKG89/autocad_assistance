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

## GEOAI-018 — local gate passed; remote gate pending

- Base: accepted 017 at `f3bee9c`, followed by P2 checkpoint and 018
  frozen-scope commit `d2ee01d`. Only the feature worktree changed.
- Project metadata schema v4 adds optional creation/expiry times and
  cleanup state for uploads. Version-2 rows migrate with NULL times,
  so historical uploads are not assigned an invented expiration. The
  opt-in retention setting creates expiration only for new uploads.
- Transactional per-owner caps cover projects, registered uploads,
  revisions, jobs and accepted bytes across uploads/sources/results.
  Development defaults are 20/100/500/500 and 512 MiB; callers can
  inject stricter limits. A rejected HTTP upload removes its newly
  written file and returns `QUOTA_EXCEEDED` (429). Concurrent project
  writers cannot exceed a single-project cap.
- Expired-upload maintenance is bounded to 100 records per call and
  dry-run by default. Explicit apply marks a row deleting, unlinks only
  its UUID-named regular file through no-follow descriptors and then
  retires the row. A symlink failure remains retryable. Project source
  snapshots and DXF results are never removed by this command.
- Final local gate at
  `/home/geoai/dev-data/geoai-autonomy/p3-018-final.log` and
  `p3-018/final-gate/`: 113 focused, 10 isolated regression and six
  isolated API tests passed with zero blocked network, dotenv, write
  and process operations; `pip check` and `git diff --check` passed.
  Tests cover count/byte limits, restart, two concurrent writers,
  API 429 with file rollback, v2 migration, opt-out retention,
  dry-run/apply, symlink retry and revision survival after cleanup.
- GitHub feature/PR CI is pending. Next: commit exact reviewed files,
  push only `codex/geoai-current`, inspect both CI runs. No cleanup of
  real data, production migration, deployment or credential change ran.

## GEOAI-018 — first scope repair before acceptance

- Initial product commit `52b794f3d89bbbd46e8cc7a806b631bc0503db99`
  passed GitHub push run 40149278271 and draft PR #6 run 40149281733.
  A review against the supplied roadmap found that cleanup still lacked
  a persistent journal. The stage remains open despite successful CI.
- One of two allowed repair cycles is used. Added version-4
  `cleanup_events` metadata with upload/owner UUID, outcome and time.
  Apply success and failure are recorded; dry-run remains read-only.
  The maintenance command returns a bounded journal. Retention classes
  are explicit: temporary uploads may expire by configuration;
  accepted source snapshots and DXF exports are retained; reference
  archives do not yet exist and cannot be cleaned here. Existing 014
  single-worker, queue and timeout bounds cover compute work.
- A focused test initially assumed ordering between independent upload
  events and was corrected to assert two removals, one failed attempt
  and the latest retry outcome. No product behavior was weakened.
  Targeted tests and the complete local gate passed again at
  `/home/geoai/dev-data/geoai-autonomy/p3-018-repair1.log`:
  113 focused, 10 isolated regression, six isolated API tests, zero
  blocked operations, pip and diff checks. Next: commit the reviewed
  journal repair, push exact feature HEAD and require both CI runs.

## GEOAI-018 — remote gate passed; GEOAI-019 next

- Exact journal repair commit `8ed56875bd1859baead50086c57c4ea52718defa`
  was pushed only to `codex/geoai-current`. GitHub `GEO AI checks`
  push run 40149469271 and draft PR #6 run 40149474159 succeeded at
  that SHA. GEOAI-018 is ACCEPTED after one scope repair; no further
  repair budget was used.
- Full branch bundle SHA-256
  `0360aab5476366e23202e5bbf1cf7cb1b098cb9887925a08a4732048093199f6`
  matches on VM and Windows. The VM worktree is clean at `8ed5687`;
  its origin still points to the local bare store. The original
  checkout/inherited workflow edit remain untouched. No real data
  cleanup, production migration or deployment ran.
- P3 remains within its 2026-10-25T05:01:04Z deadline. Next: freeze
  019's import screen and owner-scoped project/revision API from this
  accepted base, then implement it with focused and isolated gates.

## GEOAI-019 — scope frozen

- Accepted base `8ed5687`; 019's dependency set has passed local and
  GitHub feature/PR checks. Scope and acceptance are frozen in
  `harness/build/019-import-screen.md`. No new framework or system
  package is required; the screen will use local assets and existing
  FastAPI/session/parser/project services. It will collect explicit
  coordinate context and preserve warnings without changing measured
  coordinates. GEOAI-019 is READY under the P3 manifest. Next:
  implement in the same writable feature worktree, run targeted and
  full isolated gates, then push exact reviewed commits and inspect CI.

## GEOAI-019 — local and browser gates passed; CI pending

- Base: accepted 018 at `8ed5687`, followed by frozen-scope commit
  `bf35457`. Only the feature worktree changed. Added owner-scoped
  paginated project/revision API and a plain same-origin web screen;
  no new frontend package or geometry implementation was added.
- The screen signs in through 016's session, restores it after reload,
  creates/selects a project, uploads and previews TXT/CSV, shows
  warnings, maps columns, collects explicit coordinate-system/unit/
  scale labels and saves an immutable revision. KML remains available
  through the existing upload API but is explicitly unsupported by
  this tabular mapping flow. Untrusted text uses `textContent`, CSRF
  stays in page memory, and the import button remains disabled after
  success until a new upload. API create/import calls are documented
  non-idempotent and never auto-retried by the screen.
- The new API validates all mapped rows before accepting a revision,
  records mapping and declared context with exact source bytes, and
  returns matching 404s for unknown/foreign owner resources. Project
  JSON bodies are capped at 64 KiB behind the 017 auth guard. Lists
  are bounded and revisions return newest first. Invalid context,
  mapping, KML, CSRF and oversize requests leave no accepted revision.
- Final local gate: `/home/geoai/dev-data/geoai-autonomy/p3-019-final.log`
  and `p3-019/final-gate/`: 116 focused, 10 isolated regression and
  six isolated API tests passed, zero blocked network/dotenv/write/
  process operations, `pip check` and `git diff --check` passed.
  `node --check` passed for the local script.
- Real browser UI check used a disposable synthetic owner and sample
  CSV under `p3-019/browser-fixture-http/`; an HTTP-only local SSH
  forward rewrote scheme/Origin solely for the UI flow because the
  in-app browser rejected the disposable self-signed TLS certificate.
  HTTPS/Origin/cookie security was tested independently by ASGI tests.
  The browser completed login, reload/session recovery, project,
  upload/preview and two intentional revisions. Double-clicking
  create/import produced one resource per click intent; after finding
  a misleading second-click message, the import button was held
  disabled until the next upload. Screenshot:
  `/home/geoai/dev-data/geoai-autonomy/p3-019/browser-proof.png`.
  Both disposable servers, SSH forwards and the browser tab were stopped.
- GitHub feature/PR CI is pending. Next: commit exact reviewed files,
  push only `codex/geoai-current`, inspect both CI runs and then freeze
  020 if accepted. No real credentials/surveys or deployment were used.

## GEOAI-019 — remote gate passed; GEOAI-020 next

- Exact reviewed commit `897cf600e916207fa2a8f6a9797e3bc8729fe642`
  was pushed only to `codex/geoai-current`. GitHub `GEO AI checks`
  push run 40150237735 and draft PR #6 run 40150241097 succeeded at
  that SHA. GEOAI-019 is ACCEPTED without a repair cycle.
- Full branch bundle SHA-256
  `a31bbe349c520ee813c6ea05a9fa0860698c74e9fd7d05aab4cb020e90a27efa`
  matches on VM and Windows. The worktree is clean at `897cf60`;
  origin remains the local bare store. The original checkout and
  inherited CI edit are untouched. No production deployment ran.
- P3 remains within 2026-10-25T05:01:04Z. Next: freeze 020 from this
  accepted base, preserving the one-worker and two-repair bounds.

## GEOAI-020 — scope frozen

- Accepted base is `897cf60`; dependencies 014–019 passed local and
  GitHub feature/PR checks. The finite P3 manifest remains active with
  one writable tree/compute worker, 90 minutes per task and two repair
  cycles. No second worker or external executor was started.
- Scope and acceptance are frozen in `harness/build/020-jobs-results.md`:
  owner-scoped durable job submit/status/cancel/retry, atomic
  client-owned idempotency key, bounded coordinator bridge, verified
  result publication/download and browser job controls. No production
  worker or deployment is authorized. GEOAI-020 is READY; next is
  implementation in the same feature worktree and full isolated gates.

## GEOAI-020 — local implementation and browser evidence; CI pending

- Implemented from clean scope commit `8d1e411` in the one writable
  feature worktree. Explicit `jobs_root` enables one 014 coordinator
  only in authenticated mode. Project schema v5 atomically records
  idempotency UUID, owner, revision, exact request digest and job ID;
  duplicate requests replay one job, changed intent conflicts.
- Status, cancel, retry, paginated history and result download are
  owner scoped. Successful child output is read with no-follow and a
  SHA-256 comparison before versioned result publication. A coordinator
  recovery bug was fixed so interrupted records remain visible for
  explicit retry. Legacy no-auth API and Telegram paths remain intact.
- Initial full gate exposed a schema-version check in the 018 cleanup
  CLI and a minimal v2 migration fixture. Both were updated for v5;
  the following full gate passed 120 focused, 10 isolated regression
  and six isolated API tests with zero blocked operations, plus
  `pip check`, `git diff --check` and `node --check`.
- Disposable browser test used a synthetic revision and account,
  double-clicked the submit button and observed exactly one job and
  one idempotency claim in SQLite. The job succeeded, produced a DXF
  download link, and history/link survived reload. Test server/tunnel
  stopped; no real data or production side effects.
- Final local gate log: `p3-020/accepted-gate.log`. Next: inspect exact
  staged diff, commit, push only `codex/geoai-current`, require feature
  and PR CI, then record acceptance and P3 checkpoint.

## GEOAI-020 — accepted; P3 checkpoint and P4 start

- Exact feature commit `91aeb53ad410abdc071498a4d22e561db3684dbe`
  passed GitHub `GEO AI checks` push run 40151146814 and draft PR #6
  run 40151149754. Branch bundle SHA-256
  `3301fc0570f992407ad168f77b7612b3388757a1dcdb957c43762f049582055e`
  matched on VM and Windows. The feature worktree was clean at that
  HEAD before this acceptance update; the original checkout and
  inherited workflow edit remain untouched.
- Final local gate passed 120 focused, 10 isolated regression and six
  isolated API tests, zero blocked network/dotenv/write/process
  operations, `pip check`, `git diff --check` and `node --check`.
  One repair cycle addressed the v5 migration/cleanup CLI checks;
  concurrent publication was covered by a dedicated passing test.
- P3 tasks 018–020 are accepted. The P3 deadline was not exceeded;
  no production worker, migration, cleanup or deployment ran. P4
  starts with a new finite manifest. GEOAI-021's accepted base and
  frozen comparison criteria are in
  `harness/build/021-web-mvp-acceptance.md`.

## GEOAI-021 — local parity and browser checks passed; CI pending

- Base is accepted 020 at `91aeb53`; scope was frozen in
  `harness/build/021-web-mvp-acceptance.md` at local HEAD `7446d4e`.
  The same synthetic CSV with SHA-256 `b02424ae3df178448b4c9e620887b7e2c9e6fbba6401b5337a32e270221868e6`
  passed real authenticated web upload/preview/import/job/download and
  offline Telegram file/mapping/scale/generation handlers.
- First comparison found the web 1:500 denominator passed as render
  factor 500 versus Telegram's 0.5. Shared conversion now applies the
  same factor to both; measured XYZ remain unchanged. A semantic DXF
  inventory compares 25 entities, block scale, layers, text, point
  geometry and ground TIN. A deliberate one-unit point change is
  detected. Unsupported types: zero.
- Final isolated sample: web 1.977219 s, Telegram 1.39428 s,
  parent/child process peak RSS 296816 KiB each on Linux 6.12.107 /
  Python 3.13.5. The full local gate passed 121 focused, 10 isolated
  regression and six isolated API tests with zero blocked operations,
  plus `pip check` and diff checks.
  Measurements are evidence, not acceptance limits. Browser smoke used
  the same fixed source and confirmed the completed job's download
  returned HTTP 200. Its disposable server/tunnel stopped.
- Full final local gate: `p4-021/final-gate-exact.log`; exact feature
  commit and GitHub push/PR CI remain pending. No Telegram network,
  production data, migration or deployment was used.

## GEOAI-021 — remote gate passed; GEOAI-022 next

- Exact feature commit `eecaad8e7ccef59a609a8d2ad3929071efb1de7e`
  passed GitHub `GEO AI checks` push run 40151771462 and draft PR #6
  run 40151774538. Full branch bundle SHA-256
  `94e5f42b799337de4bb0bd7696e2a09bf66a968acbc7921e9623544fad3455b4`
  matches on VM and Windows. The feature worktree was clean at that
  HEAD before this acceptance update; the original checkout and
  inherited workflow edit remain untouched.
- GEOAI-021 is ACCEPTED. P4 remains inside its 2026-10-25T05:35:44Z
  deadline. Docker is absent on VM109. GEOAI-022 is READY from this
  accepted base under `harness/build/022-staging-recovery.md`, with
  the same one-worker, two-repair and zero-spend bounds. No production
  service, migration, real credential or deployment was used.

## GEOAI-022 — local staging/recovery verified; remote CI pending

- From accepted 021 base and frozen 022 scope, candidate commits are
  `6e89cbf` and `922dc0d`. One repair fixed child-process bytecode
  writes into the checksum-verified release after the first backup
  correctly rejected release drift. The second staging root was clean.
- Exact Python 3.13.5 package lock SHA-256:
  `d8d2cf3756f29f64246f133f694ee61aa9711f8eb8e95c4fd2039734d381c351`.
  Rebuilding clean commit `922dc0d` reproduced archive SHA-256
  `6e487390aff13ba4517f7d542484c50f1bfd8a80f5bd8f0efb448883e7cc5684`.
  The compatible 021 archive SHA-256 was
  `f4d43b95bcb1b1367a56c401cd7d6c7544ec78c2e17f1c221ce12da64025a8c3`.
- Loopback HTTPS at localhost:18444 passed health 200 and anonymous
  projects 401. A synthetic owner imported the fixed 021 CSV, created
  a project/revision and retrieved DXF SHA-256
  `b07df55f418a0da843793302aab9f6629966e38283b40d68e0e6bab4d6ef13db`.
  Backup while active was refused; the server then stopped.
- The offline 254-file backup succeeded. Activating the 021 code on
  the same schema v5 state passed health, owner/project, source and
  result checks. A corrupted copied backup was rejected with no
  restore target; the good backup restored into a fresh root and
  passed the same HTTPS owner/project/source/result checks. Both
  staging servers stopped. No application log files, production data,
  Docker install, system change or deployment.
- Final repaired-commit gate `p4-022/final-gate-repaired.log` passed 124
  focused, 10 isolated regression and six isolated API tests, zero
  blocked operations, `pip check` and `git diff --check`. Exact
  feature/PR GitHub CI remains before acceptance and the P4 checkpoint.

## GEOAI-022 — accepted; P4 checkpoint and P5 start

- Exact feature/documentation HEAD
  `211cf1812224c0d77803837f96db8ef60aaaebe1` passed GitHub
  `GEO AI checks` push run 40152510544 and draft PR #6 run
  40152513257. The complete branch bundle SHA-256
  `e8e51c8406db43e016e0e48775a835965ce8dc81d39cc77560605858f8fbd69f`
  matched on VM and Windows. The feature worktree was clean at that
  HEAD before this checkpoint; the original checkout/inherited CI edit
  remain untouched.
- P4 tasks 021–022 are accepted inside its deadline, with one repair
  cycle in 022. Final local gate, code rollback, backup/restore,
  corruption refusal and HTTPS result verification are recorded above
  and in `harness/build/022-staging-recovery.md`. No staging service
  remains running; no real data, production service or deployment.
- P5 finite manifest is `/home/geoai/dev-data/geoai-autonomy/p5-run-manifest.json`.
  GEOAI-023 is READY from this accepted base under
  `harness/build/023-plan-viewer.md`; next step is bounded DXF plan
  extraction plus owner-scoped API and browser inspection.

## GEOAI-023 — local viewer/API checks; CI pending

- Accepted base: 022 at `211cf18`. Scope frozen in
  `harness/build/023-plan-viewer.md` and P5 manifest before code.
  One writable feature worktree, one compute worker and $0 external
  executor. No production data or deployment.
- Owner-scoped plan API projects verified DXF bytes with 8 MiB,
  10,000 expanded-entity and 50,000-vertex caps; no schema or DXF
  algorithm change. Unsupported bulged and curved/mesh polylines are
  reported rather than drawn inaccurately. Missing/foreign result,
  over-limit and invalid DXF use safe API responses.
- Synthetic HTTPS owner/job result returned 25 model-space, 46
  expanded entities on eight layers. DXF and plan hash match:
  `6f356b6fa75fc44c317b8dae4dccd35fdef33261a7c7ee80cb5491504d4b56cc`.
  Browser static fixture taken from that API demonstrated fit/zoom,
  pan, layer toggle, block selection/attributes and +1,000,000/
  +2,000,000 coordinate offsets with preserved shape. Console errors
  were zero. Browser used disposable HTTP static fixture; HTTPS API
  was verified separately with its self-signed certificate. The
  browser warning was not bypassed. Servers and tunnels stopped.
- Initial full local gate passed; one correctness repair added
  explicit unsupported handling for curved polylines. Final gate
  `p5-023/final-gate-repaired.log` passed 127 focused, 10 isolated
  regression and six isolated API tests with zero blocked operations,
  `pip check` and `git diff --check`. Both browser scripts passed
  Windows Node 24 syntax checks. Exact feature/PR GitHub CI remains
  before acceptance and GEOAI-024 scope freeze.

## GEOAI-023 — accepted; GEOAI-024 next

- Exact feature HEAD `24dad9cddfb90c9d4f5cad9d1dfed3415bfea534`
  passed GitHub `GEO AI checks` push run 40153380771 and draft PR #6
  run 40153383129. Complete branch bundle SHA-256
  `a923b30576764257606996ef39a4907c183e90f75fad4849632d88df9649a7a4`
  matched VM and Windows. The feature worktree was clean at that HEAD
  before this acceptance update; original checkout is untouched.
- GEOAI-023 is ACCEPTED. One correctness repair, final local gate,
  browser fixture and separate authenticated HTTPS API evidence are
  under `harness/build/023-plan-viewer.md`. No production server or
  real data used. GEOAI-024 is READY from this base under
  `harness/build/024-line-candidates.md`.

## GEOAI-024 — local A/B comparison passed; CI pending

- Accepted 023 base `24dad9c`; P5 scope frozen under
  `harness/build/024-line-candidates.md` at `c0a3727`. The only
  algorithm refactor exposes the existing exact line-code grouping
  and anchored nearest-neighbor order; direct old/current synthetic
  DXF semantics matched. No change to measured coordinates or DXF
  decisions.
- Fixed synthetic HTTPS request gave group `k1`: A P1,P2,P3,P4,
  B P1,P3,P4,P2, lengths 200 m and 100 m as descriptive features.
  Repeated GETs matched, source SHA-256
  `1092bb2deb3ffb67d333746ea393699e77850926f6b7d8251873c211d56cc8d0`
  and source bytes were unchanged; no job/decision created. Browser
  static fixture showed both variants and no accepted choice, with
  zero console errors. Authenticated HTTPS API was checked separately.
- Focused tests covered stable tie, duplicate/empty IDs, every count
  bound, invalid source/settings/length, owner boundary and safe API
  413/422. One repair covered malformed CSV and overflow handling.
  Final local gate `p5-024/final-gate-repaired.log` passed 131
  focused, 10 isolated regression and six isolated API tests,
  zero blocked operations, `pip check`, `git diff --check` and JS
  syntax on Windows Node 24. Exact GitHub push run 40154016183 and
  draft PR #6 run 40154019673 passed at feature HEAD `cbcd0f3`.
  Complete branch bundle SHA-256
  `091ca2cb2383cacda8919130bda6a503a8f0ca2092680a67224ca62c05f3cf8c`.
  GEOAI-024 ACCEPTED; GEOAI-025 READY from that base under
  `harness/build/025-decisions.md`. Original checkout untouched.

## GEOAI-025 — local verification passed; CI pending

- Accepted 024 base `cbcd0f3`; 025 scope frozen at `cc752e3`. Schema
  v6 migrates v5 without losing existing project data. Decisions are
  append-only, owner-scoped, idempotent by request UUID and protected
  by expected group version. A/B require eligible candidates; skip
  and manual do not apply a new order. History is paged and bounded.
- New job requests snapshot decision versions and A/B row indexes;
  worker/generator validate each accepted group against mapped source
  rows. Existing jobs retain their original request and result.
  Focused tests verified stale tab 409, foreign 404, bad provenance
  422, tampered snapshot 422, version migration, manual fallback and
  exact DXF A/B order. Source bytes remained unchanged.
- Final gate `p5-025/final-gate.log`: 133 focused, 10 isolated
  regression, six isolated API, zero blocked operations, `pip check`,
  `git diff --check`. Browser static synthetic controls showed A
  version 1 and manual version 2 with zero console errors. Separate
  authenticated HTTPS smoke with certificate verification showed
  A X=`0,100,1,2`, B X=`0,1,2,100`, source SHA-256
  `1092bb2deb3ffb67d333746ea393699e77850926f6b7d8251873c211d56cc8d0`.
  Temporary servers/tab stopped. Exact feature/PR CI pending.

## GEOAI-025 — accepted; P5 checkpoint and P6 start

- Exact feature HEAD `43fe7403af521ffc80822dcba8ead3a5b5aee23b`
  passed GitHub push run 40154708051 and draft PR #6 run
  40154711826. Full-branch bundle SHA-256
  `9b444af3d03dbfb344616eaf3f1e57bc828063fafd503cd98da5f18a200f20c8`
  matched VM/Windows. Worktree clean at this HEAD; original checkout
  untouched. GEOAI-025 ACCEPTED.
- P5 tasks 023–025 are accepted: plan viewer, explainable A/B
  candidates, versioned decisions applied to new DXF jobs. Synthetic
  HTTPS/browser checks and isolated gates passed; no real data,
  production deployment or migration. P6 manifest deadline
  2026-10-25T06:33:23Z; GEOAI-026 READY from accepted 025 under
  `harness/build/026-line-edits.md`. GEOAI-027 needs explicit
  reference provenance and permission before ingesting real examples.

## GEOAI-026 — local verification passed; CI pending

- Accepted 025 base `43fe740`; P6 scope frozen at `29dffdd`.
  Project schema v7 stores append-only edit events with CAS,
  idempotency and SHA-256 model snapshot. Controlled reorder, split,
  explicit join code, point membership move, undo and reset preserve
  measured source rows and reject stale/foreign access. A/B changes
  invalidate an edit model until explicit reset.
- New jobs snapshot exact edited segments and event/version; worker
  validates source membership and limits. Focused tests showed
  reordered/split/joined DXF and breaklines, old job result/request
  unchanged, v6 migration, invalid code/row, history and tampered
  model failures. Synthetic HTTPS (verified certificate) split DXF
  returned three expected line sequences; source SHA-256
  `ac8ee8cb0781c34932a9fd0c68b08f40eaf4ebae38012761b8b09de8cb24750a`.
  Browser showed saved reorder v3 and point IDs; console errors zero.
- Final bounded gate `p6-026/final-gate-bounded.log`: 137 focused,
  10 isolated regression, six isolated API, zero blocked operations,
  `pip check`, `git diff --check`; Windows Node 24 syntax passed.
  Disposable servers/tab stopped; no real data or production action.
  Exact GitHub feature/PR CI pending.

## GEOAI-026 — accepted; GEOAI-027 ready

- Exact feature HEAD `6285b1ada23053dc7fbfdc5d726d85d966a91fd6`
  passed GitHub push run 40155918471 and draft PR #6 run
  40155921751. Complete branch bundle SHA-256
  `512dfb668dcc522d67482b226fc3ded041e91654467e23e83a6eb923b0163ef6`
  matched VM/Windows. Worktree clean at this HEAD; original checkout
  untouched. GEOAI-026 ACCEPTED.
- GEOAI-027 READY from accepted 026 under
  `harness/build/027-reference-archive.md`. The archive must require
  explicit provenance and permission evidence and use only synthetic
  examples during development. No real reference files or rights
  were supplied in-session; no production action.

## GEOAI-026 integration correction — accepted

- While inspecting GEOAI-027's API wiring, found that the 026 HTML
  includes `/app/line-edits.js` but the FastAPI app did not serve it.
  The detached static browser harness had tested the script itself;
  the real app route would be 404. Added the exact static route and a
  focused authenticated app test requiring script status 200/content.
  Four focused line-edit tests passed. The repeat full gate
  `p6-026/static-route-gate.log` passed 137 focused, 10 isolated
  regression and six isolated API tests with zero blocked operations,
  `pip check` and diff check. Exact feature HEAD
  `5880fea3b9341ba371baa429fab9364cb87a1aac` passed GitHub push
  run 40156349260 and draft PR run 40156351787. Bundle SHA-256
  `b3f529b58c4331f8cb10ff646088dac3f5fe6b2e60d56fdd5a2faea9034a3bac`
  matched VM/Windows. GEOAI-027 implementation resumes from this base.

## GEOAI-027 — accepted; GEOAI-028 ready

- Corrected accepted base `5880fea`. Schema v8 stores a private,
  immutable reference DXF entry bound to an owned source revision and
  its SHA-256, explicit field/reference provenance, rights holder,
  permission evidence, permitted uses and fixed correction event IDs.
  Entry metadata and author/time are SHA-256 sealed; DXF downloads are
  size/hash-verified. Idempotency, owner count/byte quotas and a 25 MiB
  authenticated CSRF upload boundary are enforced. No automatic export
  or model training.
- Five synthetic archive tests passed: restart, owner/CSRF, rights,
  invalid/oversized bytes, quota, v7 migration, fixed correction
  snapshot and tamper detection. The final local gate
  `p6-027/accepted-gate.log` passed 144 focused, 10 isolated regression,
  six isolated API, `pip check`, zero blocked operations and diff check.
  Disposable verified localhost HTTPS passed create, idempotent repeat,
  conflict, list/download byte parity, permission rejection and
  unchanged source SHA-256. No real survey/reference or production action.
- Exact feature HEAD `f618613a5d832756671a47db3351c9e2f3f7397e`
  passed GitHub push CI 40156949699 and draft PR CI 40156952551.
  Complete branch bundle SHA-256
  `c019a3e0c02f805ada39f249b996d11253f0996eb92c407e64a7333fb93ac607`
  matched VM/Windows. Worktree clean at this HEAD. GEOAI-027 ACCEPTED.
  GEOAI-028 READY under `harness/build/028-dxf-comparison.md`.

## GEOAI-028 — local gate passed; CI pending

- Accepted 027 base `f618613`; scope frozen by `83b627f`.
  Read-only, authenticated comparison binds one archived reference to
  one successful job of the same immutable revision. Exact inventory
  handles points, lines, straight polylines, 3DFACE, blocks and labels;
  unsupported entities and unexpanded block contents are counted and
  mark the report incomplete. No geodetic tolerance, pass/fail
  judgement, data export or training is introduced.
- Five synthetic focused tests detect deliberately wrong block name,
  rotation, line geometry/layer, label, missing/extra point, invalid
  and oversized DXF, complexity limit, foreign owner, unrelated
  revision, tampered result and bounded examples. The final gate
  `p6-028/accepted-gate.log` passed 149 focused, 10 isolated
  regression and six API tests, `pip check`, zero blocked operations
  and diff check. Disposable verified localhost HTTPS compared the
  synthetic archive and job, reporting exactly one wrong line, layer
  and label; unauthenticated access was 401. No real data or
  production action. Exact feature/PR CI pending.

## P6 checkpoint — GEOAI-026, 027, 028 accepted

- Exact GEOAI-028 HEAD `1ea061c1afb4b75b0aba06ae67d402b0a3e815a6`
  passed GitHub push CI 40157505101 and draft PR CI 40157509671.
  Complete branch bundle SHA-256
  `0c79af963bf558a942582ed2fdc5acb1ad742fb595ad887ab7fd0c4fb5b68e3f`
  matched VM/Windows. Feature worktree clean; original checkout and
  inherited dirty workflow untouched. All P6 tasks accepted; three
  task checkpoint recorded. No real reference examples, production
  deployment or migration.
- Next candidate GEOAI-029 depends on accepted 028. Existing
  `autocad_assistance/templates/SinoKOD.txt` and
  `autocad_assistance/config.py` contain codes and block/layer mappings;
  assess provenance and conflicts before defining versioned rules.

## P7 preflight — GEOAI-029 ready

- Accepted 028 base `1ea061c`; P6 checkpoint saved. P7 manifest
  `/home/geoai/dev-data/geoai-autonomy/p7-run-manifest.json` has a
  2026-10-25T07:20:40Z deadline, 90 minutes/task, at most two repair
  cycles, one writable worktree/compute worker and $0 external spend.
- `templates/SinoKOD.txt` has 75 point rows; `config.py` has explicit
  block aliases, line prefixes and three layer overrides. The source
  is incomplete/ambiguous for some codes, so 029 will snapshot and
  expose only existing mappings, preserving unresolved/conflicts.
  `harness/build/029-object-catalog.md` is READY. No real data,
  new taxonomy or production action.

## GEOAI-029 — local gate passed; exact CI pending

- Accepted P6 base `1ea061c`; P7 scope frozen at `7ffeeeb`.
  `object-code-v1` snapshot preserves all 75 SinoKOD point rows,
  source-line and SHA-256 provenance, explicit block aliases, line
  prefixes/layer overrides and special support/tower settings. AST
  parser reads literal fields only; no `config.py` execution, `.env`
  read, DB migration or generator behavior change. Unmapped and
  competing mappings are recorded without invented precedence.
- Four focused tests passed deterministic source parity, conflict,
  lookup, malicious expression rejection and authenticated API.
  `p7-029/full-gate.log` passed 153 focused, 10 isolated regression,
  six API tests, `pip check`, zero blocked operations and diff check.
  Verified localhost HTTPS passed 401 without login and exact
  `moln`, `gaz1`, `tower1` lookups. No real data or production action.
  Exact feature/PR CI pending; GEOAI-030 waits for acceptance.

## GEOAI-029 — accepted

- Exact feature HEAD `79528bb9f6070e458724886a915f9d035cdfd110`
  passed GitHub push CI 40158200653 and draft PR CI 40158204850.
  Complete branch bundle SHA-256
  `25c91b6bd21aef2ce13e930e4e7a01188d06fdca5a65bfd1dfcf204b5e62cb07`
  matched VM/Windows. Worktree clean at this HEAD; original checkout
  untouched. Draft PR #6 description updated to current scope.
- GEOAI-030 dependency accepted. Current evidence is only synthetic;
  no authorized real held-out reference objects, class acceptance
  criteria or domain-approved tracing tolerance were supplied. An
  offline non-product candidate/benchmark can progress independently.

## GEOAI-030 preflight — synthetic experiment only

- Accepted 029 base `79528bb`. The current line baseline is anchored
  nearest-neighbor ordering; A/B and append-only edits already support
  explicit human decisions. No real reference corpus or class-level
  regression criteria exist in-session. A bounded 2-opt uncrossing
  suggestion and independent synthetic whole-object fixtures are
  frozen by `harness/build/030-tracing-experiment.md` and
  `harness/fixtures/030-synthetic-objects.json` before implementation.
  Valid self-crossings are possible, so the candidate cannot alter
  generated DXF or be called domain-validated. Full GEOAI-030 remains
  dependent on authorized real held-out objects and criteria.

## GEOAI-030 — synthetic experiment local pass; full task blocked

- Frozen fixture at `1ae3b57` was augmented only with family IDs to
  enforce whole-object split, without changing points or truth.
  Offline review-only 2-opt candidate starts from exact legacy
  anchored nearest order. It preserves row/XYZ input and reports
  source, baseline and candidate 2D length, self/environment crossings,
  turn reversals and ranked gaps; no API/jobs/DXF mutation.
- Three focused tests passed deterministic benchmark, invalid/limit
  cases and split isolation. Held-out synthetic class
  `uncrossing-helpful` improved matched edges 2/4 → 4/4; class
  `crossing-legitimate` regressed 5/5 → 3/5. Automatic adoption is
  unsuitable. Report `/home/geoai/dev-data/geoai-autonomy/p7-030-report.json`
  SHA-256 `24582b7cb5dccaaee70491ca3a33071b644aeac5acfeabfd4cdf42ada92de188`.
  Full gate `p7-030/full-gate.log` passed 156 focused, 10 isolated
  regression, six API, `pip check`, zero blocked operations and diff
  check. Exact feature/PR CI pending for the experimental commit.
- Full GEOAI-030 and dependent 031 cannot be accepted without
  authorized, independent real reference objects and agreed class
  regression criteria. No production action or real data was used.

## P7 checkpoint — experimental 030 accepted; full 030/031 blocked

- Exact experimental HEAD `8e30d74e3ba31505b0f8f1a9e065cb1e43cdfd2c`
  passed GitHub push CI 40158735797 and draft PR CI 40158740954.
  Bundle SHA-256
  `d220e62975df89cdcad4846249bce7fe471d2757e4ef2a4d82772d36e70c1f5c`
  matched VM/Windows. Feature worktree clean at this HEAD.
- P7 029 and the synthetic-only 030 experiment are accepted. Full
  GEOAI-030 is blocked by absent authorized independent real objects
  and per-class regression criteria; GEOAI-031 depends on it and is
  blocked. No implementation was started for 031. Proceed only with
  independently ready tasks such as GEOAI-036.

## P10 preflight — GEOAI-036 ready

- Accepted 025/027/028 satisfy the structural dependencies. P7
  030/031 remain blocked on real held-out objects and class criteria.
  P10 manifest `/home/geoai/dev-data/geoai-autonomy/p10-run-manifest.json`
  sets deadline 2026-10-25T07:37:48Z, one task/worker/worktree,
  90 minutes/task, two repair cycles and $0 external spend.
- GEOAI-036 READY under `harness/build/036-dataset-readiness.md`:
  a read-only owner-scoped audit of archive metadata with concrete
  blockers. GEOAI-027 permission is an unverified user assertion;
  there are no approved real examples, independent object-family IDs,
  reviewed labels or class-level acceptance criteria in-session.
  The audit cannot export data or start training. 037/038 are blocked
  until actual readiness is demonstrated.

## GEOAI-036 — local gate passed; exact CI pending

- Implemented owner-only, read-only `/api/v1/dataset-readiness` over
  bounded private archive metadata. The report counts user-asserted
  training/evaluation uses and enumerates concrete evidence gaps. It
  never reads raw reference bytes or emits permission text, and it
  always keeps readiness false under the current unverified schema.
- Three focused readiness tests cover empty/authenticated owners,
  assertion/privacy/foreign-owner isolation and tamper/limit failure.
  Full gate `p10-036/full-gate.log` passed 157 focused, 10 isolated
  regression and six API tests, `pip check`, zero blocked operations;
  `git diff --check` passed. Verified localhost HTTPS synthetic smoke
  passed with one reference, two use assertions, seven concrete
  blockers, false readiness and no permission-evidence leak.
- No real reference corpus or independently verified rights was used.
  GEOAI-037/038 remain blocked pending a passing later readiness audit.
  Exact feature push and draft PR CI are pending for 036.

## GEOAI-036 — accepted; P10 checkpoint

- Exact HEAD `e5663faec664e270da4ec21af004e9d5e6e5f792` passed
  feature push CI 40159298332 and draft PR CI 40159301340. Full
  bundle SHA-256 `0ed004d3d23dd5db59254178b34c5f7796972eadf154ed4bd585454d96619bee`
  matched on VM109 and Windows. Draft PR #6 description was updated.
  Feature worktree was clean; original checkout remains untouched.
- P10 036 accepted as a precise not-ready audit, not as approval to
  train. 037/038 are blocked by absent approved real examples, rights
  review, independent whole-object splits and class metrics.

## Independent package preflight after P10

- P8 032: `autocad_assistance/dxf_generator/surface.py` currently draws
  breaklines as polylines but calls point-only `scipy.spatial.Delaunay`;
  breaklines cannot affect those triangles. SciPy's published API
  accepts points without constrained segments. The `triangle` wrapper
  supports segments and holes, but the underlying author's licensing
  page says inclusion in commercial products needs a license. Shapely
  constrained triangulation accepts polygonal input and requires GEOS
  3.10; interior breakline handling still needs a design. No alternate
  library is installed in the clean venv. No geodetically validated
  reference sites, boundary/mask decisions or specialist acceptance
  are in-session. P8 is PROPOSED and not started.
- P9 034/035: the roadmap explicitly requires provided document forms,
  units, rounding and mandatory-field rules. None are supplied in the
  worktree or session; no forms or values have been invented. P9 is
  blocked pending these inputs.
- Current feature HEAD after 036 is `e5663fa`; next commit contains
  only checkpoint documentation. No production action or real data.

## GEOAI-030 — owner DXF intake; full validation remains blocked

- Owner supplied one completed DXF used in an engineering-geodetic
  report, and confirmed that its original field TXT is unavailable.
  The file is 202,633,692 bytes, AutoCAD DXF `AC1027`; its Windows
  and private VM109 copies matched SHA-256
  `3b1fa964d205b774967855211e2a43b8fe0b56566dcbff272eaf0232811f98df`.
  The copy and constant-memory inventory are stored outside Git under
  private VM109 staging with directory mode 700 and files mode 600.
- Read-only scan completed with zero malformed group-code pairs and
  counted 457,748 entities: 42,718 POINT, 9,268 LWPOLYLINE,
  163,447 LINE, 97,385 3DFACE, plus other entities. It emitted only
  aggregate metadata; no coordinates, labels or raw drawing bytes
  were committed or published.
- The DXF can support a reviewed output inventory, but no independent
  source-to-reference mapping or whole-object held-out benchmark can
  be derived responsibly from this single final drawing. Original
  point codes, object labels, class regression criteria and rights for
  model training/publication are not established. The synthetic 030
  candidate stays review-only; full 030/031 and 037/038 remain blocked.
  Feature base was clean `dcc00b7` before this documentation update.
- A second private, read-only two-pass scan compared exact XY equality
  without a tolerance or coordinate export. There were 42,716 unique
  `POINT` XY pairs; among major plan layers, only 1 of 38,898 road
  `LINE` endpoints and 4 of 289,196 ordinary contour polyline
  vertices coincided exactly with a `POINT` XY. This diagnostic does
  not prove source provenance, but rules out assuming that the final
  drawing directly labels the survey-point sequence. Its private
  aggregate report remains outside Git.

## GEOAI-039 — exact release candidate, isolated acceptance, partial final gate

- Accepted dependencies 018, 021–022, P0–P6 and 029 were verified.
  The chosen release is exact ancestor `79528bb9f6070e458724886a915f9d035cdfd110`,
  whose feature/PR CI runs 40158200653/40158204850 succeeded. The
  release archive SHA-256 is
  `cada7fb4f2919fe321cffbe74beeec499bc60e833e33f36a94f404560f91ce81`;
  an independent `git archive` rebuild matched exactly. Python 3.13.5,
  33-package lock SHA-256
  `d8d2cf3756f29f64246f133f694ee61aa9711f8eb8e95c4fd2039734d381c351`
  and schema v5 were verified. The archive contains no 030 experiment
  or 036 readiness API. The current development HEAD is not the release.
- A first test invocation ran inside a staged release and created
  `bot_shutdown.log`; immutable verification correctly rejected it.
  Root cause was a focused Telegram import. The tainted stage was
  preserved for diagnosis. The suite was rerun on a separate extracted
  copy of the exact archive, leaving a newly built stage verified.
  A subsequent owner-seeding import created exactly three Python
  bytecode cache files; only those diagnosed extras were removed, and
  the stage verified again. All later imports disabled bytecode writes.
  These were acceptance-process repairs, not product-code changes.
- The final isolated release gate passed 151 focused tests, 10
  regression and six API tests in 77.516 seconds, `pip check`, and zero
  blocked network/dotenv/write/process operations in the isolated
  bootstrap reports. Focused checks include nine calculation-job tests,
  six resource-limit tests, seven upload-security tests and three
  ownership tests. The checksum-verified stage remained immutable
  through the subsequent HTTPS checks.
- Verified localhost HTTPS synthetic flow passed owner login,
  anonymous 401, CSV import, project/revision, job and DXF download
  (source/result SHA-256 recorded privately), plan JSON, A/B decision
  replay/stale rejection and distinct DXF orders, controlled line edits,
  reference archive upload/download, exact DXF comparison, and the
  75-entry object-code catalog. Fixed import/job smoke elapsed 2.441
  seconds. The plan exposed three unsupported LWPOLYLINE bulges from
  this fixture; an older fixture-specific smoke expectation of zero
  was diagnosed, and the endpoint/hash checks passed with explicit
  unsupported reporting. The app supports one provisioned owner in
  this configuration; cross-owner isolation was verified by focused
  tests with separate auth roots, not by two live accounts.
- A sampled staging server high-water mark after the main workflow was
  331,564 kB; this is a small synthetic workload, not a production
  concurrency or site-capacity guarantee. No application log files,
  request bodies or credentials were emitted in stage logs. Backup
  while the service ran was refused without creating a target.
- After stopping the server, an offline backup of 339 files succeeded;
  its manifest SHA-256 is
  `b6580c757fc332649e5a8b072f36a337b5a7298e24d32ab310d7a670bc1f461e`.
  Switching code to compatible accepted P6 commit
  `1ea061c1afb4b75b0aba06ae67d402b0a3e815a6` preserved HTTPS
  health, owner/project, source and DXF SHA-256. The same backup
  restored to a fresh root with candidate 79528bb and passed HTTPS
  owner/source/result checks and release-file integrity. A separately
  corrupted copy was rejected before the restore target existed.
  All three disposable server processes are stopped; no real data,
  production service, merge or publication was touched.
- GEOAI-039 remains PARTIAL: an actual target, acceptable load/error
  thresholds, monitoring and operational owner, and a reviewed
  migration/no-migration decision are absent. GEOAI-040 requires full
  sign-off and separate authorization. Materials for 030–038 are
  consolidated in `harness/build/missing-materials.md`; the concrete
  proposed rollout/rollback steps are in
  `harness/build/039-deployment-plan.md`. Source HEAD before this
  documentation commit was clean `75b02eb`.

## GEOAI-039 closed-pilot preparation — 2026-10-25

- Scope was read-only infrastructure survey plus feature-branch
  configuration/instructions. No pilot, deployment, merge, network,
  secret, working-data or running-service change was authorized.
  Worktree began clean at `108d6367b331908a178df0cbb4ad27af272d3969`
  on `codex/geoai-current`.
- VM109: Debian 13.7, 2 vCPU, about 3.9 GiB RAM and 50 GiB free;
  active loopback development servers. CT108: Debian 13.6, 2 vCPU,
  4.0 GiB RAM and 24 GiB free; NetBird, mail and MCP-ops in use.
  Neither is selected for the pilot. No Docker found on either; the
  repository Dockerfile/Compose/main workflow target the Telegram bot.
  The actual bot host and hypervisor free capacity are unknown.
- Proposal: new isolated Debian 13 VM, 2 vCPU, 4 GiB RAM, 60 GiB disk,
  private HTTPS/VPN only, app bound to loopback, one owner/two browser
  sessions and one compute child. Exact VM/IP, capacity, DNS/TLS,
  clients and operator await owner confirmation. Candidate tar contains
  144 tracked files, 8,570,880 bytes; commit, archive and lock SHA are
  in `harness/pilot/release-79528bb.json`. The existing tar remains
  outside Git on VM109 and was not sent to a pilot target.
- New empty pilot state needs no migration. Code check corrected the
  earlier ambiguous "schema v5": projects SQLite is user_version 8,
  auth SQLite is user_version 1; v5 names the staging manifest format.
  Compatible P6 code rollback on a copy was previously verified; no
  new migration or rollback test was repeated.
- Measured synthetic smoke 2.441 s and sampled server VmHWM 331,564
  kB are explicitly separated from proposed target p95, concurrency,
  memory, disk and error thresholds in
  `harness/build/039-pilot-preparation.md`. Existing product gates
  were not rerun because no product code or candidate archive changed.
  The pilot ASGI adapter/TLS/unit, target load result, responsible
  operator and final sign-off remain open. GEOAI-039 is PARTIAL and
  GEOAI-040 BLOCKED.

## GEOAI-039 operational overlay technical preparation — 2026-10-25

- User authorized code/tests/docs, local commits, feature push and draft
  PR update but not VM creation, network changes, real data, merge or
  pilot launch. Working tree began clean at `0b0eaf070dfa73632ecacc7fe2faf6815b6695b3`.
  Product archive `79528bb9f6070e458724886a915f9d035cdfd110.tar`
  remained byte-identical, SHA-256
  `cada7fb4f2919fe321cffbe74beeec499bc60e833e33f36a94f404560f91ce81`.
- Operational overlay implementation was committed at
  `aa74a11abe4b26fffc82c659e33237127618d005`; the validated TLS
  template was committed at final package source
  `7f5bbecbb05a9f86f9850ed7e045a49fde040b89`, tree
  `dab84ce2892da719a5eed7c1b1e42ed4eb50b60f`. Its 8-file
  `git archive` is 40,960 bytes, SHA-256
  `71c330b1252c54f1d67f488ff0e39aae98a7b521d3fcf074fda4c15a2fb5213c`;
  independent rebuild matched byte-for-byte. Overlay is not inside the
  product archive. Full two-component and P6 rollback provenance is in
  `harness/pilot/combined-manifest.json`.
- Five focused config tests passed. The exact **packaged** overlay with
  the exact 79528bb archive passed a disposable synthetic HTTPS flow:
  upload/preview/revision, three queued/running/succeeded jobs, DXF
  result 4,287,358 bytes, anonymous 401, foreign-session 401,
  foreign-Origin 403, restart with unchanged result SHA, active
  backup/restore refused, offline backup of 27 files/restoration and
  tampered-backup rejection. The same overlay started accepted P6
  `1ea061c1...` on restored v8 state and served the same DXF SHA.
  Evidence file SHA-256
  `61cae027e5ba87095c23784ac57e4e6448fa1ca59fb8f8e0d13ac8de81da5d97`
  under `/home/geoai/dev-data/geoai-autonomy/pilot-combination-packaged-v2/`.
  The verifier independently rebuilt both Git archives and checked
  individual overlay file SHA values. No product gate was rerun.
- Independent Windows copies of the 79528bb product tar, final
  `7f5bbec` overlay tar and P6 rollback tar were saved under
  `C:/Users/krog0/OneDrive/Документы/ChatGPT/Assistance/geoai-pilot-prep/artifacts/`;
  all three SHA-256 values matched the combined manifest. These are
  artifact copies, not a deployment.
- Read-only VPN survey: CT108 NetBird 0.81.2, IP 100.104.140.204,
  two connected peers and no Networks. `pve1.netbird.cloud`
  resolves to 100.104.86.94 but is unreachable from CT108 (SSH/22
  no route, API/8006 unavailable); Windows has no NetBird route and
  cannot reach ports 22/8006. VM109 has no NetBird client.
  Proxmox reserve, free VM ID and address/DHCP inventory remain
  unverified; no ID/IP was called free. Official Caddy 2.11.7 was
  downloaded only to dev-data, its Linux tar SHA-512 matched the
  release checksums, and a synthetic rendering of the final TLS
  template passed `caddy adapt`/`caddy validate` with a single
  bound HTTPS listener and no HTTP redirect. Real VPN IP/certificate
  remain untested. `systemd-analyze verify` parsed the unit
  but reported the expected absent target Python path.
- GEOAI-039 remains PARTIAL for designated VM/resources, target load,
  approved VPN clients/thresholds, operator/monitoring and release
  sign-off. GEOAI-040 remains BLOCKED. No infrastructure or working
  service was changed.

## GEOAI-039 target VM report — 2026-10-25

- Owner supplied a read-only PVE1 report: VM 110 `GEOAI` is running
  with autostart; Debian 13.7, hostname `debian13-new`, 2 vCPU,
  4 GiB RAM, 60 GiB disk, about 56 GiB available and DHCP
  `192.168.1.162`. SSH/22 is enabled; `geo-admin` uses password/sudo
  and `openclaw` uses SSH key. Credential location was described as
  Vaultwarden; no credential was read or copied. Failed systemd units
  were reported absent. These are owner-reported facts, not a login
  or direct Proxmox inventory result.
- Owner reports no swap, nftables firewall, public DNS, reverse proxy,
  NetBird or Proxmox backup schedule on VM 110. Current DHCP IP is not
  confirmed stable. Windows read-only TCP probe reached
  `192.168.1.162:22`; `ssh-keygen -F` found no pinned host key in
  the local known_hosts, so no SSH login was attempted.
- Candidate target is now VM 110. Before pilot launch: verify host
  identity/access, approve private VPN/TLS/client list and stable
  address, choose off-VM backup location/retention and test restore,
  measure target load/memory with no swap, and record operator/window
  and release approval. No VM settings, network rules, secrets,
  running services, real data or pilot state were changed. GEOAI-039
  remains PARTIAL and GEOAI-040 BLOCKED.

## GEOAI-039 VM110 technical preparation — 2026-10-25

- The owner authorised VM110 preparation and a limited synthetic pilot after
  private-access and off-VM restore gates. Console-confirmed SSH host identity
  was pinned and `ssh geoai-pilot` succeeded as `openclaw`; `sudo -n` works.
  Guest netplan directly shows static `192.168.1.162/24`, rather than DHCP.
- The Git-source verifier on VM109 rebuilt exact product `79528bb` and separate
  overlay `7f5bbec` archives and checked all eight overlay file hashes.
  Independent Windows and delivered VM110 tar hashes matched the combined
  manifest. The P6 rollback tar matched its recorded hash.
- VM110 now has a dedicated service user and isolated code/state/backup/log
  directories. Python 3.13.5 venv `pip check` passed; `pip freeze` SHA-256
  equals the release lock. Official Caddy 2.11.7 tar hash matched the
  manifest. NetBird 0.81.2, nftables and Certbot DNS-Cloudflare are installed.
  Both pilot systemd units remain disabled/inactive. The exact-release pilot
  config and empty marked state passed `geoai_pilot_ops check` (144 files).
- Local nftables default-deny input is enabled. It preserves LAN SSH and
  allows TCP 22/443 on future NetBird `wt0` only from the two owner-selected
  observed peer IPs. Fresh SSH login succeeded after applying the rules;
  timed rollback units were cancelled. No 443/18460 listener exists.
- VM110's separate synthetic target check passed HTTPS, 401/403 access,
  three queued/running/succeeded jobs, DXF, restart preservation, 27-file
  backup/restore, tamper refusal and P6 rollback compatibility. This is a new
  target-environment check, not a repeat of GEOAI-030 experiments.
- The owner selected NetBird group/clients, `geoai.exitline.site`, Cloudflare
  DNS-01, and Proxmox storages `backup-fast-nfs`/`backup-weekly-nfs` with
  proposed retention. NetBird still needs a one-use setup key, Cloudflare a
  scoped DNS token. Neither secret is in chat/Git. PVE storage/schedule access
  and schedule remain unverified. A VM110 synthetic backup was transferred
  to VM109 with matching SHA-256 and restored to a new root; SQLite versions
  1/8 and quick checks passed, and the restored DXF SHA matched VM110.
  This temporary copy is not the selected retention destination.
  No shared VPN policy or Proxmox
  schedule was changed. Full target evidence and next gates are in
  `harness/build/039-vm110-pilot-execution.md`; GEOAI-039 remains PARTIAL.

## GEOAI-039 private hostname correction — 2026-10-25

- The owner confirmed `geoai.froglight.ru` in the Reg.ru-managed home DNS
  zone, superseding the earlier `geoai.exitline.site`/Cloudflare plan.
  Public NS for `froglight.ru` are `ns1.reg.ru` and `ns2.reg.ru`.
  VM110 `/etc/geoai-pilot/config.json` was changed to the new HTTPS origin;
  a pre-change copy was preserved and `geoai_pilot_ops check` passed again
  with the exact 79528bb archive and lock. Pilot services remain inactive.
- NetBird still reports `NeedsLogin`; the one-use setup key is not yet in
  the root-only file, so the VM110 VPN IP is unknown. No A or ACME TXT
  record was created. A manual Reg.ru DNS-01 challenge or separately
  reviewed API method is required for a public certificate. The earlier
  Cloudflare-token request is obsolete.

## GEOAI-039 VM110 NetBird enrollment — 2026-10-25

- Owner provided a root-only one-use NetBird setup key on VM110. File mode
  and owner were checked without reading it into logs; `netbird up` connected
  to the existing managed control plane. The local setup-key file was then
  deleted. VM110 FQDN is `geoai.netbird.cloud`, NetBird IP
  `100.104.46.7/16`, interface `wt0` and UDP port 51820. Initially the
  only visible peer was `desktop-l4bb2vp.netbird.cloud`; the selected
  `openclawagent` peer was absent, so both-client access is unverified.
- The owner was given A-record fields `geoai` -> `100.104.46.7` for the
  Reg.ru zone. No record was changed by Codex. The exact Caddy template was
  rendered for `geoai.froglight.ru` and VPN IP `100.104.46.7`;
  `caddy adapt` passed. Certificate is not issued and both pilot services
  remain inactive. No public listener or global VPN policy was changed.

## GEOAI-039 Reg.ru DNS and pending ACME challenge — 2026-10-25

- The owner created A `geoai.froglight.ru` -> `100.104.46.7`. Both
  `ns1.reg.ru` and `ns2.reg.ru` returned that exact A record.
- Certbot 4.0.0 registered the ACME account with the owner-provided contact
  email and requested a manual DNS-01 TXT value for
  `_acme-challenge.geoai.froglight.ru`. The value was sent to the owner for
  entry in Reg.ru. The owner reported it entered, but the authoritative
  servers have not returned it yet. Certbot remains waiting; no ACME
  validation or certificate issuance has been attempted.

## GEOAI-039 private certificate issued — 2026-10-25

- The exact DNS-01 TXT value appeared on both Reg.ru authoritative servers.
  Certbot then completed the challenge and issued a certificate for
  `geoai.froglight.ru`, SAN matching the name, valid from 2026-10-25
  12:38:04 UTC to 2027-01-23 12:38:03 UTC. Chain verification against the
  system CA succeeded with the intermediate supplied separately.
- Fullchain and key were installed under `/etc/geoai-pilot/tls/` as
  root:caddy mode 0640; `caddy validate` passed when executed as the
  service user. The app and TLS units remain inactive. Manual Certbot
  certificates do not auto-renew, so the renewal timer stays disabled;
  a new Reg.ru TXT challenge is required before expiry.
- `ns1.reg.ru`, `ns2.reg.ru` and public resolvers returned A
  `100.104.46.7`; VM110's configured resolver `192.168.1.1` still
  returned name not found after VM110's local resolver cache was flushed,
  while the ACME TXT resolved. This may be router cache or filtering;
  no router/DNS change was made. Only the desktop NetBird peer was
  visible on VM110, so the second selected access path remains unverified.

## GEOAI-039 private client and firewall recheck — 2026-10-25

- The owner chose to retain VM110 instead of moving the pilot to a VPS. No VPS or public entry point was configured.
- On VM110, NetBird 0.81.2 remained connected as `geoai.netbird.cloud` at `100.104.46.7` and reported only the approved desktop peer `100.104.97.169`. A read-only check on separate `mcp-ops` found both desktop and `openclawagent.netbird.cloud` (`100.104.100.176`), confirming that the second peer is online but not yet in VM110's peer map. Owner verification of GEOAI-Clients group/policy is pending.
- This local Windows host is `WIN11`, not `DESKTOP-L4BB2VP`, and has no NetBird client. Its router resolver `192.168.1.1` returned NXDOMAIN for `geoai.froglight.ru`; direct query to `8.8.8.8` returned `100.104.46.7`. Approved client DNS checks are pending. No router or shared VPN DNS change was made.
- NetBird inserted a blanket `wt0` accept into nftables input chains, including an attempted input guard. A corrected early `prerouting` guard now limits decrypted `wt0` ingress to the two selected source IPs on TCP 22/443; later NetBird ACL rules still apply. `nft -c` passed. The installed `/etc/nftables.conf` and versioned `harness/pilot/vm110-nftables.conf` match SHA-256 `24111e37bd82912e8f7ab6cd72731c896a43ec6730b9341d683c4dd939f177be`. Fresh LAN SSH, NetBird management, and the desktop peer connection remained active; rollback timers were cancelled. Do not restart nftables alone while NetBird is active because the file's `flush ruleset` also removes the NetBird ACL until its daemon reinstalls it.
- The application and TLS units remain disabled/inactive. No port 443 or 18460 listener exists. Exact archive and off-VM synthetic restore results are unchanged; no completed test was repeated.

## GEOAI-039 bounded VM110 synthetic session — 2026-10-25

- Both selected NetBird peers became connected to VM110: desktop `100.104.97.169` and openclawagent `100.104.100.176`. VM110's NetBird ACL admitted TCP 22/443 from both; the independent nftables prerouting guard remained intact. The owner checked `geoai.froglight.ru` -> `100.104.46.7` and HTTPS `/health` = 200 with valid TLS from the desktop. Unapproved CT108 could not connect to TCP 443.
- Before launch the product, overlay and P6 archive SHA-256 values matched the manifest; `geoai_pilot_ops check` passed exact product and lock, Caddy validated, and the certificate was valid. A `geoai-owner` account was provisioned; its generated password is root-only on VM110 at `/etc/geoai-pilot/private/owner-password` and was never printed or committed. App and TLS units were started without enabling autostart. ASGI listened only on `127.0.0.1:18460`, Caddy only on `100.104.46.7:443`.
- Live HTTPS smoke passed owner login, 401 anonymous, 403 foreign Origin/missing CSRF, project, upload, preview, revision, queued job and DXF. The small job took 2.026 s; DXF SHA-256 `568a75f2afd98767db205df25645f3c228ac7bdafe19460b32b7dc0e3aec0d4d`.
- Target load: 100 authenticated API requests from two sessions, p95 3.4 ms, zero 5xx; UI shell 1.2 ms. Queue initially contained one running and two waiting. 20/20 small synthetic jobs succeeded with unique IDs, maximum observed 2.06 s; cgroup peak 405.8 MiB and disk growth 163.9 MiB. A 10,000-point, 1,050,026-byte CSV yielded an 11,765,787-byte DXF in 5.35 s; peak cgroup memory 511.7 MiB.
- The agreed upper-bound input of 100,000 points and 10,000,026 bytes uploaded in 0.5 s and was admitted. Its job failed `WORKER_FAILED` after 23.81 s, cgroup peak 1033.5 MiB. Worker traceback ended in `OSError: [Errno 27] File too large` while ezdxf wrote output: the exact product sets `RLIMIT_FSIZE` to 25 MiB. This is an after-admission failure, so the approved upper-bound criterion is **not met**. No product or overlay code was changed to hide it.
- With services stopped, the overlay backed up 136 synthetic files and checked SQLite versions 1/8. The compressed backup was copied to VM109, matching SHA-256 `22313a7a4550d5202d5609cd2032fd55ce88364317be0088659b0a654daf9402`, restored into a fresh root, and passed exact product verification. Restored DXF SHA matched the source. VM109 remains a temporary test site, not the selected retention storage.
- Restarting VM110 app and TLS preserved owner login, prior succeeded job and DXF hash. Both units were then stopped and remain disabled/inactive. No 443/18460 listeners remain; SSH, NetBird and nftables are active. About 54 GiB disk is free. No permanent monitoring, Proxmox schedule, production data, public exposure, router/DHCP/shared VPN policy change or PR merge occurred.
- GEOAI-039 remains PARTIAL. Next decision: restrict the pilot to a newly agreed verified workload, or prepare a separately reviewed release that handles the 100k-point boundary. Do not start user acceptance under the currently approved upper-bound criterion. See `harness/build/039-vm110-pilot-execution.md`.