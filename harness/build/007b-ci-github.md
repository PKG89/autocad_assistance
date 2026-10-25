# GEOAI-007B — isolated CI and GitHub handoff

Status: READY under the owner's 2026-10-25 continuous-roadmap authorization.
Scoped CI edits, tested feature push and draft PR are authorized. Production
publication and deployment remain excluded.

## Base and dependencies

- Start from accepted local `codex/geoai-current` HEAD
  `bbf6f660985db3e519b06deec52e7ef39b9678a3`, after 007A.
- The original `codex/geo-ai-start` checkout has one inherited, uncommitted
  `.github/workflows/cicd.yml` edit. Its exact copy, diff and hashes are
  preserved under `/home/geoai/dev-data/geoai-autonomy/p0-007a/`.
- GitHub `PKG89/autocad_assistance` currently reports default branch
  `main`; branch protection/rulesets have not been verified. There is no
  Git remote configured in the VM source checkout.

## Goal and proposed scope for a separately authorized run

Make feature/PR checks run all current focused tests plus isolated regression
and API bootstrap suites in a fresh runner. Decouple these checks from image
publication and production deployment. Preserve the inherited workflow edit
as evidence and review every intended change against it before editing.

Candidate files: `.github/workflows/cicd.yml`, the two isolation bootstrap
scripts under `tests/`, a narrow CI runner script if needed, CI-specific
tests, and shared project memory. Exact allowed files and base revision must
be frozen before execution. No production bot, real survey data, `.env`,
database migration, deployment, main merge or package publication is in the
local verification scope.

The existing direct `unittest discover` invokes guarded regression tests
without bootstrap. Both bootstraps also require absolute VM-specific output
roots under `/home/geoai/dev-data`; simply calling them on a GitHub runner
will fail. Introduce a portable, explicit output-root contract while keeping
the runtime write boundary, blocked-operation counters, network/dotenv guards
and regression/API assertions. Review focused tests for temporary-file and
side-effect isolation; do not silently shrink the suite.

## Acceptance

1. A clean local CI-like environment installs dependencies, passes pip check,
   all focused tests, isolated 10-test regression baseline and isolated
   six-test API baseline; later tests are additive.
2. A deliberate failing test makes the check job fail. Negative guard
   self-checks and a direct-discovery rejection remain effective.
3. PR and feature branch events run checks with minimal permissions and no
   deployment secrets. Image publication and deployment require separate
   main/release conditions and cannot run from a PR or feature check.
4. Review trigger/permission behavior for PR, push and manual events, and
   inspect current `main` rules. No rules are changed without a separate
   decision.
5. After an authorized push, a real successful remote CI run and its commit
   SHA are required for FULLY COMPLETE status. Until then the maximum status
   is LOCALLY VERIFIED.

## Checks, budgets and stop conditions

Use a new isolated worktree and compare the inherited workflow copy/diff
before editing. Check workflow syntax and event/permission logic; run
positive and intentionally failing jobs in a clean environment; run the
full current local tests, `git diff --check`, and inspect the exact diff.
Record outputs and hashes in `harness/build-log.md`.

Proposed bounds only: one implementation agent, one compute worker,
90 minutes active time, one initial attempt plus at most two repairs; P0
package ceiling four hours and zero external executor spend for the direct
Codex run, recorded in the P0 manifest. Stop on
unexpected edits, lost isolation, missing dependencies, exhausted limits,
need for main-rule change/deployment beyond the approved scope, or
failure to preserve the inherited workflow. Preserve HEAD, diff and exact
failed check when stopped. Do not restart the completed 008–011 queue.
