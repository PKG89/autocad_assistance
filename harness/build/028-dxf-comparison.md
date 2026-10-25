# GEOAI-028 — bounded DXF inventory and reference comparison

Status: READY; exact GEOAI-027 feature and PR CI passed. Accepted
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
