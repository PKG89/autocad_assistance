# GEO AI closed-pilot operational overlay, version 0.1.0

This overlay is separate from immutable product archive
`79528bb9f6070e458724886a915f9d035cdfd110.tar`. It imports the
product only from the checksum-verified extracted archive. The approved
rollback code archive `1ea061c1afb4b75b0aba06ae67d402b0a3e815a6.tar`
is an explicit alternative. Do not run the repository HEAD as product code.

## Installation sequence after separate authorization

1. Verify the combined manifest and both tar SHA-256 values. Create a
   dedicated Debian VM, service users and `/srv/geoai-pilot` with
   `archives/`, `releases/`, `states/`, `backups/`, `logs/` and
   `pilot_ops/` owned by the appropriate users. Never point these at bot data.
2. Extract the exact product tar to `releases/<full SHA>/` and the
   separately versioned overlay tar at the installation root, yielding
   `pilot_ops/`. Use Python 3.13.5
   with the product lock. No product or overlay package installation
   through `pip install -e`; use `PYTHONPATH=/srv/geoai-pilot/pilot_ops`.
   Install the lock's dependencies in an isolated venv from an approved
   wheel source, then run `pip check`. The lock pins versions but not
   wheel hashes.
3. Copy and fill a fresh config from
   `pilot_ops/config.example.json`; its exact JSON keys and
   derived paths are enforced. Put it at `/etc/geoai-pilot/config.json`
   with owner-only write permission. `mode=pilot` requires installation
   root exactly `/srv/geoai-pilot`, a private DNS HTTPS origin on 443,
   and ASGI bind exactly `127.0.0.1`. `mode=synthetic` is only for
   isolated loopback tests.
4. `python -m geoai_pilot_ops init-state --config ...` creates a
   **new** marked state root. It refuses an existing root. Then
   `python -m geoai_pilot_ops check --config ...` verifies both tar
   and extracted code, the marker and private state permissions.
5. Provision one owner through the approved secret channel. The
   overlay contains no owner credentials. Review the two systemd
   templates and Caddyfile, replace placeholders, provide a private
   CA certificate covering the chosen VPN hostname and install CA
   trust on allowed clients. Caddy binds only the approved VPN IP;
   the app binds only loopback. Do not enable units until the pilot
   launch is approved. Verify listeners after launch.

The direct TLS flags on `serve` are accepted only for synthetic
loopback tests. In pilot mode Caddy terminates TLS and forwards to
Uvicorn with proxy headers trusted only from `127.0.0.1`. The app
checks the exact HTTPS origin for login and state-changing requests.

## Stop, backup and restore

Stop the TLS proxy and app; wait for the one child worker to exit.
`backup --name <new-name>` holds an exclusive state lock, refuses an
active service, checks SQLite versions/integrity and writes a SHA
manifest. `restore --backup-name <name> --new-state-name <new-name>`
verifies the backup **before** creating a new state root, then copies
and rechecks it. Point a reviewed config to that new root and run
`check` before starting. Never overwrite the current state or sole
backup. Switching code to the P6 rollback tar uses the same state
schema v8 but removes the 029 catalog feature; test on a copy first.

No command in this package changes Proxmox, VPN, systemd or existing
services automatically. TLS templates are unrendered until the
hostname, VPN IP and internal-CA cert are approved.
