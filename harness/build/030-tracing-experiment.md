# GEOAI-030 — offline tracing experiment; domain validation remains open

Status: READY for synthetic, read-only experiment after accepted
GEOAI-029 at `79528bb9f6070e458724886a915f9d035cdfd110`.
Full GEOAI-030 production acceptance is blocked by absent authorized
held-out topographic objects and agreed per-class regression criteria.
The P7 manifest deadline is 2026-10-25T07:20:40Z, with 90 minutes
for this task, at most two repairs, one worktree/compute worker and
$0 external executor.

## Bounded work

Implement an offline candidate that starts from the existing anchored
nearest-neighbor order and removes strict self-intersections by a
deterministic 2-opt reversal. This is only a review suggestion: some
valid objects legitimately cross, so it must never change jobs,
accepted A/B choices, line edits or the generated DXF automatically.
Report source-order and baseline/candidate sequence, 2D length,
self-crossings, turning reversals, ranked long gaps (potential breaks)
and crossings with explicitly supplied surrounding lines. Keep source
row IDs and XYZ immutable. Limit one line to 100 points and context to
10 lines of 100 points each; bound work and reject nonfinite input.

Freeze a small synthetic object fixture before implementation with
separate development and held-out object IDs; versions of an object
may not cross the split. Include a simple line, a case where uncrossing
helps, and a deliberately valid crossing where it hurts. Compare exact
undirected edge overlap with the labelled sequence and report per-class
baseline/candidate outcomes, including regressions. No absolute
coordinate tolerance, success threshold or domain approval is
inferred from these synthetic cases.

Allowed files: offline service, benchmark CLI and synthetic fixture,
focused tests, this spec and shared memory. No API/product activation,
DB migration, generator change, real data, production action or new
dependency.

## Acceptance and commands

1. Candidate is deterministic, preserves each point exactly once, and
   removes strict crossing in the positive fixture. Its report exposes
   a regression in the legitimate-crossing fixture; it does not claim
   universal improvement.
2. Hold-out split is by whole object; the benchmark emits raw and
   per-class metrics for source, current baseline and experimental
   candidate. Limits, duplicates, nonfinite coordinates and invalid
   truth fail safely; no project or DXF bytes are written.
3. Focused `python -m unittest -v tests.test_trace_experiment`, full
   `scripts/geoai-ci-checks.sh` with clean venv/outside report root,
   `git diff --check`, repeatable benchmark output and exact feature/
   PR CI pass. Record synthetic-only limits and missing real validation.

Do not mark full GEOAI-030 accepted until authorized, independent
real references and class-level regression criteria support it. Stop
on budget, unexpected edits, lost isolation or production action.
