# GEOAI-029A–031: Field-to-Finish development plan

Status: PROPOSED. Owner approved roadmap registration on 2026-10-25,
Europe/Moscow. This document is not a frozen execution specification and
does not start a queue, change product code or authorize a pilot deployment.

## Scope and invariants

Extend accepted 029 rather than replacing its catalog or renumbering stages.
Preserve accepted 027/028 and the exact installed pilot product/operations
pair. Separate explicit field-code interpretation from inferred connections.
Keep original XYZ, raw codes, row order and source IDs immutable; store
parsed attributes, derived geometry and presentation as versioned outputs.
Do not turn absent Z into zero, silently swap axes, or replace missing
ordering semantics with nearest-neighbor connections. Each edge/object must
carry its source point IDs, profile version and reason for construction.

Reuse the existing shared DXF service, owner-scoped revision/job snapshots,
023 viewer, 025 decisions and 026 edits. No parallel catalog/generator or
automatic data ingestion is introduced by this plan.

## Source inventory before implementation

The owner's local `!Рисовка Автокад` collection was inspected read-only.
Record source/archive hashes, author/provenance, versions, dependencies,
license/use evidence and intended use before adopting code, assets or data.
Keep original binaries/survey files out of Git; record paths/hashes in a
private inventory and commit only permitted specifications/test fixtures.

- `DrawLineObjectByCode05a.zip`: documented line-object IDs, start/end
  tokens, numeric point ordering, line styles/layers/colors and terrain flags.
- `DrawPointObjectByCode05.zip`: code-to-block/layer mapping and multiple
  symbols at a point. Eleven mappings reference only six included DWG symbols.
- `NXYZCode2acad07.zip`: NXYZ+Code import, block attributes and scale/label
  precision. Its 134-record example has duplicate ID 21, alphanumeric IDs
  25a/28a/103a and 24 empty codes. Resolve explicitly, never silently.
- `CodeSDR2NXYZ*` / `TestSDRdoublePk02`: documented code/coordinate join and
  duplicate-ID checks. Main executables are compiled FAS/VLX, not inspected
  source code; do not infer a complete algorithm from the file names.
- `C3D.SURVEY.zip`: 1,235 files, CRC verified; 929 extracted files match and
  306 are absent from the local extracted copy. The ZIP also has C3D11.fbk,
  ЗУ15.txt and Table_Symbols.xls. Teaching source/DWG correspondence is not
  established. C3D11.fdb_xdef has 37 entries; #TOPO.fdb_xdef has 29, with
  explicit layer/style/breakline/lot-line fields. Historical templates and
  symbols do not establish compliance with current domain requirements.

External references to inspect at pinned revisions before any reuse:

