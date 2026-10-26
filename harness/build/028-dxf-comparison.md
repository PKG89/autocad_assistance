# GEOAI-028 — bounded DXF inventory and reference comparison

Status: ACCEPTED; exact feature/PR CI passed. GEOAI-027 accepted
base `f618613a5d832756671a47db3351c9e2f3f7397e`.
P6 manifest deadline 2026-10-25T06:33:23Z; task ceiling 90 minutes,
one initial attempt plus at most two repairs, one writable worktree,
one compute worker and $0 external executor.

## Dependency and scope

Use only owner-scoped, verified bytes from a GEOAI-027 archive entry
and a successful stored job of the same source revision. Read both
without changing either. Expose an authenticated, read-only comparison
endpoint returning per-type/layer inventory, unsupported model-space
entity counts, exact discrepancy counts and bounded examples. No
automatic dataset/training export. Synthetic DXF fixtures only.

Supported model-space records: POINT, LINE, straight LWPOLYLINE,
simple POLYLINE, INSERT, TEXT, MTEXT and 3DFACE, including their
layer, local coordinates and relevant name/text/rotation/scale.
Bulges, arcs, curves, xrefs, nested block geometry and all other
entities are counted explicitly as unsupported; do not silently
approximate them. For supported entities, compare exact stored numeric
values. Report wrong block name/rotation, wrong layer or label,
line shape and missing/extra elements. Exact equality is a diagnostic
definition here; no geodetic acceptance tolerance or QA pass/fail
threshold is invented.

Limit each DXF to 25 MiB, 100,000 model-space entities, 500,000
vertices, bounded text and no more than 100 examples per metric.
Reject invalid, nonfinite or over-limit data predictably. If either
file has unsupported entities, `complete=false` and the metrics cover
only the supported subset. Never claim complete equivalence.

Allowed files: a comparison service, API router/wiring, synthetic
tests, this spec and shared memory. Do not change generator behavior,
survey measurements, existing archive records, production settings,
workflow deployment, or real data.

## Acceptance and actual checks

1. Byte-identical synthetic DXFs yield zero supported discrepancies;
   adding/deleting a supported entity changes missing/extra counts.
2. Deliberately wrong block name/rotation, line geometry/layer and
   label text are each detected separately. Unsupported entities are
   counted by type and mark comparison incomplete.
3. Foreign owner, unrelated revision, invalid DXF and size/complexity
   bounds fail safely; source/job/reference bytes remain unchanged.
4. Focused `python -m unittest -v tests.test_dxf_comparison`, the
   full `scripts/geoai-ci-checks.sh` with the clean venv and outside
   report root, `git diff --check`, synthetic verified localhost HTTPS
   API smoke, then exact feature and PR CI pass.

Stop on exhausted budget, missing accepted 027 dependency, unexpected
edits, lost isolation, real data rights question or production action.
Record exact HEAD, diff, checks and blocker in shared memory.

## Local verification (2026-10-25)

The read-only owner-scoped endpoint compares an archived reference with
a successful job result from the same immutable revision. Exact
inventory covers the supported model-space subset, reports
unsupported types including unexpanded block contents, and bounds
examples. Five synthetic comparison tests passed deliberate wrong
block/rotation/line/layer/label, missing/extra point, invalid/limit,
foreign owner, unrelated revision and tampered result checks. The
final gate passed 149 focused, 10 isolated regression, six isolated
API, `pip check`, zero blocked operations and `git diff --check`.
Verified localhost HTTPS showed the exact three introduced errors and
rejected an unauthenticated read. No real data or production action.
Exact HEAD `1ea061c1afb4b75b0aba06ae67d402b0a3e815a6` passed
feature CI 40157505101 and draft PR CI 40157509671. P6 accepted.
