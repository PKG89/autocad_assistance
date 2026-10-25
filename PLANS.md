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
- GEOAI-010 (#4) is ACCEPTED at local commit
  `5c5915fbb3e6df07a1a7b2d1d3a73d8a02750564`; its Issue is closed.
  Explicit mapping and typed API passed protected tests and Codex review.
- GEOAI-011 (#5) is ACCEPTED at local commit
  `b78b1f591244f04c6652c9fe857b93d282f134ec`; its Issue is closed.
  Both Telegram and API use the isolated shared DXF service. The protected
  package 008–011 is complete; the dispatcher and broker are stopped.
- P0 is complete. GEOAI-007A evidence and an independent Windows copy of the
  accepted branch bundle plus inherited CI edit are verified. GEOAI-007B is
  accepted at `49dea8a` after successful push and PR checks in GitHub.
  The old 008–011 Symphony queue remains stopped.
- The inherited CI edit is preserved separately. It uses direct unittest
  discovery, and the isolation bootstraps contain VM-specific output paths.
  Local baseline success is not CI/deployment readiness.

## P0 — local record and CI preparation

- GEOAI-007A: COMPLETE on 2026-10-25. Accepted product commits 008–011
  are ancestors of final local code/documentation HEAD
  `bbf6f660985db3e519b06deec52e7ef39b9678a3`. The final bundle passed
  verification. The difference from product commit `b78b1f5` is a
  documentation commit. The inherited uncommitted CI workflow has matching
  SHA-256 copies on VM109 and Windows; the final P0 branch bundle is also
  verified on Windows.
- GEOAI-007B: ACCEPTED at `49dea8abd8d1a6705a842bdcf80e7672a9135c91`.
  Separate feature/PR checks, portable bootstrap roots, clean-venv install
  and positive/negative local gates passed. GitHub push run 40145553092
  and draft PR #6 run 40145565460 succeeded at that SHA. The production
  workflow was unchanged. GitHub reports `main` unprotected and no active
  branch rules; no rules were changed.
  Scope and checks are in `harness/build/007b-ci-github.md`.
- The owner now authorizes the scoped CI edit, exact origin, feature push and
  draft PR for 007B; branch-rule changes and deployment remain excluded.
  The prior 30-minute/task and two-hour/package controller settings applied
  only to 008–011. The current P0 run manifest is under
  `/home/geoai/dev-data/geoai-autonomy/p0-run-manifest.json`.
- Next: freeze GEOAI-012 from the accepted 011/007A baseline, then execute
  P1 by dependencies. No production deployment is authorized.

P1 run manifest: `/home/geoai/dev-data/geoai-autonomy/p1-run-manifest.json`.
GEOAI-012 was accepted after local and remote checks.
GEOAI-013 is accepted at `66b8dcc` after local and GitHub feature/PR checks.
Its fixed bounds and safe-read contract are in `harness/build/013-upload-guard.md`.
GEOAI-014 is accepted at `0ad1e0a` after local and GitHub feature/PR
checks. P1 is complete. GEOAI-015 is accepted after one CI repair at
`a0e82bc`; both GitHub feature/PR runs passed. GEOAI-016 passed its local
gate under `harness/build/016-owner-auth.md`; GitHub CI is pending.

## Proposed product roadmap — not queued

Numbers 012–040 were checked against this plan on 2026-10-25: none were
assigned here. Each row below is PROPOSED and needs a frozen task specification,
base HEAD, file scope, tests, budget and package authorization before dispatch.
The first product milestone is a private web cabinet for upload, preview,
mapping and DXF through the shared engine.

| Package | ID | Outcome | Depends on | Status |
| --- | --- | --- | --- | --- |
| P1 | 012 | Survey model, coordinates and provenance | 007A, 008–011 | ACCEPTED at 608a8e3 |
| P1 | 013 | Safe uploads and file paths | 012 | ACCEPTED at 66b8dcc |
| P1 | 014 | Bounded calculation jobs | 013 | ACCEPTED at 0ad1e0a |
| P2 | 015 | Versioned project storage | 012–014 | ACCEPTED at a0e82bc |
| P2 | 016 | Owner authentication | 015 | LOCAL ACCEPTED; remote CI pending |
| P2 | 017 | Project, job and file ownership checks | 015–016 | PROPOSED |
| P3 | 018 | Quotas, retention and cleanup | 014–017 | PROPOSED |
| P3 | 019 | Web import, preview and mapping | 009–010, 012–013, 016–017 | PROPOSED |
| P3 | 020 | Web jobs, results and download | 014–019 | PROPOSED |
| P4 | 021 | End-to-end web MVP acceptance | 018–020, remote 007B CI | PROPOSED |
| P4 | 022 | Reproducible staging, recovery and rollback | 021 | PROPOSED |
| P5 | 023 | Browser plan viewer | 015, 020–021 | PROPOSED |
| P5 | 024 | A/B line-connection candidates | 012, 023 | PROPOSED |
| P5 | 025 | Confirmed decisions and review history | 017, 023–024 | PROPOSED |
| P6 | 026 | Reversible derived-geometry edits | 025 | PROPOSED |
| P6 | 027 | Reference-object archive | 015, 017, 025 | PROPOSED |
| P6 | 028 | DXF comparison and quality measures | 027 | PROPOSED |
| P7 | 029 | Versioned object-code rules | 012, 028 | PROPOSED |
| P7 | 030 | Measured line-tracing improvement | 024–025, 028–029 | PROPOSED |
| P7 | 031 | Contours and composite situation objects | 028–030 | PROPOSED |
| P8 | 032 | TIN with effective breaklines and masks | 012, 015, 028 | PROPOSED |
| P8 | 033 | Terrain contours and elevation checks | 032 | PROPOSED |
| P9 | 034 | Report data model and templates | 012, 015 | PROPOSED |
| P9 | 035 | Versioned deliverable package | 034; 033 if terrain included | PROPOSED |
| P10 | 036 | Verified dataset readiness | 025, 027–028 | PROPOSED |
| P10 | 037 | Small offline recommendation model | 036 | PROPOSED |
| P10 | 038 | Reviewable model suggestions | 025, 037 | PROPOSED |
| P11 | 039 | Acceptance of a chosen release | 018, 021–022, chosen features | PROPOSED |
| P11 | 040 | Authorized publication and operations | 039, release authorization | PROPOSED |

For a first limited site release, P1–P4 plus P11 are the main path. P5–P10
can follow; the document package can move earlier if it does not depend on
terrain. Stage 031 must be split by object class. ML needs a verified,
object-separated dataset and an independent comparison with the old algorithm.
No automated publication is authorized by this roadmap.

Proposed future execution bounds: one implementation agent and one compute
worker, at most three prepared tasks per package, one initial attempt plus
at most two repairs, up to 90 minutes per task and four hours per package.
Set an executor spending limit before any run. These are proposals, not
current Symphony settings. Stop on exhausted limits, unexpected changes,
lost test isolation, missing data, unaccepted dependencies or work outside
the package scope; record HEAD, diff, checks and reason.

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

## Architectural notes for later packages

Project storage, authentication and ownership precede the private web
cabinet. PostGIS is not required merely to store a project list. Preserve
measured coordinates separately from derived geometry. Introduce ML only
after a verified dataset of topographer decisions exists.
