"""
Entry point with full crash isolation (SYSTEM 5).

Terminal NEVER crashes. All unhandled exceptions are:
  - Logged to ~/.droxcli/debug.log with full traceback + timestamp
  - Shown to user as a single clean error line
  - Exited with code 1
"""

import sys
import traceback
import datetime
from pathlib import Path

DEBUG_LOG = Path.home() / ".droxcli" / "debug.log"
DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)


def _log_crash(exc_type, exc_val, exc_tb) -> None:
    with DEBUG_LOG.open("a", encoding="utf-8") as f:
        f.write("\n" + "=" * 70 + "\n")
        f.write(f"CRASH @ {datetime.datetime.utcnow().isoformat()}Z\n")
        f.write("=" * 70 + "\n")
        traceback.print_exception(exc_type, exc_val, exc_tb, file=f)
        f.write("\n")


def main() -> None:
    try:
        from droxcli.cli import main as cli_main

        cli_main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\n\n⚠  Interrupted.")
        sys.exit(0)
    except Exception as exc:
        _log_crash(type(exc), exc, exc.__traceback__)
        print(f"\n✗  Fatal error: {exc}", file=sys.stderr)
        print(f"ℹ  Full details: {DEBUG_LOG}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
