# GEOAI-030A — readiness for explicit coded tracing

Status: PROPOSED, not READY (2026-10-25). This is a bounded readiness
record after accepted 029A, not an implementation or acceptance of 030A,
030B or aggregate 030. No pilot VM110 change.

## Existing evidence and boundary

Accepted 029A profile `drawcode-explicit-v1` preserves raw code and reports
candidate roles. In the owner-provided DrawLine description, `1` is declared
as a line-start marker and `0` as an end marker; the same conversion table
also contains style rows `0` and `1`. Its README requires point numbers on
a line to increase but gives no rule for alphanumeric IDs, repeated IDs or
multiple interleaved objects. The original FAS executable was not run or
copied. See `029a-profile-spec.md` for exact archive/member hashes and rights
limits.

The accepted `SurveyRecord` stores point ID, exact XYZ text/Decimal values,
raw code, source row/line and original cells. It does **not** store a line
object/string ID, parsed action or a separately confirmed sequence key.
Existing 024 `line_candidates.py` groups established generator prefixes and
offers reviewable A/B order; it does not establish DrawLine field-code
semantics. Existing 030B is a separate review-only synthetic inference
experiment with a known class regression. Neither is a valid fallback for
missing explicit 030A rules.

## Proposed conservative contract for owner decision

Do not connect records from raw `0`/`1` alone. An accepted 030A input would
need an explicit, provenance-labelled `objectId`, action (`start`,
`continue`, `end`) and a strict ordering key for each involved source row.
These could come from a documented coding grammar or from a separate
owner-reviewed mapping; 030A must record which source supplied each field.
If a value is missing, duplicated or ambiguous, return `needs_review` with
diagnostics and no edges for that affected object. Do not silently use row
order, lexical sorting, nearest neighbour or the 030B candidate as a
substitute. The original raw code, XYZ, source row and point ID remain
unchanged. This is a **proposal**, not a claimed local code standard.

Before READY, the owner/domain reviewer must either confirm this explicit
mapping contract or provide the actual grammar that identifies object IDs,
disambiguates action from style, and orders numeric/alphanumeric/repeated
point IDs. The chosen contract must also define whether `end` contributes a
final vertex, how an unclosed chain is reported, and whether an explicit
restart creates a new segment or an error. Without those answers, no exact
expected edge set can be frozen without inventing subject rules.

## Candidate acceptance matrix after contract freeze

Use only self-authored synthetic points and an isolated service/API stage.
Test two adjacent and intersecting independent object IDs, interleaved
source rows, nonconsecutive increasing numeric IDs, a duplicated point ID,
alphanumeric ID without a confirmed sequence, repeated start, orphan end,
unfinished chain and an unknown/ambiguous token. Assert exact edges only
for rows with confirmed object/action/order evidence; all other cases
abstain with a stable diagnostic. Every edge must carry source point IDs,
source row indices, profile version/hash and the selected rule reason. Check
that no edge crosses object IDs and no source measurement or accepted DXF
changes. Include a bounded per-object/total point limit and finite execution
budget in the implementation spec once the contract is chosen.

When authorized and specified, use the current single-writer/single-worker
workflow, a 90-minute implementation budget and at most two repairs. Run
focused tests, the current isolated regression/API gate, `git diff --check`
and exact PR CI. Synthetic acceptance would not establish real-survey
quality; paired authorized source/reference objects and a geodetic review
remain needed. 031B cannot be accepted from a 030A proposal alone.
