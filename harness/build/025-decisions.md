# GEOAI-025 — versioned decisions on line candidates

Status: LOCAL VERIFIED; exact feature/PR CI pending. Base:
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

## Local implementation and evidence (2026-10-25)

- Project schema v6 adds append-only, owner-scoped decision events with
  per-group version, request UUID, action, candidate/source snapshot,
  owner and UTC time. Existing v5 data migrates in place. The immutable
  revision retains the source bytes; the decision records its SHA-256,
  settings SHA-256, candidate version and full group A/B candidate
  snapshot. History is paged at 50 events and latest state is explicit.
  A 2,000-event/revision quota bounds history growth.
- A/B is accepted only for eligible candidate groups. Same request UUID
  and payload returns the original event; conflicting reuse and stale
  expected versions return 409. Foreign revision access returns 404.
  Skip/manual events have no chosen order. The browser displays the
  saved action/version/author/time and offers A/B/skip/manual controls.
- Each new job stores its current decision versions and chosen row order
  in both the project request fingerprint and durable worker request.
  The generator checks row membership before drawing. Existing jobs
  retain their request/result across later decisions. Legacy Telegram
  and direct upload DXF callers use the unchanged default order.
- The final gate `p5-025/final-gate.log` passed 133 focused, 10 isolated
  regression and six isolated API tests, zero blocked operations,
  `pip check` and `git diff --check`. Browser static synthetic control
  showed A then manual version 2, author/time and zero console errors.
  A separate authenticated localhost HTTPS smoke with certificate
  verification produced LWPOLYLINE X sequences A `0,100,1,2` and B
  `0,1,2,100`; source bytes stayed byte-identical at SHA-256
  `1092bb2deb3ffb67d333746ea393699e77850926f6b7d8251873c211d56cc8d0`.
  Temporary HTTP/HTTPS servers and browser tab were closed. Exact
  GitHub feature/PR CI remains pending.
