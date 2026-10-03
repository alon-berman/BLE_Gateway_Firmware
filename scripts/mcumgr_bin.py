"""Locate the mcumgr binary the same way everywhere.

The wizard is usually started from a desktop launcher or an IDE, where PATH
does not include ~/go/bin, which is where `go install` puts mcumgr.
"""
import os
import shutil

CANDIDATES = ("~/go/bin/mcumgr", "/usr/local/bin/mcumgr", "/opt/homebrew/bin/mcumgr")


class McumgrNotFound(RuntimeError):
    pass


def mcumgr_path() -> str:
    """Absolute path of mcumgr, or McumgrNotFound with an actionable message."""
    found = shutil.which("mcumgr")
    if found:
        return found
    for candidate in CANDIDATES:
        path = os.path.expanduser(candidate)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    raise McumgrNotFound(
        "mcumgr not found on PATH or in " + ", ".join(CANDIDATES)
        + ". Install it with: go install github.com/apache/mynewt-mcumgr-cli/mcumgr@latest"
    )
