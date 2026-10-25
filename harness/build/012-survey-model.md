# GEOAI-012 — shared survey data contract

Status: ACCEPTED at `608a8e3ff84178470dbad6663fcca27fef5508b9`.
Base: accepted `codex/geoai-current` at
`6e1a75154e4ac1cac4ce439a32569a735f9f1dd0`.
Dependencies 007A and 008–011 are accepted. P0 remote CI has passed.

## Goal and bounded scope

Define one framework-independent, additive contract for parsed/mapped
TXT/CSV survey points. Reuse `survey_parser.py` and `column_mapping.py`
without changing their existing field values or the DXF geometry engine.
Carry exact raw cells, parsed row index, source line when available,
source SHA-256, Point ID, X/Y/Z, Code, Comments, explicit unit/CRS context
and scale factor. No coordinate transformation or unit conversion occurs.
Unknown CRS/units remain unknown; a local CRS label is valid without EPSG.

Candidate files: `services/survey_contract.py`, additive parser metadata,
the API and Telegram adapters that build mapped records, focused tests,
this specification and shared memory. No storage, auth, upload limits,
job queue, DXF geometry/templates, KML, production DB or deployment.

## Acceptance

1. Preserve original coordinate strings and raw source cells; numeric
   comparison uses finite Decimal values without rewriting measurements.
   Explicit X/Y column mapping controls axis order. Scale is metadata
   only, never silently applied to the measured XYZ.
2. Missing/blank/non-finite X, Y or Z fails predictably before DXF.
   Unknown height never becomes zero. Empty IDs and duplicate IDs are
   reported explicitly without dropping or renumbering points.
3. CRS and horizontal/vertical units are either explicit nonempty labels
   or `None` (unknown). No EPSG or unit is inferred from coordinates.
   Source SHA-256, row order and source row/line provenance are retained.
4. Existing API mapping/DXF and Telegram mapping behaviors remain
   compatible where inputs were valid; both adapters use the shared
   contract or demonstrate equivalent contract tests. Existing 008–011
   and regression/API suites remain green.

## Verification and stop

Focused contract tests cover swapped axes, duplicate/empty IDs, blank Z,
NaN/Inf, local CRS, unknown metadata, decimal boundary values and source
provenance. Run all current focused tests, isolated regression/API suites,
negative guard checks, `pip check`, `git diff --check` and exact diff
review. Budget: 90 minutes for 012, one initial attempt plus at most two
repair cycles; P1 wall ceiling four hours and zero external executor spend
in its manifest. Stop and record a domain question if a real geodetic unit,
CRS interpretation or tolerance is required but unavailable.

## Local result

The shared immutable dataset carries Decimal XYZ alongside unchanged text,
raw cells, source-row index, physical CSV line when available, source SHA-256,
context and structured warnings. The existing mapper still rejects missing
or nonfinite Z; Telegram keeps its accepted mapping behavior and applies
the shared contract before DXF generation. API mapping and DXF use the same
contract. Final local gate: 68 focused, 10 isolated regression and six
isolated API tests; pip and diff checks passed. No coordinate transformation,
unit inference or geodetic tolerance was introduced.
GitHub push run 40146181250 and draft PR #6 run 40146183772 both
succeeded at the exact accepted commit.
