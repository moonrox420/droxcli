"""Safety layer — lint, type-check, test, security scanning."""

from collections import namedtuple

Result = namedtuple("Result", ["ok", "message", "detail"])

# Shared subprocess options — UTF-8 safe, no cp1252 crashes on Windows
SUBPROCESS_OPTS = dict(
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
)
