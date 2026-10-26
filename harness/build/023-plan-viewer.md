# GEOAI-023 — browser plan viewer

Status: ACCEPTED. Base: accepted GEOAI-022 feature commit
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
The viewer accepts at most 8 MiB of already verified result bytes,
10,000 source plus expanded entities, 50,000 rendered vertices and
64 characters per displayed DXF text attribute. The project result
store's independent 25 MiB maximum remains unchanged. Exceeding any
viewer bound returns 413 and does not modify the source or result.

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

## Local implementation and evidence (2026-10-25)

- `dxf_plan.py` projects an integrity-checked owner result into bounded
  JSON for POINT, LINE, plain LWPOLYLINE/POLYLINE, 3DFACE, CIRCLE,
  segmented ARC, TEXT/MTEXT and nested INSERT geometry. DXF arc
  approximations are marked; bulged polylines and mesh/curve polylines
  are explicitly unsupported instead of being shown as straight lines.
  Viewer caps are 8 MiB, 10,000 expanded entities, 50,000 vertices,
  four block levels and 64 displayed text characters. API has safe
  401/404/413/422 responses, no-store output and existing owner guard.
- The synthetic HTTPS result from the fixed 021 CSV returned 25
  model-space objects, 46 expanded objects and eight layers. Plan
  result SHA-256 matched the DXF download:
  `6f356b6fa75fc44c317b8dae4dccd35fdef33261a7c7ee80cb5491504d4b56cc`.
  Browser used a disposable HTTP-only static harness with that
  authenticated API's JSON. The self-signed HTTPS API was checked
  separately with certificate verification; no browser certificate
  warning was bypassed. In the browser, block selection exposed its
  layer, scale, rotation and XYZ; fit/zoom/pan and layer toggling worked.
  Shifting the fixture by +1,000,000 X and +2,000,000 Y preserved the
  visible geometry and exposed the shifted exact coordinates. Console
  errors: zero. All disposable servers/tunnels stopped.
- Focused parser and owner/job API tests passed, including no source
  mutation, unsupported bulge, over-limit/corrupt DXF and foreign owner.
  The final local gate `p5-023/final-gate-repaired.log` passed 127
  focused, 10 isolated regression and six isolated API tests, zero
  blocked operations, `pip check` and `git diff --check`. `node --check`
  passed both browser scripts on Windows Node 24. Exact GitHub feature
  and PR CI remain pending. No schema, Telegram, geodetic algorithm
  or production state change.

## Exact remote acceptance

Feature HEAD `24dad9cddfb90c9d4f5cad9d1dfed3415bfea534` passed
GitHub `GEO AI checks` push run 40153380771 and draft PR #6 run
40153383129. Complete branch bundle SHA-256
`a923b30576764257606996ef39a4907c183e90f75fad4849632d88df9649a7a4`
matched on VM and Windows. The feature worktree was clean at that
HEAD before this acceptance update. GEOAI-023 is accepted; next is
024 from this verified base.
