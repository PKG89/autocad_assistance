# GEOAI-024 — explainable A/B line-connection candidates

Status: READY. Base: accepted GEOAI-023 feature commit
`24dad9cddfb90c9d4f5cad9d1dfed3415bfea534`; 012, 015, 020–023
dependencies passed local and exact GitHub feature/PR checks. P5
manifest: `/home/geoai/dev-data/geoai-autonomy/p5-run-manifest.json`;
deadline 2026-10-25T05:58:12Z. Task ceiling: 90 minutes.

## Scope and immutable boundary

For a verified, owner-scoped TXT/CSV project revision, show two
**proposals** for each eligible controller line-code group: A is the
recorded survey-row order; B is the current DXF builder's
first-point-anchored nearest-neighbor order. Preserve its exact
grouping and stable tie behavior by extracting/reusing small pure
helpers from `dxf_generator/polylines.py`. Do not infer that shorter
means geodetically correct, choose a winner, persist a decision or
change the approved DXF/Telegram output. P5-025 will save decisions.
The roadmap's `line_review` prototype is not present in this checkout;
do not substitute an unverified external implementation.

Return a versioned JSON comparison containing project/revision ID,
source/settings SHA-256 and generator/candidate algorithm versions;
for each eligible exact code group, immutable point IDs, survey row
indexes and local XYZ, A/B sequences, descriptive 2D length and
reordering features, clear reason codes, and an explicit `sameOrder`
flag. Empty/duplicate IDs or ambiguous groups must abstain with
reasons. Never replace measured XYZ or invent a geodetic tolerance.
The browser can request this comparison for a selected revision and
read both sequences/reasons without writing any choice.

Bounds: at most 200 line groups, 500 eligible points per group, and
5,000 eligible points total. Exceeding a bound gives a safe 413; an
invalid/tampered source or settings gives safe 422; a missing or
foreign project/revision gives 404. No result should include raw file
paths. No new DB schema or network dependency.

Candidate files: `dxf_generator/polylines.py`, a small
`services/line_candidates.py`, owner-scoped project router,
`api/web/*`, focused tests, this spec and shared memory. Preserve
working 023 viewer, 021 web/Telegram parity and existing DXF shape.

## Acceptance and gates

1. A deliberate zigzag fixture produces different A and B; B's
   point-coordinate order exactly equals the current builder's order.
   Stable ties and repeated calls yield the same sequences. Actual
   DXF bytes from the old generation path remain semantically equal.
2. Malformed/duplicate IDs abstain, unauthorized access fails, source
   integrity errors and every bound fail safely. Browser displays
   both candidates/reasons for an owned revision, with no mutation.
3. Focused tests, current isolated regression/API tests, `pip check`,
   JS syntax, `git diff --check`, disposable browser/API smoke and
   exact GitHub feature/PR CI pass.

Full gate: `GEOAI_PYTHON=/home/geoai/dev-data/geoai-autonomy/p0-007b/clean-venv/bin/python GEOAI_TEST_REPORT_ROOT=/home/geoai/dev-data/geoai-autonomy/p5-024/final-gate bash scripts/geoai-ci-checks.sh`.
One initial attempt and at most two repairs; one writable worktree,
one compute worker, $0 external executor. Stop on time/repair budget,
unexpected edits, lost isolation, missing domain decision or production
action; record HEAD, diff, checks and exact blocker.