- [Land Survey Codes Import](https://gitlab.com/Oslandia/qgis/landsurveycodesimport):
  field-code interpretation and geometric constructions; QGIS dependency,
  repository lists GPL-2.0-or-later.
- [R3Survey Smart Strings](https://whitecairn.com.au/r3survey/docs/smart-strings/):
  design reference for code/string/style/annotation and surface rules;
  documentation is not a license to copy proprietary implementation.
- [autoplan-python](https://github.com/OpenGeoWorks/autoplan-python):
  DXF layout and annotations, MIT file observed. Streaming decimation and
  ordinary Delaunay/smoothing are not accepted substitutes for preserved
  measurements or constrained TIN. DWG conversion depends on ODA.
- [Auto Contour Generator](https://github.com/Yudharssiif/auto-contour-generator):
  QGIS/GDAL contour workflow; README says MIT but LICENSE contains GPL v2.
  Resolve the conflict before copying any code.
- [ArcGeek Topo](https://github.com/franzpc/arcgeek_topo):
  QGIS plan layout/tables; GPL v3 stated. Use only after dependency/license review.

The reported behavior is based on instructions and selected source review,
not successful execution of third-party packages. No CAD binaries were run.

## Subtasks and proposed acceptance

### 029A — versioned field-coding profiles

Depends on accepted 012/029 and the relevant provenance/rights inventory.
Define an explicit profile mapping to the shared model: feature type,
object/string ID, start/continue/end actions, symbol(s), depth and units,
terrain eligibility, breakline role, layer, line type and annotation rules.
Retain raw code and unknown/ambiguous tokens. Support explicit mapping of
local/Civil 3D/SinoKOD profiles without assuming their code values coincide.
Accept when profile parsing/version snapshots are deterministic, unknown
codes are visible, originals are unchanged and existing 029 behavior passes.

### 030A — deterministic tracing from explicit codes

Depends on 012, 025–026, 028 and accepted 029A. Freeze ordering semantics
including numeric/alphanumeric IDs and repeated/missing actions before coding.
Test two adjacent/intersecting independent objects, interleaved input rows,
repeated start, orphan end, unfinished chain and duplicate ID. Assert exact
expected edges and explicit diagnostics; never bridge distinct object IDs.
Every edge must be explainable from the selected profile and source records.
Synthetic contract acceptance is limited to the tested profile. Real-survey
quality acceptance still needs authorized paired examples and domain review.

### 030B — inference when coding is insufficient

Carries the existing synthetic tracing/uncrossing experiment, including its
class gain and regression; it does not reset its status or erase evidence.
Full acceptance remains blocked by reviewed real source/reference pairs,
whole-object independent splits and agreed per-class regression criteria.
No ML dependency is imposed on 030A. Acceptance of 030A cannot accept 030B
or the aggregate 030. Keep inference review-only until its own gates pass.

### 031A — point symbols and annotations

Depends on 012, 028, accepted 029A and approved asset/rule scope, not 030B.
Test multiple symbols per point, layer, scale, insertion point, rotation,
missing block/font and unknown code. Preserve XYZ; distinguish a hidden
height label from an absent measurement. Use self-authored synthetic symbols
when third-party asset rights are unresolved; identify that limited scope.

### 031B — coded line and area objects

Depends on 028, accepted 029A/030A and reviewed class rules. Subdivide by
object class if needed. Test separation, explicit closure/open chains,
line styles/layers and source provenance through shared DXF generation.
Do not close an ambiguous polygon or invent a measurement. Validate target
class examples with 028; synthetic-only evidence is not universal acceptance.

### 031C — ambiguous composite objects

Depends on the relevant accepted 030B capability, 028 and reviewed examples
for the selected class. Preserve explicit A/B/manual confirmation and object
provenance. Remains blocked by inference/domain evidence. Accepting 031A or
031B does not accept 031C or all of 031.

## Later placement and data gates

- Existing 027: register authorized teaching pairs as unverified candidates;
  record provenance and separate internal comparison/training/evaluation/
  publication rights. Existing 028: reviewed source-to-result comparison.
- 032: consume verified profile terrain/breakline flags when applicable;
  generated breaklines depend on the relevant 030A/031B outputs. Still needs
  constrained TIN, masks, analytic/reference sites and specialist acceptance.
- 033: contour classification, labels and smoothing ideas follow accepted
  032 and agreed accuracy criteria; attractive rendering is not validation.
- 034/035: layout, frames and coordinate tables remain subject to approved
  forms, units, rounding and consistent project-version outputs. No ML needed.
- 036–038: teaching examples are not automatically independent held-out data;
  current not-ready audit and rights/split/class gates remain unchanged.
- 039/040: continue the selected pilot's operational/user acceptance
  independently. New features require a separately tested release and the
  applicable deployment approval; do not install QGIS or these binaries on VM110.

## Before READY

Freeze one subtask's base HEAD, exact file scope/non-goals, profile semantics,
permitted source/assets, expected geometry, executable checks and a finite
time/spend budget. Keep one writer/compute worker and existing repair limits.
Run meaningful focused checks, current isolated regression/API checks and
feature/PR CI for implementation. This planning amendment needs documentation
consistency and diff checks only; it grants no implementation dispatch.
