# GEOAI-039: VM110 closed-pilot execution record

Status on 2026-10-25: target preparation completed through private-access prerequisites; the application and TLS services have not been started. This document records direct target checks, superseding the earlier owner-only VM inventory in the preparation plan.

## Authorisation and exact components

The owner authorised VM110 package, service-user, directory, systemd, local firewall, NetBird-client and private-TLS setup, followed by a limited synthetic pilot after artifact, private-access and off-VM restore gates. No PR merge, public listener, production data, router, DHCP, global VPN-policy or Proxmox schedule change is authorised by this step.

- Product archive: commit `79528bb9f6070e458724886a915f9d035cdfd110`, 8,570,880 bytes, SHA-256 `cada7fb4f2919fe321cffbe74beeec499bc60e833e33f36a94f404560f91ce81`.
- Separate operational package: commit `7f5bbecbb05a9f86f9850ed7e045a49fde040b89`, 40,960 bytes, SHA-256 `71c330b1252c54f1d67f488ff0e39aae98a7b521d3fcf074fda4c15a2fb5213c`.
- Compatible P6 rollback archive: commit `1ea061c1afb4b75b0aba06ae67d402b0a3e815a6`, SHA-256 `9e3858aeec823b64ae7bfa61c69890a93acd1f0f2e29c687ee149afd34229c8f`.
- `harness/pilot/verify_artifacts.py` rebuilt both Git archives and checked all eight overlay file hashes on VM109. Independent Windows copies and delivered VM110 tar files matched the combined manifest. The product archive was not modified.

## Direct VM110 checks and preparation

- Host identity was confirmed from the VM110 console and pinned for `ssh geoai-pilot`; direct SSH login as `openclaw` passed. `sudo -n` works. VM110 reports Debian 13.7, 2 vCPU, 3.8 GiB RAM, 59 GiB root filesystem, initially 56 GiB free, no swap and no failed systemd units.
- `/etc/netplan/50-cloud-init.yaml` specifies static `192.168.1.162/24`, gateway/DNS `192.168.1.1`; the earlier description of this address as DHCP is superseded by direct guest inspection. No network configuration was changed.
- Dedicated `geoai-pilot` and `caddy` system users and separated `/srv/geoai-pilot/{archives,releases,states,backups,logs,pilot_ops}` paths were created. Exact product and P6 archives and the separate overlay were extracted, with code root-owned and state owned by `geoai-pilot`.
- Python 3.13.5 venv installed the exact 33-line lock from public PyPI; `pip check` passed and `pip freeze` SHA-256 matched the lock (`d8d2cf3756f29f64246f133f694ee61aa9711f8eb8e95c4fd2039734d381c351`). The lock pins versions, not wheel hashes.
- Official Caddy 2.11.7 archive matched SHA-256 `727b91701a392de6ebc5027509f548bf39979e5216340d0faed8fa5e69c84f8b`; binary installed at `/usr/bin/caddy`. NetBird CLI 0.81.2, nftables and Certbot 4.0.0 with its Cloudflare DNS plugin are installed. NetBird reports `NeedsLogin`; no VPN peer or public listener has been created. Certbot renewal timer remains disabled until certificate issuance.
- Exact systemd templates were installed and syntax-checked, but `geoai-pilot.service` and `geoai-pilot-tls.service` remain disabled and inactive. A private-origin pilot config for `https://geoai.exitline.site` was installed at `/etc/geoai-pilot/config.json`, and a new empty marked state was initialized. `geoai_pilot_ops check` passed: 144 release files, exact archive/lock and Python version.
- Local nftables default-deny input is enabled. It preserves LAN SSH from `192.168.1.0/24`, NetBird UDP/51820, loopback and established traffic. For the two owner-selected peers, it permits TCP 22/443 only on future `wt0` from currently observed `100.104.97.169` and `100.104.100.176`. A fresh LAN SSH connection succeeded after each rule change; temporary rollback timers were cancelled. No service listens on 443 or 18460 yet.
- A target-specific disposable synthetic check ran on VM110 with the exact tar pair and P6 rollback: HTTPS, 401 anonymous/foreign session, 403 foreign Origin, three queued/running/succeeded jobs, DXF, restart persistence, active-backup refusal, 27-file offline backup/restore, corrupted-backup refusal and P6 code compatibility all passed. It used `/home/openclaw/geoai-target-check-20261025`, separate from pilot state. This is not a real-data quality or load acceptance result.
- The synthetic 27-file backup was archived on VM110 and copied to the separate VM109 test root `/home/geoai/dev-data/geoai-autonomy/target-offvm-restore-test/`; the transfer SHA-256 matched `b9fa42206d9a9185c04598dae78abd84f9c4f3f3794ffd27d967be2cf931924d`. The overlay restored it to a new state root on VM109. The exact product check passed, both SQLite databases returned `PRAGMA quick_check=ok` with versions 1 and 8, and a restored DXF matched the VM110 result SHA-256 `75eca13e10f6c485008d753908fcac0eed6844ab3425b301bdefc5e6155320bd`. This is a temporary off-VM recovery test, not the approved retention destination.

## Remaining gates before starting the pilot

1. One-use NetBird setup key, assigned to destination group GEOAI, must be delivered to VM110 through a root-only file. Verify assigned peer FQDN/IP and that only the selected client peers can reach 22/443. No shared NetBird policy changes are made here.
2. A scoped Cloudflare DNS token must be delivered through a root-only file. Verify `geoai.exitline.site` availability, create DNS-only A record to the observed VM110 NetBird IP, obtain an ACME DNS-01 certificate, render Caddyfile and verify private HTTPS. No DNS record or certificate exists yet.
3. The owner selected Proxmox storages `backup-fast-nfs` (daily, keep 7) and `backup-weekly-nfs` (weekly, keep 4), with an application dump before VM backup. PVE authentication/storage inventory and concrete schedule authorisation are absent. A disposable synthetic backup was restored outside VM110, but the selected storage and retention policy have not been implemented. Do not treat the VM109 test copy as the long-term backup destination.
4. Run the owner-approved target thresholds in a limited technical session, record measured p95/RSS/disk/errors, then report the exact active services and stop commands. Owner performs user acceptance. No persistent monitoring is enabled.

No migration is required for the new empty pilot state. Production bot data and secrets remain untouched.
