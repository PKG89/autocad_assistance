# GEOAI-030A — private same-object point-file inventory

Read-only local inspection on 2026-10-26. The owner described these four
Azat exports as points from the same object as the previously supplied
Kirill file. This is an owner assertion about object identity, not a
verified pairing to a finished drawing. The owner explicitly confirmed that
these files do **not** correspond to the earlier completed DXF. Only
filenames, hashes and aggregate structural findings are recorded here. No
coordinate, raw row, survey file or third-party asset was copied into Git,
VM109 or VM110.

## Local files

- `Azat VOLS U-P_2025-10-11-10-2-57.txt`: 24,048 bytes; SHA-256
  `4df8d99621143b9465bac29ff236cc6347f5ce14bac239a69a2a374b5ecee9cc`;
  599 nonempty rows.
- `Azat VOLS U-P_2025-10-16-17-35-12.txt`: 100,216 bytes; SHA-256
  `5a1b66cdd29ba17c6e1c8b55dba6ca1a3e9bcb997565291404e3e6b6c087025d`;
  2,272 nonempty rows.
- `Azat VOLS U-P_2025-10-20-15-50-21.txt`: 20,050 bytes; SHA-256
  `04776032560ed88fc90fa9c31c18b85e40475bb05021958db5a842fb16a17f33`;
  448 nonempty rows.
- `Azat VOLS U-P_2025-10-22-17-30-32.txt`: 165,759 bytes; SHA-256
  `1ef98e60a6b56f10272edd8bc1bc16e3b346a557bd866288f45529bd29008bbc`;
  3,733 nonempty rows.
- Prior `Kirill VOLS U-P 20.10 vse.txt`: 27,907 bytes; SHA-256
  `8937c61583f29da94047fbbf26646324a10696b715d6454049dd623535686b60`;
  632 nonempty whitespace-delimited rows, with some split point IDs.

All four Azat files are comma-delimited UTF-8 text with six fields per row,
despite the `.txt` extension. The apparent fields are point ID, three
numeric coordinates, code and an optional final field. Field meaning,
coordinate system, units and any special `Base`/control rows require domain
confirmation. There is no separate, identified receiver, timestamp or
line-object column in these exports. Filenames are source labels, not
row-level receiver evidence.

## Overlap and ambiguity

- All 599 exact rows of the 11 October file occur in the 16 and 22 October
  exports; they form the suffix of both. All 448 exact rows of the 20 October
  file occur in the 22 October export as a contiguous block.
- All 2,270 distinct exact rows of the 16 October export occur in the 22
  October export. The 16 October file has two repeated exact rows; the 22
  October file has four. The latter has 3,729 distinct point-ID/XYZ pairs
  among 3,733 rows and two IDs associated with more than one XYZ position.
- The 22 October export shares 183 exact point-ID/XYZ/code records with the
  Kirill file, all within its first 195 rows. Ten more point IDs occur in
  both sources without the same XYZ match. These overlaps show that the
  latest Azat export contains records also present in Kirill's file; it must
  not be labelled an independent receiver-only sequence from its filename.
- The 22 October export has 212 rows with an empty code and 242 distinct
  code strings. These are inventory counts, not validated coding rules.

The files improve format, provenance and deduplication analysis for 030A.
They do not identify actual line boundaries or correct links/breaks, and do
not justify applying either offline candidate mode to real points. In
particular, the `per_receiver` alternative requires independently verified
row-level receiver identity; an aggregate export cannot supply it merely by
filename. No corresponding finished DXF has been identified for this point
set. Correct source-to-DXF pairing, permission for internal comparison,
object/string identity, action/style grammar, ordering and domain reference
criteria remain open. The 030A offline experiment stays PARTIAL, the pilot
is unchanged, and no training/evaluation readiness follows.
