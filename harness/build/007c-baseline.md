# GEOAI-007C - confirm baseline and prepare commit

## Scope and acceptance criteria

Verify the existing recovered/GEOAI-006/007 baseline in the VM109 feature
checkout. Run preflight, isolated regression/API suites, pip check and diff
check; preserve application, tests, dependencies, scripts, and workflow
contents. Record evidence, Git state, limitations and the next phase in
AGENTS.md, PLANS.md and harness/build-log.md. Prepare explicit candidate file
lists for later approval; do not stage, commit, push, or edit CI.

Expected baseline: 10 regression tests and 6 API tests, no failures/errors/
skips, and zero blocked-operation counters during tests. Python guards are
not an OS sandbox. Local baseline success does not certify CI readiness.

## Preparation repair

The generic build/ ignore rule also hid harness/build/*.md. Add a scoped
Markdown-only exception and verify phase specs are visible to Git while
ordinary build artifacts stay ignored.

## Outcome and next step

Completed 2026-10-24 (Europe/Moscow); see harness/build-log.md and evidence at
/home/geoai/dev-data/geoai-007c/20261024T204452Z/.
Next candidate is GEOAI-007A, whose exact definition must be recovered first.
