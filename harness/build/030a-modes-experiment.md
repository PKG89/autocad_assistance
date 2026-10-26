# GEOAI-030A — bounded explicit/no-end tracing experiment

Status: **PARTIAL — offline synthetic comparison implemented and checked**,
following the owner's 2026-10-25 instruction to try both explicit end and
no-end approaches for surveys made by multiple receivers. This is not full
acceptance of 030A,
030B or the aggregate 030, and does not change DXF jobs or VM110.

Base: VM109 `codex/geoai-current` at
`dc766aa0d61fcec62cace75a3d9208150f2dcd4b`, with accepted 012,
025–026, 028 and 029A. Use one writer/worker, a 90-minute ceiling,
at most two focused repairs, and no external executor spend.

## Evidence and input boundary

`SurveyDataset` preserves point ID, exact XYZ text, raw code, source row and
source SHA-256. It has no line-object ID or receiver ID. The local DrawLine
table uses `0/1` both for end/start and style IDs, so raw code alone cannot
select an action. The owner confirmed that a survey made with multiple
receivers may not reveal line start/end in the field file. Therefore the
experiment takes a **separate, explicit, versioned annotation** keyed by
source row: object ID; optional receiver ID; and, for explicit-end mode,
confirmed action plus integer order key. These annotations are synthetic
for this task and are not assumed to exist in real files. Unknown or
ambiguous raw tokens remain visible through 029A; no action is inferred
from them.

The privately supplied 632-line TXT example confirms mixed row shapes,
including two-token point IDs and multiple trailing code tokens, but does
not identify receiver, time or line-object fields. See `030a-readiness.md`
for its hash and structural inventory. The file remains local and is not
used as a test fixture or evidence of correct connections.

## Two read-only modes

1. `explicit_end`: within each object ID, sort only by supplied integer
   order keys and require a confirmed `start`, zero or more `continue`, and
   `end`. The end point is included as the last vertex. Another `start`
   after a completed `end` begins a separate chain; no edge bridges the
   chains. Repeated start before end, orphan end/continue, unfinished chain,
   duplicate point ID or order key, missing action/order, or missing object
   ID yields `needs_review` and **no edges for that object**. This mode is
   deterministic only because the annotations are explicit; it does not
   claim to decode the field file automatically.
2. `no_end_review`: do not infer a true start/end. For each explicit object
   ID, emit two reversible alternatives: `source_order` connects successive
   source rows; `per_receiver` connects successive rows only within each
   known receiver ID and leaves receiver chains disconnected. The second
   alternative is unavailable if any receiver ID is missing. Both carry
   `needs_review` and must never become a job/DXF result automatically.
   Duplicate point IDs or missing object IDs abstain for the affected
   object. Different candidate edges expose the uncertainty rather than
   choosing a winner.

Each edge carries the source point IDs, source row indices, object ID,
profile version and SHA-256, mode/candidate label and a human-readable rule
reason. Original source records/XYZ/raw codes stay unchanged. Neither mode
uses nearest-neighbour, lexical/numeric point-ID sorting, global row order
as a claimed survey truth, or the 030B uncrossing experiment. No line
styles, symbols, surfaces or drawing layers are selected.
The result exposes the separate annotation version, its synthetic origin,
and each row's receiver/action/order fields so a reviewer can see what was
supplied rather than mistake it for parsed evidence.

## Bounded checks

Limit 200 objects, 500 points per object and 5,000 annotated points total.
Reject unknown rows, repeated annotation rows, overly long IDs, invalid
actions/keys and over-limit inputs before producing edges. Test two
independent adjacent/intersecting objects with interleaved source rows;
separate completed chains; repeated start, orphan end, unfinished chain,
duplicate ID/key; alphanumeric point IDs with an explicit key; and a
two-receiver no-end case where the alternatives differ. Assert no edges
cross object IDs, exact endpoint inclusion, explicit diagnostics, stable
ordering, source SHA/provenance and byte-for-byte unchanged raw input.

Allowed files: one offline service in existing `services/`, focused
synthetic tests, this specification and shared memory. No database schema,
API route, job, viewer, DXF generator, import mapping, model, third-party
binary, real survey, or pilot deployment changes. Run focused tests,
current isolated regression/API gate, `git diff --check` and exact feature/
PR CI. A passing experiment remains **PARTIAL** until real source fields,
rights, class criteria and a domain review can support integration.

## Verification and next gate

Focused synthetic tests passed 4/4 after two fixture-only repairs. The
isolated gate passed its focused feature checks, 10/10 prior regressions,
6/6 API checks, and `pip check`; `git diff --check` passed. The tests assert
that interleaved object rows never connect across object IDs, an explicit
end contributes its final vertex, two completed chains remain separate,
the no-end alternatives visibly differ for two receivers, and uncertain
cases abstain. Source measurements remain unchanged. This is a review-only
experiment; it is not present on VM110 and does not change the accepted DXF.

Before product integration, identify a verified object/receiver mapping for
the intended source format, settle action/style and sequence semantics with
a domain reviewer, and obtain authorized paired source/reference objects
with correct links and breaks plus class-specific acceptance criteria. The
private TXT example alone cannot satisfy those gates.
