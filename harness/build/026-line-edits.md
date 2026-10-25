# GEOAI-026 — controlled line edits over immutable measurements

Status: READY after exact GEOAI-025 feature and PR CI passed. Base:
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
