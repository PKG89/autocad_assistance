# GEOAI-021 — end-to-end web MVP acceptance against Telegram

Status: ACCEPTED at `eecaad8e7ccef59a609a8d2ad3929071efb1de7e`. Base: accepted GEOAI-020 feature commit
`91aeb53ad410abdc071498a4d22e561db3684dbe`; 018–020 and remote
007B CI passed. P4 deadline: 2026-10-25T05:35:44Z.

## Scope

Exercise the same fixed, synthetic TXT/CSV field file and explicit
mapping, coordinate labels, scale and TIN settings through the
authenticated web upload/preview/import/job/download API and the
existing Telegram file/mapping/generation handlers with a fake update,
context and bot. Do not start polling or contact Telegram. Reuse the
shared survey and DXF engine without changing geodetic calculations.

Compare parsed row counts, exact measured XYZ/IDs/codes/comments,
source provenance and warnings. Parse the two generated DXFs with
`ezdxf` and compare a canonical semantic inventory: supported model
space entity type, layer, block/text attributes, insertion/geometry
and scale or rotation. Ignore only volatile handles, ownership IDs,
timestamps and nonsemantic ordering. Add a negative comparator check
that deliberately changes a coordinate, layer or block and must fail.
Record unsupported entity types explicitly; no byte-for-byte DXF
requirement and no invented geodetic tolerance.

Measure wall time and peak memory for this fixed fixture, including
the web child process and Telegram in-process path, in a repeatable
local harness. Record raw measurements and environment; do not invent
a pass threshold. A browser smoke check should confirm the user can
reach the completed job and verified download without a terminal.

Candidate files: focused acceptance tests and harness script/data,
small adapter fix only if parity exposes a root cause, docs and shared
memory. Keep one worker and one writable worktree. No real survey,
real Telegram token, chat message, production data, deployment,
new package/system install, auth weakening or geometry rewrite.

## Acceptance

1. Both adapters process the identical fixture and declared options;
   preview/mapping/provenance agree and semantic DXF inventories match.
   Deliberately modified geometry must fail comparison.
2. Web browser completes a disposable synthetic user flow through
   result download; no Telegram network call or credential is made.
3. Repeatable wall/memory evidence is recorded. Current focused,
   isolated regression/API, `pip check`, `git diff --check`, JS syntax
   when touched, and exact GitHub feature/PR CI pass.

Actual full gate: `GEOAI_PYTHON=/home/geoai/dev-data/geoai-autonomy/p0-007b/clean-venv/bin/python GEOAI_TEST_REPORT_ROOT=/home/geoai/dev-data/geoai-autonomy/p4-021/final-gate bash scripts/geoai-ci-checks.sh`.

Budget: 90 minutes, initial attempt and at most two repairs; P4
manifest limits the package to four hours, one writable worktree,
one compute worker and $0 external executor spend. Stop on an
unaccepted dependency, lost isolation, unexpected edits, missing
domain data/decision, exceeded budget or unauthorized production
action; record HEAD, diff, checks and blocker before any pause.

## Implementation and local evidence

- Fixed fixture `harness/fixtures/021-field.csv` has SHA-256
  `b02424ae3df178448b4c9e620887b7e2c9e6fbba6401b5337a32e270221868e6`.
  An isolated test runs real authenticated web upload, preview, mapped
  revision, queued child calculation and verified result download. The
  same bytes pass Telegram's offline file, mapping, scale and generation
  handlers with a synthetic update and bot; no polling/token/network.
- Initial semantic comparison reproduced a web scale bug: the web job
  passed plan denominator 500 as a DXF multiplier, while Telegram
  passed 0.5. A shared denominator-to-drawing helper now gives both
  1:500 the same render factor without modifying measured XYZ. The
  browser label explicitly calls the input `1:N`.
- Accepted inventories have 25 model-space entities with identical
  geometry/attributes, including a block reference, point coordinates,
  layers, text formatting and selected ground TIN. Handles and owner
  IDs are excluded; unsupported types are reported and currently zero.
  Moving one point by one unit makes the comparison fail. Preview rows,
  mapped values, source SHA and warning codes also match.
- Final isolated sample on Linux 6.12.107 / Python 3.13.5: web flow
  1.977219 s, offline Telegram flow 1.39428 s; parent and child
  process peak RSS each reported 296816 KiB by `resource` for the
  overall test process family. These are raw observations on a small
  synthetic fixture, not performance pass thresholds.
- Disposable browser fixture used the same CSV: login, selected
  revision, submitted job, observed success and downloaded the
  accepted DXF through the UI (`GET /result` 200). Its server and
  SSH tunnel were stopped. No real data or deployment was touched.
- Full local gate log is
  `/home/geoai/dev-data/geoai-autonomy/p4-021/final-gate-exact.log`;
  it passed 121 focused, 10 isolated regression and six isolated API
  tests with zero blocked operations, plus `pip check` and diff checks.
  GitHub `GEO AI checks` push run 40151771462 and draft PR #6 run
  40151774538 passed at the exact commit. Full branch bundle SHA-256
  `94e5f42b799337de4bb0bd7696e2a09bf66a968acbc7921e9623544fad3455b4`
  matched on VM and Windows. No production action ran.
