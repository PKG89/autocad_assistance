# GEO AI — единый перечень материалов для заблокированных этапов

Status: REQUESTED, not supplied or approved as of 2026-10-25. Do not
replace missing domain decisions with inferred values. Keep real source
files in an owner-approved private location outside Git and disposable
synthetic staging. Record provenance and scope of use per object.

| Material from owner/domain reviewer | Purpose and required association | Unblocks |
| --- | --- | --- |
| Field points for each surveyed object in any recoverable source/export format, with point IDs, XYZ, codes, units, CRS/scale where known, plus the corresponding final approved DXF and object/revision identity | Reconstruct the same input and compare exact object geometry without mixing revisions or train/validation families. A lone finished DXF does not establish the original point sequence. | Full GEOAI-030 validation; class-by-class GEOAI-031; dataset audit 036 prerequisites; later 037–038 |
| Provenance and permission for **each** proposed object pair: rights holder, who supplied and reviewed it, permitted uses separately for internal comparison, training, evaluation and publication if applicable | Determine which objects may enter comparison or a later dataset. Existing archive use flags are owner assertions, not independently verified rights. | Real GEOAI-030 held-out checks; verified 036 readiness; 037–038 only if training/evaluation is explicitly permitted |
| Class definitions, correct labelled connections/breaks for each selected object, independent whole-object split, baseline measures and maximum acceptable per-class regression agreed by a topographer | Evaluate direction, order, crossings and breaks against the current algorithm; prevent a gain in one class from hiding a loss in another. No numeric tolerance is inferred from synthetic cases. | Full GEOAI-030; then small GEOAI-031 class tasks; 036 metrics/split review; 037–038 evaluation |
| P8 analytical surfaces and real reference sites with measured points, structural breaklines, boundaries and exclusion masks; expected checks and named geodetic reviewer/sign-off procedure | Verify that breaklines actually change TIN, masks clip it, measured and derived points stay distinct, and contour elevation/smoothing are acceptable. Library capability, license and VM resource fit must also be checked. | GEOAI-032; after 032, GEOAI-033 |
| P9 approved sample forms/templates (coordinate/height catalogues, schedules and appendices), required fields, units, rounding rules, version and a reviewer | Produce documents whose figures match one project version and whose pages can be visually checked. Unknown values stay unknown. | GEOAI-034; then GEOAI-035 |

The supplied 202.6 MB completed DXF is retained privately as a read-only
reference for later review. Its original field TXT/CSV is unavailable;
direct exact XY matching did not recover a point-to-line mapping. It
does not by itself clear any dataset or training gate. GEOAI-036 is
accepted as an audit *that reports not ready*.

For GEOAI-040 only, the owner must separately approve a concrete target,
DNS/TLS, secrets handling, production backup destination, maintenance
window, migration decision, monitoring contacts and rollback authority.
None is presumed by GEOAI-039 acceptance.
