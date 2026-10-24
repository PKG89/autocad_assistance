# Reusable phase prompts

## START_PHASE

Read `AGENTS.md`, `PLANS.md`, and the requested `harness/build/` phase. Run a
read-only preflight, then state scope and acceptance criteria. If scope is
ambiguous, stop before writing.

## EXECUTE_PHASE

Execute exactly one approved phase. Preserve project boundaries, make the
smallest change, and do not begin a later phase.

## VERIFY_PHASE

Run the phase's focused checks, existing isolated regression/API baselines, and
`git diff --check`. Collect concise evidence without starting production.

## REVIEW_PHASE

Review the current diff for regression risk, security issues, architecture
drift, and violations of `AGENTS.md`. Report actionable findings only.

## HANDOFF_PHASE

Report what changed, tests and commands run, files changed, unresolved limits,
and one next phase candidate. Do not start that phase.
