"""Where a results file came from: git commit of the code and the platform it ran on."""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def provenance(root: Path) -> dict:
    """``git_commit`` (full SHA or None outside a git checkout), ``git_dirty`` (tracked files
    modified; None if unknown), ``platform`` and ``python``. Written into results meta."""
    commit = _git(root, "rev-parse", "HEAD")
    status = _git(root, "status", "--porcelain", "--untracked-files=no") if commit else None
    return {
        "git_commit": commit,
        "git_dirty": None if status is None else bool(status),
        "platform": platform.platform(terse=True),
        "python": platform.python_version(),
    }
