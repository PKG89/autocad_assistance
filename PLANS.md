# GEO AI roadmap

This file holds the phase sequence. Detailed acceptance criteria live in the
matching file under `harness/build/`.

## Current phase and execution order

- Baseline GEOAI-007C is committed at `c33340366ee4016a7e2d2576bb9c46931875db16`
  on `codex/geo-ai-start` and preserved in a verified bundle and separate
  bare Git store under `/home/geoai/dev-data/geoai-autonomy/`.
- Completed: Codex and Cursor both passed real CLI calls. The disposable pilot
  is `ACCEPTED` at local commit `08bdbad32799ad48cb6f8df3eaad37d562fb7aa9`.
  GEOAI-008 (#2) is `ACCEPTED` at local commit
  `aec7fdad107cc1e4382b97f2d3218129e80dbccc`; its Issue is closed.
- GEOAI-009 (#3) is ACCEPTED at local commit
  `10cd7ff75cc44eacfd38d2df937605f82f64a688`; its Issue is closed. The
  protected broker/Symphony handoff, exact review, one repair, independent
  checks and local preservation completed.
- Current work: prepare frozen GEOAI-010 (#4) acceptance from the accepted
  009 commit, then queue exactly that Issue. GEOAI-011 (#5) follows only
  after 010 is accepted.
- Agreed remainder: GEOAI-009 (#3) -> 010 (#4) -> 011 (#5), one accepted
  predecessor at a time. Only issues bearing `geoai-queue` may dispatch;
  #4–#5 carry `geoai-planned` only; neither is queued yet.
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
