"""CLI entry point; only the explicit serve command starts an HTTP listener."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .runtime import (
    Config, PilotError, backup_state, init_state, make_app, restore_state,
    state_lock, verify_release,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "init-state", "serve", "backup", "restore"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--name", help="new backup name")
    parser.add_argument("--backup-name", help="existing backup name")
    parser.add_argument("--new-state-name", help="fresh restored state name")
    parser.add_argument("--tls-cert", type=Path, help="synthetic-only direct TLS certificate")
    parser.add_argument("--tls-key", type=Path, help="synthetic-only direct TLS key")
    args = parser.parse_args(argv)
    try:
        config = Config.load(args.config)
        if args.command == "init-state":
            init_state(config)
            result = {"state": str(config.state_root), "initialized": True}
        elif args.command == "check":
            config.check_state()
            result = verify_release(config)
        elif args.command == "backup":
            if not args.name:
                parser.error("backup requires --name")
            result = backup_state(config, args.name)
        elif args.command == "restore":
            if not args.backup_name or not args.new_state_name:
                parser.error("restore requires --backup-name and --new-state-name")
            result = restore_state(config, args.backup_name, args.new_state_name)
        else:
            if config.mode == "synthetic":
                if args.tls_cert is None or args.tls_key is None:
                    parser.error("synthetic serve requires --tls-cert and --tls-key")
                if any(path.is_symlink() or not path.is_file() for path in (args.tls_cert, args.tls_key)):
                    raise PilotError("synthetic TLS files must be regular files")
            elif args.tls_cert is not None or args.tls_key is not None:
                raise PilotError("pilot TLS must terminate in the reviewed private proxy")
            import uvicorn

            with state_lock(config):
                os.chdir(config.state_root)
                app = make_app(config)
                uvicorn.run(
                    app, host=config.bind_host, port=config.bind_port,
                    workers=1, access_log=False, log_level="warning",
                    server_header=False, proxy_headers=config.mode == "pilot",
                    forwarded_allow_ips="127.0.0.1" if config.mode == "pilot" else "",
                    ssl_certfile=str(args.tls_cert) if args.tls_cert else None,
                    ssl_keyfile=str(args.tls_key) if args.tls_key else None,
                )
            return 0
    except PilotError as exc:
        parser.exit(2, f"pilot configuration refused: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
