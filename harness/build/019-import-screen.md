# GEOAI-019 — owner web import screen and project revisions

Status: ACCEPTED at `897cf60` after local/browser and GitHub push/PR gates. Base: accepted GEOAI-018 feature commit
`8ed56875bd1859baead50086c57c4ea52718defa`. Dependencies
009–010, 012–013 and 016–018 passed local and GitHub feature/PR checks.
P3 deadline: 2026-10-25T05:01:04Z.

## Scope and UI/API contract

Add a small same-origin browser screen, served only when authenticated
mode is configured. It signs in with the existing owner session,
restores the session after reload, lists/creates the owner's projects,
uploads TXT/CSV using the accepted endpoint, shows preview columns,
rows and warnings, lets the owner choose column mapping, and collects
explicit coordinate-system label, horizontal/vertical units and scale.
Unknown labels remain unknown; no coordinate conversion or inferred
geodetic datum is introduced. If a required choice is missing, the UI
shows a clear prompt and the API rejects invalid mapping/context.
The existing KML upload remains available but this mapped survey screen
must clearly state that KML has no column preview/mapping and cannot
enter this TXT/CSV revision workflow.

Add owner-scoped project and revision routes: list/create projects,
list revisions, import a validated upload as an immutable revision with
its mapping and explicit context/settings. Validate all mapped rows
before accepting a revision. Keep the existing shared survey parser
and ProjectStore; do not import the Telegram entry point or geometry
engine in the web adapter. The owner comes only from verified request
scope. Unknown and foreign project/upload IDs have identical 404s.
List responses have bounded pagination and revisions list newest first;
project JSON requests are capped
at 64 KiB before parsing. Create/import requests are explicitly
non-idempotent and the browser never retries them automatically.

The screen uses plain local HTML/CSS/JavaScript, no external CDN or
new frontend build tool. Render untrusted names/cells/warnings with
`textContent`, keep CSRF only in page memory, and use the secure cookie
for requests. Disable submit buttons while requests are pending and
make no automatic retries. Job submission/idempotency belongs to 020.
Only a static shell is public; resource data remain behind 017's
session/Origin/CSRF guard. No production deployment, real credentials,
real survey uploads, Telegram/statistics DB change or geometry change.

Candidate files: a narrow project router, app factory registration,
static web assets, optional scoped ProjectStore reads, focused API/UI
tests and project memory. Existing no-auth regression app retains its
current routes and behavior.

## Acceptance and checks

1. Browser can sign in and recover the session after reload, create or
   choose a project, upload a file, inspect its preview/warnings, map
   columns, enter CRS/units/scale and persist a revision without terminal.
   Warnings are readable and a pending action cannot be double-clicked.
2. Only the authenticated owner can list/create/read projects and
   revisions. A/B/unknown IDs, missing session, CSRF and invalid
   mapping/context fail without accepted revision or cross-owner data.
   Restart preserves the revision and its source/context/mapping.
3. Render untrusted survey cells/project names as text, avoid inline
   third-party scripts, and keep session/CSRF data out of URL and
   browser storage. Existing Telegram/DXF, upload and isolated gates
   continue to pass.
4. Run focused `python -m unittest tests.test_project_api -v` and
   web asset checks, then `GEOAI_PYTHON=/home/geoai/dev-data/geoai-autonomy/p0-007b/clean-venv/bin/python
   GEOAI_TEST_REPORT_ROOT=/home/geoai/dev-data/geoai-autonomy/p3-019/final-gate
   bash scripts/geoai-ci-checks.sh`, plus `pip check`, `git diff --check`
   and GitHub feature/PR CI at the exact commit.

Budget: 90 minutes for 019, initial attempt plus at most two repair
cycles, one writable worktree/compute worker and zero external spend.
Stop on missing access or geodetic decision, unaccepted 018, unexpected
edits, lost isolation, resource-limit exhaustion or unauthorized
production action; record HEAD, diff, tests and blocker.
