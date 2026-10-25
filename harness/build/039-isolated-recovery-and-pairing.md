# GEOAI-039 — isolated recovery and VM110 backup pairing

Status: ACCEPTED for the installed synthetic pilot pair on 2026-10-25.
Product `15374b5c856958fdf67c5efdce68db81e05ac92f`; separate operations
package `71ab84cba999bcf2fd105b69917cdd1e8907671f`. The owner's
import/preview/mapping/calculation/DXF/reopen scenario passed with no remarks.
This status does not establish accuracy on real surveys or authorize 040.

## Isolated VM recovery

PVE1 restored `backup-fast-nfs:backup/vzdump-qemu-110-2026_10_25-18_53_35.vma.zst`
to test VM111. Before boot, VM111 had no `net0` and Start at boot was off.
It booted Debian 13 twice without a virtual NIC; only loopback existed in
the guest. The copied NetBird service was disabled and its state moved into
`/var/lib/netbird.restore-quarantine-111` on VM111 only. No guest route or
working-network connection was added.

On the booted clone, `geoai_pilot_ops check` returned the exact product
commit and 144 product files. Auth and project SQLite passed `quick_check`
at user versions 1 and 8. The restored state contained 153 files, including
seven source CSVs and 52 nonempty DXFs; sampled DXF headers contained
`SECTION`. The cloned application started locally at `127.0.0.1:18460`;
`/health` returned the expected 200 JSON. The app was stopped and VM111 was
shut down. Final `qm status 111` was `stopped`; its config had no network
adapter and no boot autostart. VM110 and its NetBird identity were not
replaced or modified by this recovery test.

## Coordinated backup contract

The guest `geoai-pilot-app-backup` records a root-only latest-attempt status
(`running`, `failed`, `success`) and verifies its manifest/file hashes and
both SQLite databases before reporting success. At most two local successful
dump directories remain. The two **VM110-only** PVE jobs use
`/usr/local/sbin/geoai-vzdump-110-hook`; other VM jobs were not edited.
The hook checks the guest dump before and after the VM backup, with an
explicit maximum age of 2700 seconds at each check. It validates the VM
archive with `zstd -tq`, records its byte size and SHA-256, and writes a
root-only `.geoai.json` sidecar on the selected NFS storage. A missing,
failed, stale, changed or unverifiable dump yields `appDumpStatus=vm-only`
and an explicit reason, never a coordinated-copy claim. The Proxmox task
itself must additionally report `OK` and the archive must still exist.
The hook never blocks retention of a valid VM-only archive.

Daily VM110 job `backup-fb780d73-bebc`: `backup-fast-nfs`, 05:30 Moscow,
keep-last 7. Weekly job `backup-6c2ab3d4-9573`: `backup-weekly-nfs`,
Monday 01:30 Moscow, keep-last 4. Guest dump timer runs 30 minutes before
each job (02:00 UTC daily, Sunday 22:00 UTC). Next scheduled launches after
this check: Monday 2026-10-26 01:30 and 05:30 Moscow respectively.

The real guest dump `scheduled-20261025-193705-12774` completed at
2026-10-25T19:37:09Z with attempt ID `dump-20261025-193705-12774`, 164
files and manifest SHA-256
`01f8f85901e1416d249d56dfdf7d523197a3d38e098175fdcf4d3a359f2490b0`.
The first actual hook run produced archive
`vzdump-qemu-110-2026_10_25-22_39_14.vma.zst` with Proxmox `OK`, but
explicit `vm-only`: vzdump omitted `qm` from its PATH. This negative run
demonstrated a visible failure without a false paired status. The hook was
fixed to call `/usr/sbin/qm` and `/usr/bin/zstd`; installed hook SHA-256 was
`73c9435bfc06e047d4a74754dc60860ed56a1b6cdc8ce3a2e3ea174b3dff4b41`.

The corrected actual run produced
`backup-fast-nfs:backup/vzdump-qemu-110-2026_10_25-22_40_59.vma.zst`.
Proxmox task finished `OK` at 2026-10-25T19:41:54Z. The sidecar records
`zstd-ok`, 1,266,486,182 bytes, archive SHA-256
`efc35e55058d20926a8da72ad46c41f964fced24d38620da17e9aa34429a6b0c`,
`appDumpStatus=paired`, and the guest attempt/manifest above. Dump age was
230 seconds at backup start and 280 seconds at backup end, below 2700.
The actual manual `vzdump` invocation used the storage's default keep-last 3
and pruned one older **VM110** archive; configured scheduled jobs retain
their explicit keep-last 7/4. An orphan sidecar must never be counted unless
its corresponding archive still exists.

Synthetic hook/checker tests covered a valid pair, a missing or failed dump,
staleness and tampering, changed identity, and a corrupt zstd archive:
3 guest-checker and 5 hook tests passed. VM110 app/TLS and backup timer were
active after the check; app/TLS boot autostart remained disabled. VM111 was
stopped. No real surveys, other-VM backup settings, PR merge or network
access change occurred.
