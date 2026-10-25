# GEOAI-021 — end-to-end web MVP acceptance against Telegram

Status: READY. Base: accepted GEOAI-020 feature commit
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
