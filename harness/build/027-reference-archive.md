# GEOAI-027 — private, immutable reference archive

Status: READY after exact GEOAI-026 feature and PR CI passed. Base:
`6285b1ada23053dc7fbfdc5d726d85d966a91fd6`.
P6 manifest deadline 2026-10-25T06:33:23Z; task ceiling 90 minutes,
one initial attempt plus at most two repairs, one writable worktree,
one compute worker and $0 external executor.

## Scope

For an owned immutable survey revision, accept a separately supplied
DXF that the operator explicitly identifies as the correct reference.
Do not treat GEO AI's own generated result as ground truth. Seal the
original field source (by immutable revision reference), reference
DXF bytes and SHA-256, metadata, current decision/edit event IDs and
model hash, provenance and explicit permission evidence in a private
archive entry. The source revision and correction histories remain
immutable and independently verifiable. Archive entries never become
training/evaluation examples automatically.

The operator must supply bounded, nonempty provenance for the field
file and reference DXF, identify the rights holder, provide the exact
permission evidence text or reference, and explicitly select permitted
uses. Store these assertions without interpreting legal sufficiency or
inventing permission. Reject missing assertions and keep all data
owner-scoped. For this task, use only newly created synthetic fixtures;
no real field file/reference or permission is available in-session.

Accept a bounded DXF upload through an authenticated, CSRF-protected
endpoint separate from the 64 KiB project JSON body path, with a
fixed 25 MiB limit. Validate syntactic DXF and reject unsafe/oversized
bytes. Write via safe, private paths and atomic metadata; expose
owner-scoped listing, metadata and verified download. Use a UUID
idempotency key for creation and reject conflicting reuse. Keep a
per-owner entry count/byte quota and no public sharing/export.

Candidate files: project store archive schema/storage and migration,
archive validation service, API and request limits, focused tests,
this spec and shared memory. No production migration/deployment,
automatic corpus generation, ML training or legal judgement.

## Acceptance

1. Synthetic field source/reference DXF, exact provenance,
   permission record, correction snapshot, author/time and SHA-256
   survive restart; verified downloads are byte-identical. Source
   measurements and existing jobs are unchanged.
2. Missing permission/provenance, foreign owner, invalid/oversized DXF,
   tampered bytes/metadata, repeated and conflicting idempotency keys
   fail safely. No archive is exported into a dataset automatically.
3. Focused tests, isolated regression/API, `pip check`, diff check,
   disposable HTTPS smoke and exact GitHub feature/PR CI pass.

Stop on exhausted budget, unexpected edits, lost isolation, missing
data rights, unclear source provenance or production action. Record
HEAD, diff, checks and exact blocker in shared memory.
