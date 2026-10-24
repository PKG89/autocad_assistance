# GEO AI roadmap

This file holds the phase sequence. Detailed acceptance criteria live in the
matching file under `harness/build/`.

## Current phase and execution order

- GEOAI-007C: baseline confirmed and commit preparation complete, 2026-10-24
  (Europe/Moscow). Regression 10/10, API 6/6, pip check and diff check passed.
- Evidence: `/home/geoai/dev-data/geoai-007c/20261024T204452Z/`.
- Git: `codex/geo-ai-start`, HEAD `36f49b2`, uncommitted working changes,
  empty index, no remote. Commit/push and workflow changes still need approval.
- Next: GEOAI-007A -> GEOAI-007B -> GEOAI-008 -> 009 -> 010 -> 011.
- 007A/007B task definitions are not present in the repository; obtain their
  scope and acceptance criteria before implementation. Do not infer them
  from their identifiers or start a later phase automatically.
- Known limitation: inherited CI uses direct unittest discovery, incompatible
  with the required isolation bootstrap. No CI run is claimed.

## Foundation

Preserve the recovered working baseline, isolated regression tests, minimal
FastAPI health/upload adapters, and evidence under `/home/geoai/dev-data/`.

## GEOAI-008 — survey parser service

Extract safe TXT/CSV parsing from Telegram handlers into a framework-independent
service. Telegram continues to use the same parser.

## GEOAI-009 — preview API

Return columns, initial rows, detected delimiter and encoding, plus validation
warnings for an uploaded survey.

## GEOAI-010 — column mapping

Support explicit mapping for Point, X, Y, Z, Code, and Comments.

## GEOAI-011 — DXF generation service

Expose existing DXF generation through one isolated core service shared by web
and Telegram adapters.

## Later

Project storage, authentication, ownership, cleanup, PostGIS, line-review A/B,
web editing, terrain improvements, and document generation. Introduce ML only
after a verified dataset of topographer decisions exists.
