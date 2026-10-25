# GEOAI-013 — bounded uploads and safe file access

Status: LOCAL ACCEPTED; remote CI pending. Base: accepted GEOAI-012 feature commit
`608a8e3ff84178470dbad6663fcca27fef5508b9`.
Dependency 012 passed local and remote push/PR checks.

## Bounded scope and fixed resource profile

Keep the existing 10 MiB HTTP file-size limit. On the 2-vCPU, approximately
4-GiB VM, additionally cap TXT/CSV surveys at 100,000 usable point rows,
150,000 physical lines, 64 columns and 4,096 characters per field. Cap KML
at 100,000 coordinate tuples and 200,000 XML elements. These limits bound
parser materialization and job input independently of later compute quotas;
they may be lowered by configuration, never raised by a test. Reject binary
or disguised content, malformed KML and unsupported archives. KML with NUL
bytes (including UTF-16 XML) is outside this safe upload profile. Do not
extract archives or infer geodetic validity from an extension.

Candidate files: `services/uploads.py`, `api/uploads.py`,
`api/app.py` only if passing limits is required, focused API/service tests,
and task memory. Preserve existing upload IDs and response fields.
User-supplied filename remains metadata only. Do not change geometry,
project storage, authentication, production data, `.env`, deployment or
system packages.

## Acceptance and checks

1. Upload directory and stored basename are server generated. Traversal,
   Unicode control/bidi names, empty names, unsupported extensions,
   symlinked upload directories/files and path swaps cannot read or
   overwrite outside the upload root. Repeated requests get distinct IDs.
2. Oversized, binary/spoofed, malformed or over-limit input returns a
   stable 413/422 error and leaves no partial upload. KML is parsed as
   bounded XML without expanding DTD/entities. Source coordinates are
   never changed or sent externally.
3. Preview, mapping and DXF read only the exact file bound to a UUID
   through one bounded, no-follow open path; no check-then-read race.
4. Test normal TXT/CSV/KML, limits at and above boundary, traversal,
   symlinks, name edge cases, invalid content, repeated upload and
   cleanup. Run all current focused tests plus isolated regression/API,
   negative guard checks, pip and diff checks.

Budget: 90 minutes for 013, one attempt plus at most two repair cycles.
P1 ceiling four hours, one writable tree/compute worker and zero external
executor spend per manifest. Stop on untrusted content bypass, lost test
isolation, unexpected edits or an unavailable subject-specific rule.
