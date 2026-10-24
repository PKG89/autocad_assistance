# GEO AI roadmap

This file holds the phase sequence. Detailed acceptance criteria live in the
matching file under `harness/build/`.

## Current phase and execution order

- Baseline GEOAI-007C is committed at `c33340366ee4016a7e2d2576bb9c46931875db16`
  on `codex/geo-ai-start` and preserved in a verified bundle and separate
  bare Git store under `/home/geoai/dev-data/geoai-autonomy/`.
- Current work: autonomous tooling and isolated pilot. Codex CLI and Cursor
  Agent CLI are installed; Codex signed in and completed a read-only tool
  call. Two Cursor browser logins failed; the pilot controller persists
  `BLOCKED` with zero attempts. The owner is checking sign-in on Windows.
  Full pilot and service dispatch remain pending. No task is queued.
- Agreed package: pilot -> GEOAI-008 (#2) -> 009 (#3) -> 010 (#4) -> 011 (#5).
  Only issues bearing `geoai-queue` are dispatchable; the four product Issues
  currently carry `geoai-planned` only.
- GEOAI-007A/007B definitions are absent and outside this package.
- Inherited CI uses direct unittest discovery, incompatible with the required
  isolation bootstrap. Local baseline success is not CI/deployment readiness.

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
