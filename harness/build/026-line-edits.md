# GEOAI-026 — controlled line edits over immutable measurements

Status: LOCAL VERIFIED; exact feature/PR CI pending. Base:
`43fe7403af521ffc80822dcba8ead3a5b5aee23b`.
Package P6 manifest: `/home/geoai/dev-data/geoai-autonomy/p6-run-manifest.json`,
deadline 2026-10-25T06:33:23Z. One
writable worktree, one compute worker, $0 external executor, at most
three prepared tasks, 90 minutes per task, four hours per package,
one initial attempt and at most two repairs.

## Scope

Create a separate, versioned line-edit model for an owned immutable
revision. Vertex identity is the original one-based mapped survey row
index; original point ID, code and measured XYZ never change. The
initial model follows confirmed A/B decisions where present and the
legacy B order elsewhere, with explicit provenance labels. It is not
an automatic geodetic correction.

Allow explicit operations: reorder the vertices of one line; split a
line into two sequences; join two lines with an explicit resulting
line code; move one vertex between lines at an explicit position;
undo to a prior saved model. A split/join/move must conserve the set
of mapped source row indexes without duplication. The operator may
explicitly choose an existing target line code for cross-code
membership; that does not alter the source point's measured code or
XYZ. Invalid or ambiguous groups require manual review before editing.
No freehand coordinate editing or inferred geodetic tolerance.

Append every accepted operation with request UUID, expected model
version, complete bounded before/after model hashes, author and UTC
time. Same request/payload is idempotent; stale expected version is
409; foreign revision is 404. Expose current model and paged history.
Undo appends a new version referencing the target version rather than
deleting history. Bound vertices/lines/event size using 024/025 caps.

New project DXF jobs snapshot the current model version and its line
segments at admission; the generator validates membership and draws
the exact split/reordered segments and corresponding breaklines.
Existing jobs/results and Telegram or direct upload defaults stay
unchanged. The browser should allow a reviewable small edit flow with
clear original IDs and saved version, without claiming automatic
correctness.

Candidate files: project store migration, edit service/router,
job/coordinator/worker/render/generator/polyline pipeline, browser
review controls, focused tests, this spec and shared memory.

## Acceptance

1. Synthetic reordered, split, joined and moved vertex sequences
   reproduce exactly in subsequent DXF LWPOLYLINEs and breaklines;
   source bytes/XYZ remain identical. Undo reproduces a previous
   model in a new history version.
2. Repeated request, stale tab, foreign owner, duplicate/missing
   vertices, invalid target code and oversized model fail safely.
   Earlier jobs retain their admitted model and result.
3. Focused tests, isolated regression/API, `pip check`, JS syntax,
   `git diff --check`, disposable browser/API smoke and exact GitHub
   feature/PR CI pass.

Stop on budget, unexpected edits, lost isolation, missing domain
decision or production action. Record HEAD, diff, checks and exact
blocker in shared memory.

## Local implementation and evidence (2026-10-25)

- Project schema v7 adds append-only, owner-scoped line-edit events with
  expected revision model version, request UUID, operation, complete
  model snapshot and SHA-256, author and UTC time. Existing v6
  projects migrate without losing records; history is paged at 50
  events and capped at 2,000 per revision. A replay returns the same
  event; a stale or reused request returns 409.
- The initial model uses accepted A/B order if present, otherwise the
  existing B order, and marks which it used. Only groups with
  unambiguous candidate IDs enter the editable model. Explicit
  reorder, split, join with chosen target code, move between lines,
  undo and reset conserve the set of original survey row indexes.
  The source point IDs, codes and XYZ are never changed. A later A/B
  decision makes an existing edit model stale; new edits/jobs return
  409 until an explicit reset to current decisions.
- New project jobs snapshot the edit event/version/model hash plus
  exact line segments; the worker and generator validate source row
  membership and 200-group/500-line/500-vertices-per-line/5,000-row
  limits before drawing. Previous job requests/results remain fixed.
  Direct upload and Telegram DXF use the legacy path. Browser controls
  show source IDs, lines, operations, current version and history.
- Synthetic focused tests verified reorder, split, cross-code move,
  join, undo, stale/foreign owner, invalid target/missing row, history,
  idempotency, v6 migration, tampered model, unchanged source and
  frozen old jobs. A direct breakline check matched the edited split.
  Authenticated localhost HTTPS with certificate verification produced
  three expected LWPOLYLINE sequences after a split; source SHA-256
  `ac8ee8cb0781c34932a9fd0c68b08f40eaf4ebae38012761b8b09de8cb24750a`.
  The disposable browser showed reorder v3 and original point IDs,
  with zero console errors. Temporary HTTP/HTTPS servers and tab were
  closed. The full gate `p6-026/final-gate-bounded.log` passed 137
  focused, 10 isolated regression and six isolated API tests, zero
  blocked operations, `pip check` and `git diff --check`. JS syntax
  passed Windows Node 24. Exact GitHub feature/PR CI remains pending.
