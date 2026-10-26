# GEOAI-029A — one bounded field-code profile

Status: ACCEPTED for the bounded parser contract. Frozen implementation
base: `ca87c06f7187a698ff1da6417a9e1409750e6bae` on
`codex/geoai-current`; the same tree was published at `db485c4` on
`codex/geoai-current` in draft PR #6. 012 and 029 are accepted. One writer,
one worker, 90-minute implementation budget, at most two focused repairs,
and zero third-party executable/asset import.

## Provenance and permitted use

The owner-provided local collection was inspected read-only. The archive
`DrawLineObjectByCode05a.zip` has SHA-256
`4f8d5987b293f022854c130d5bc7904fd8017685942976a844d1e31e2007ac9a`.
Its `ConversionCodeLine05.txt` has SHA-256
`d6cfc6383a770a481025e21a1cd7440f2f270739ee427d02b1659fbf1dfb815b`;
`Read me drawline05a.txt` has SHA-256
`5085341c094456b9b49b8f8baebaa14f475aadd243522111b4fc208cd7652003`.
The archive
`DrawPointObjectByCode05.zip` has SHA-256
`b864e9dbcf9b30d0c4dc6a72684bbe2ee7ac12953ee50f37eb58f72668706b56`.
Its `ConversionCodePoint05.txt` has SHA-256
`19f7eeacc5161f8dd7cda2187a6dceee30bc34cbdb0e3f02b8c7346f793ddb7e`;
`Read me drawpoint 05.txt` has SHA-256
`9279d5f558e2e2f57d8d62e37f06ff61fa386029d9d48fb49f5cebd696d183db`.
Authorship, license and transfer/reuse rights for the FAS, DWG, SHX and
survey assets remain unverified. Only the documented **token identifiers**
and their candidate roles are recorded as provenance-labelled facts. No
FAS/VLX, DWG, SHX, block definitions, line styles, survey examples or
third-party algorithms enter the product or tests.

## Exact minimal semantics

Profile ID `drawcode-explicit-v1`. It extends the accepted 029 catalog;
SinoKOD and local token namespaces are distinct and never silently equated.
The raw input is an unmodified code string, maximum 128 characters. Tokens
are nonempty runs separated by ASCII space or tab. Preserve raw input,
token order, exact case, and start/end offsets. No normalization or rewriting
of source records. Empty/whitespace-only input returns an explicit
`EMPTY_CODE` diagnostic; newline, carriage return and other controls are
invalid input. At most 32 tokens are parsed.

The point-code candidates are the eleven exact identifiers documented in
the point conversion table: `KIK`, `KM`, `OXR`, `DER_L`, `DER_X`, `DER_F`,
`FNR_O`, `FNR_D`, `PNT_D`, `PNT_V`, `RP_V`. They mean only that the local
profile listed a point-symbol candidate. There is **no approved drawable
asset** and no automatic block/layer placement in 029A. Multiple point
identifiers separated by spaces remain separate candidates at one point.

The line table explicitly declares marker `1` as start and `0` as end;
its numbered rows also list style IDs `0`–`9` and `11`. Hence standalone
`0` and `1` each have two documented candidate roles and must return
`AMBIGUOUS_TOKEN` with both candidates. `2`–`9` and `11` are line-style
candidates only, without selecting geometry, layer or line type. The table
does not establish how a point's fields disambiguate a marker from a style,
nor the semantics of repeated/missing markers, object IDs or point ordering.
Those decisions belong to 030A/031B. Token `&`, `&&`, depth values, Civil 3D
prefixes, case variants and other unlisted codes return `UNKNOWN_TOKEN` for
this profile; other local conventions are not imported implicitly.

API contract: authenticated `GET /api/v1/object-catalog/profiles/drawcode-explicit-v1`
returns the immutable profile version/hash and bounded source evidence;
authenticated `POST /api/v1/object-catalog/parse` accepts
`{"profileVersion":"drawcode-explicit-v1","rawCode":"..."}` and returns
the same exact raw string, ordered token spans/candidates and diagnostics.
The POST is read-only and still requires the existing Origin/CSRF policy.
Unknown profile version is a structured 422 error. No project revision,
upload, job, DXF, source coordinate or existing catalog snapshot is changed.

## Acceptance and limits

Check stable profile bytes/hash and source identifiers, exact multi-token
point candidates, ambiguous `0`/`1`, unknown/case/control/empty/boundary
handling, unchanged raw code and no geometry generation. API checks cover
auth, CSRF, body bound and deterministic response; existing 029 catalog
lookup must remain unchanged. Run focused profile and catalog tests, current
isolated regression/API gate, diff check and exact PR CI. Synthetic examples
test the parser contract only. Real-survey interpretation, symbol rights,
line construction and object quality remain outside 029A.

Allowed implementation files: one profile snapshot under the existing
catalog templates, a small parser in existing services, additive catalog
API wiring/body limit, focused tests, this spec and shared memory. No schema
migration, worker/generator change, pilot deployment or external data import.

## Implementation result (2026-10-25)

The self-authored `field_code_profile.py` and immutable JSON profile extend
the existing 029 catalog. Authenticated profile read and CSRF-protected parse
are additive; the parse endpoint has a 4096-byte request limit. The original
raw string, case, order and spans are returned unchanged. No source survey,
coordinate, revision, geometry or DXF is modified. A pinned profile file
SHA-256 prevents a silent change under the same version. The eleven point
identifiers are candidates only; no blocks or style assets are shipped.

Focused 029A plus 029 catalog tests passed 8/8. The current isolated
`scripts/geoai-ci-checks.sh` gate passed all focused tests, protected
regressions 10/10, API bootstrap 6/6 and `pip check`, with zero blocked
network/dotenv/write/process operations in the two bootstrap reports.
The subsequent character-control tightening passed the focused 8/8 again.
Published implementation head `6236df112d448f4502e276672d675f5fb3cc6478`
passed both GitHub `tests` checks (Actions runs 40228038941 and
40228035964), and its Git tree matched VM109. Synthetic parser results
do not validate actual field coding, symbol placement, line construction or
asset rights. The next candidate is a separate 030A or 031A specification;
neither is automatically READY.
