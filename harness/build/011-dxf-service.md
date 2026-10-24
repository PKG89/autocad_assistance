# GEOAI-011 — DXF generation service

## Goal

Wrap existing DXF generation in one isolated service shared by Telegram and web.

## Scope

Accept validated mapped survey data and explicit options, call existing DXF/TIN
algorithms, and write output only to an isolated job directory.

## Non-goals

No algorithm rewrite, background queue, PostGIS, production deployment, or UI.

## Inspect

`dxf_generator/`, templates, Telegram generation flow, GEOAI-010 mapping, and
geometry regression tests.

## Expected changes

A DXF service boundary, minimal adapter changes, and focused output tests.

## Acceptance criteria

- Web and Telegram call the same core operation.
- Template/layer/coordinate behavior remains byte- or geometry-compatible where
  the existing baseline defines it.
- Invalid coordinates fail before output; partial files are removed.
- CPU-heavy work does not run directly in an async event loop.

## Tests and verification

Known survey smoke test, invalid coordinates, TIN/KML regressions, DXF audit,
API/regression baselines, and `git diff --check`.

## Approval gates

Approval required for algorithm/coordinate changes, queues or large dependencies,
workflow/production, commit, push, or migrations.
