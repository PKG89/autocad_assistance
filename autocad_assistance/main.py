"""Launcher stub - delegate to the bot.run module.

This module attempts a normal import first and, if that fails (for example
when the file is executed directly and the package root isn't on sys.path),
adds the repository root to sys.path and retries the import.

Prefer running the application with:
    python -m autocad_assistance.main
or by configuring your IDE to set PYTHONPATH to the repository root. This
shim makes direct execution (python autocad_assistance/main.py) more forgiving.
"""

try:
    # Preferred: import the package normally
    from autocad_assistance.bot.run import main
    # Ensure basic logging is configured when running directly so handlers
    # like the diagnostic `_log_unhandled_text` are visible in the terminal.
    import logging
    logging.basicConfig(level=logging.INFO)
except ModuleNotFoundError:
    # Add the repository root (parent of this package) to sys.path and retry.
    import sys
    from pathlib import Path

    package_root = Path(__file__).resolve().parents[1]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))

    from autocad_assistance.bot.run import main


if __name__ == "__main__":
    main()
