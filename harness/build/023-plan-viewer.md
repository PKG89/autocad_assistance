# GEOAI-023 — browser plan viewer

Status: READY. Base: accepted GEOAI-022 feature commit
`211cf1812224c0d77803837f96db8ef60aaaebe1`; all P4 local and
exact GitHub feature/PR checks passed. P5 run manifest:
`/home/geoai/dev-data/geoai-autonomy/p5-run-manifest.json`, started
2026-10-25T01:58:12Z, deadline 05:58:12Z.

## Outcome and boundaries

An authenticated owner can open a completed job's plan in the web
cabinet and inspect its point, line, block and layer geometry with
zoom, pan and selected-object attributes. The source is the existing
owner-scoped, SHA-256-verified DXF result from GEOAI-020; no new drawing
algorithm or new project schema. Local survey coordinates stay in
their own coordinate system. Viewport normalization affects pixels only,
never stored or returned measured XYZ.

Add a bounded server adapter that reads the owner-scoped result and
returns a documented JSON plan: result/job identity, entities with
stable per-response IDs, DXF type/layer, local geometry and relevant
attributes, bounds, per-layer counts and explicitly reported unsupported
types. Expand supported block inserts for display while retaining insert
identity/attributes; never claim a partial unsupported block as exact.
Reject invalid/corrupt DXF, excessive byte/entity/vertex expansion,
non-finite coordinates, and unavailable/foreign jobs with safe errors.
Use existing result size policy where possible; freeze numeric bounds
in the implementation and tests before writing the parser.

In `/app`, add a plan action on a ready job. Render only vetted geometry
with DOM/SVG APIs, no untrusted HTML. Offer layer toggles, fit/zoom/pan,
selection and a readable attribute panel. Show unsupported counts and
the local coordinate context. Keep DXF download available. Existing
login/import/job/reload flows continue to work.

Candidate files: `autocad_assistance/services/dxf_plan.py`,
`autocad_assistance/api/owned_files.py` or a small plan router,
`autocad_assistance/api/app.py`, `autocad_assistance/api/web/*`,
focused tests, this spec and shared memory. Do not change measured
coordinates, Telegram handlers, database schema, geodetic algorithms,
production settings or infrastructure.

## Acceptance and checks

1. A synthetic result displays real model-space points/lines/blocks
   by layer. Fit, zoom, pan, layer toggles and selection work in the
   browser; large local-coordinate offsets do not erase relative shape.
   Attribute labels and unsupported entities are explicit.
2. An anonymous or foreign owner cannot obtain plan JSON. Corrupt,
   unsupported and over-limit DXF fail predictably; no source path or
   sensitive content appears in errors. DXF bytes and stored XYZ are
   unchanged by viewing.
3. Focused viewer/API tests and current isolated regression/API suites,
   `pip check`, `git diff --check`, JS syntax, disposable browser smoke
   and exact GitHub feature/PR CI pass.

Full gate: `GEOAI_PYTHON=/home/geoai/dev-data/geoai-autonomy/p0-007b/clean-venv/bin/python GEOAI_TEST_REPORT_ROOT=/home/geoai/dev-data/geoai-autonomy/p5-023/final-gate bash scripts/geoai-ci-checks.sh`.
Budget: one initial attempt and at most two repairs, 90 minutes for
023, one writable worktree, one compute worker, $0 external spend;
four-hour P5 ceiling. Stop on deadline, exhausted repairs, unexpected
edits, lost test isolation, required domain decision or production
action. Record HEAD, diff, checks and blocker before pausing.
