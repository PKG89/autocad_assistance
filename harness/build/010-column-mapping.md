# GEOAI-010 — column mapping

## Goal

Define and validate mapping of survey columns to Point, X, Y, Z, Code, Comments.

## Scope

Create a framework-independent mapping contract and a typed API operation that
preserves source values and produces explicit validation errors.

## Non-goals

No DXF generation, UI editor, database migration, or automatic AI mapping.

## Inspect

GEOAI-008/009 services, Telegram mapping handlers, state constants, and tests.

## Expected changes

A mapping service/schema, thin Telegram/API adapters as needed, and focused tests.

## Acceptance criteria

- Required fields are validated; optional fields remain optional.
- X/Y order is explicit and never silently swapped.
- Numeric validation rejects NaN/infinity before downstream generation.
- Telegram regression behavior remains compatible.

## Tests and verification

Both supported X/Y mappings, missing/duplicate columns, invalid numeric values,
baseline tests, and `git diff --check`.

## Approval gates

Approval required for changed coordinate semantics, dependencies, persistence,
workflow/production, commit, push, or migrations.
