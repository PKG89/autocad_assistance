# GEOAI-008 — survey parser service

## Goal

Extract TXT/CSV decoding, delimiter detection, and row parsing into a plain
Python service used by Telegram without changing accepted survey semantics.

## Scope

- Preserve UTF-8-first and existing fallback behavior.
- Preserve delimiters, empty fields, header handling, and row ordering.
- Route the Telegram handler through the extracted service.

## Non-goals

No preview API, column mapping redesign, DXF changes, uploads redesign, or web UI.

## Inspect

`autocad_assistance/bot/file_handlers.py`, current parser-related tests, and
`autocad_assistance/services/`.

## Expected changes

A new survey parser service, a minimal Telegram adapter change, and focused
parser/regression tests. Exact filenames are decided after preflight.

## Acceptance criteria

- Service has no Telegram/FastAPI dependency and no network or `.env` access.
- TXT/CSV behavior and coordinates match the current baseline.
- Telegram uses the service rather than duplicated parsing logic.
- Invalid/empty input produces explicit errors without partial output.

## Tests and verification

Focused encoding/delimiter/header/empty-field tests; existing 10 regressions;
API baseline; `git diff --check`; protected-file scope review.

## Approval gates

Separate approval for new dependencies, workflow/production changes, commit,
push, migration, or any coordinate/expectation change.
