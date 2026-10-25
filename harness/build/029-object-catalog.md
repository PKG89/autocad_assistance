# GEOAI-029 — versioned catalog of existing object-code rules

Status: LOCAL GATE PASSED; exact feature/PR CI pending from accepted GEOAI-028 at
`1ea061c1afb4b75b0aba06ae67d402b0a3e815a6`.
P7 manifest deadline 2026-10-25T07:20:40Z; task ceiling 90 minutes,
one initial attempt plus at most two repairs, one writable worktree,
one compute worker and $0 external executor.

## Source and scope

The committed `templates/SinoKOD.txt` contains 75 point-code rows.
`config.py` contains `sm_controller_config.block_mapping`, special
support/tower settings, `polyline_prefixes` and a small explicit
`polyline_layer_mapping`. These are implementation sources, not a
complete or legally authoritative surveying standard. Avoid importing
`config.py` in catalog generation because it may read `.env`.

Create an immutable, versioned, reproducible catalog snapshot from
the existing committed source fields only. Parse the configuration
structure safely as data; preserve code case, names, descriptions,
source hashes and exact source line references. Associate a point
code with a block only where the current generator's explicit mapping
does so uniquely. Preserve unmapped entries and competing mappings as
unresolved/conflicts; do not invent a precedence or object meaning.
Record line prefixes and the three explicit layer overrides separately.
Expose read-only authenticated catalog and exact code lookup API for
future tasks. Changing source data without an explicit catalog version
bump must fail its parity test. No generator behavior, job results or
existing project versions change in this task.

Allowed files: catalog parser/snapshot, read-only API adapter/wiring,
synthetic tests, this spec and shared memory. No database migration,
production action, new domain taxonomy or external data.

## Acceptance and commands

1. Snapshot has a stable catalog version and SHA-256 provenance for
   both source files. Repeat builds are byte-identical. All SinoKOD
   rows remain represented, including unmapped/ambiguous codes.
2. Exact lookup distinguishes one block mapping, no mapping and a
   conflict. Prefixes/layer overrides are sourced exactly from config.
   Invalid or malicious config syntax is rejected without executing it.
3. Authenticated API returns bounded catalog pages and exact lookup;
   unauthenticated requests fail. No `.env`, Telegram DB or real data
   is read by catalog parser. Existing generator parity remains.
4. Focused `python -m unittest -v tests.test_object_catalog`, full
   `scripts/geoai-ci-checks.sh` with clean venv and outside report root,
   `git diff --check`, verified localhost HTTPS smoke and exact
   feature/PR CI pass.

Stop on exhausted budget, source mapping ambiguity requiring domain
judgement, unexpected edits, lost isolation or production action.
Record HEAD, diff, checks and exact blocker in shared memory.

## Local verification (2026-10-25)

Immutable `object-code-v1` snapshot includes 75 SinoKOD rows, exact
source hashes, all explicit block aliases, line prefixes/overrides and
special support/tower settings. Parser uses Python AST literal fields;
it never imports/executes `config.py` or reads `.env`. Unmapped and
ambiguous codes remain visible. Four focused catalog tests passed
source parity, deterministic bytes, lookup, conflict, safe rejection
of executable syntax and authenticated pagination. Final isolated
gate passed 153 focused, 10 regression and six API tests, `pip check`,
zero blocked operations and diff check. Verified localhost HTTPS
showed 401 without login and mapped/line/dynamic lookups after login.
No real data or production action. Exact feature/PR CI pending.
