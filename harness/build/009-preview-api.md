# GEOAI-009 — preview API

## Goal

Use the GEOAI-008 parser to return a safe preview of an uploaded survey.

## Scope

Return detected encoding and delimiter, columns, bounded initial rows, and
validation warnings through a typed FastAPI response.

## Non-goals

No column mapping persistence, DXF generation, authentication, or web UI.

## Inspect

The GEOAI-008 parser, `autocad_assistance/api/`, upload storage, and API tests.

## Expected changes

A small preview route/schema and focused API tests; reuse existing upload IDs
without exposing server paths.

## Acceptance criteria

- Preview is bounded and does not load an unbounded response.
- Only an existing allowed upload is read.
- Parsing warnings are explicit; source bytes and coordinates are unchanged.
- Errors use the established API error shape.

## Tests and verification

Success, invalid upload ID, malformed/empty survey, preview bound, isolation,
regression/API baselines, and `git diff --check`.

## Approval gates

Approval required for dependencies, auth/storage redesign, workflow/production,
commit, push, or migrations.
