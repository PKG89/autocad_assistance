# GEOAI-025 — versioned decisions on line candidates

Status: READY after exact GEOAI-024 feature and PR CI passed. Base:
`cbcd0f39174b8b25afc6771a2f6f5643c02dcee5`. P5 manifest:
`/home/geoai/dev-data/geoai-autonomy/p5-run-manifest.json`; package deadline
2026-10-25T05:58:12Z; task ceiling 90 minutes, one initial attempt and at
most two repairs. One writable worktree, one calculation worker, $0 external.

## Scope

For each eligible line-code group of an immutable, owned TXT/CSV revision,
allow A (survey-row order), B (existing anchored nearest neighbor), skip,
or manual review. Save an append-only event with revision, source/settings
hashes, candidate algorithm version and complete A/B candidate snapshot,
selected action, owner/author and UTC time. Reject A/B where proposals
abstain. Keep original source bytes and measured XYZ immutable. Do not
infer that B's shorter length is correct.

Use an expected integer version and UUID request key for each write.
The same request key and same payload returns the original event;
reusing the key with different content conflicts. A stale expected version
conflicts without modifying history. An owner may see only decisions for
their own revision. Expose read/history and write endpoints beneath the
existing owner-scoped project/revision API, and a minimal browser control
showing saved state and fresh-version conflicts.

New project DXF jobs must snapshot accepted A/B choices by group at
admission, including decision versions/hashes in the idempotency fingerprint
and durable worker request. A chooses source order; B chooses existing order;
skip/manual or no decision retains existing B behavior and is labeled
unapproved. Retry uses the original durable worker request. The generator
must validate every override against the current group row indexes and
leave Telegram and upload DXF behavior unchanged. Existing jobs/results
must not change when a later decision is saved.

Candidate files: project store schema/migration, a small decision service,
project router, job bridge/coordinator/worker, DXF render/generator/polyline
pipeline, browser comparison panel, focused tests, this spec and shared
memory. No production migration/deployment, ML, arbitrary editing or
geodetic tolerance.

## Acceptance

1. A/B/skip/manual decisions preserve candidate/source provenance and
   author/time in ordered history. Repeated confirmation is idempotent;
   stale tabs and foreign owners cannot overwrite or read decisions.
2. A chosen zigzag is reflected in a newly generated DXF LWPOLYLINE and
   structural breakline; B equals the legacy path. Measured points remain
   unchanged. Old jobs and retries retain their admitted decision snapshot.
3. Ineligible groups cannot confirm A/B. Tampered source/snapshot or
   invalid order fails safely. Focused tests, isolated regression/API,
   `pip check`, JS syntax, `git diff --check`, disposable HTTPS/browser
   smoke, and exact feature/PR CI all pass.

Stop on exhausted time/repair budget, unexpected edits, lost isolation,
missing domain decision or production action. Record HEAD, diff, checks
and exact blocker in shared memory.
