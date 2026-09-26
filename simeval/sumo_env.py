"""Locate SUMO binaries (SUMO_HOME, pip ``eclipse-sumo``, or PATH)."""
from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


def _sumo_home() -> str | None:
    home = os.environ.get("SUMO_HOME")
    if home:
        return home
    try:  # pip install eclipse-sumo
        import sumo  # type: ignore

        return sumo.SUMO_HOME
    except Exception:
        return None


def binary(name: str) -> str:
    home = _sumo_home()
    if home:
        for cand in (Path(home) / "bin" / name, Path(home) / "bin" / f"{name}.exe"):
            if cand.exists():
                return str(cand)
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(f"SUMO binary '{name}' not found (set SUMO_HOME or pip install eclipse-sumo)")


@lru_cache(maxsize=1)
def sumo_version() -> str:
    out = subprocess.run([binary("sumo"), "--version"], capture_output=True, text=True, check=True).stdout
    first = out.splitlines()[0]  # "Eclipse SUMO sumo Version 1.24.0"
    return first.rsplit(" ", 1)[-1].strip()


def available() -> bool:
    try:
        binary("sumo")
        binary("netconvert")
        return True
    except FileNotFoundError:
        return False
