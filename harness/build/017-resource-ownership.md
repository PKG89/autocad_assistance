# GEOAI-017 — project, job and file ownership checks

Status: READY. Base: accepted GEOAI-016 feature commit
`04522becb613dc06d4b19e4b579318315cac6775`. Dependencies 015–016
passed local and GitHub push/PR checks.

## Scope and access contract

Add an additive version-2 migration to the separate project SQLite store.
Record the authenticated owner UUID on new projects and uploaded source
files. Existing version-1 projects have no owner and are denied through
the protected API; this task does not guess or assign their owner. Keep
server-generated upload/project/revision/job identifiers and accepted
source/result digests. An owner association is immutable once accepted.

When auth is configured, require an explicit project root and guard all
`/api/v1/uploads`, `/api/v1/projects` and `/api/v1/jobs` requests before
body parsing. Derive the actor only from the verified HTTPS session
cookie, not from a path, header or request body. Unsafe methods require
the exact trusted Origin and the session CSRF token. The current legacy
unconfigured app mode remains for isolated regression; it is not a
private deployment configuration.

At every upload preview, mapping and DXF request, verify the actor owns
that upload ID and that stored bytes still match its accepted SHA-256.
On successful upload, persist the owner; if that persistence fails,
remove the newly stored file through a no-follow path. Add authenticated
source and DXF-result download routes that check project/revision/job
ownership before returning bytes. Return the same 404 shape for unknown
and foreign IDs. Service methods for future project/job creation and
result publication must enforce ownership; no route may use an unsafe
unscoped read. Preserve the 10 MiB source and 25 MiB result bounds.

No real data ownership claim, user account creation, UI, deployment,
Telegram statistics migration or system packages. Candidate files:
`services/project_store.py`, `services/uploads.py`, `api/app.py`,
`api/uploads.py`, new owner middleware and download routes, focused tests
and task memory. Existing geometry and Telegram survey behavior stay.

The per-request and per-object checks follow OWASP primary guidance:
https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
and https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html.

## Acceptance and checks

1. Protected mode rejects missing/expired sessions before upload body
   parsing. CSRF/Origin failures do not create files or jobs. Authenticated
   uploads are bound to one owner and cannot be claimed again.
2. Owner A can preview/map/render/download only A's resources. Replacing
   IDs with B's upload, project, revision or job ID yields the same 404
   as an unknown ID, including source and DXF downloads. Unowned legacy
   projects remain inaccessible.
3. Tampered stored bytes, forged owner fields, symlink/path swaps and
   failed owner registration cannot leak data or leave an accepted
   orphan. Restart preserves owner checks and version-1 migration.
4. Run focused tests, current isolated regression/API suites, negative
   IDOR/download/CSRF checks, `pip check` and `git diff --check`.

Budget: 90 minutes for 017, one attempt plus at most two repair cycles.
P2 deadline 2026-10-25T04:33:23Z, one writable worktree/compute worker,
zero external executor spend. Stop on a missing owner decision,
unexpected edits, lost isolation, access bypass, exhausted limits or
an unauthorized production operation; record exact blocker and Git state.
