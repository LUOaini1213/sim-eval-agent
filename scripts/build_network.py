"""Regenerate network/merge.net.xml. With --check, fail if the committed file differs."""
import argparse
import sys
import tempfile
from pathlib import Path

import _path  # noqa: F401
from simeval.network import build_network, sha256
from simeval.sumo_env import sumo_version

ROOT = _path.ROOT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="compare a fresh build with the committed net file")
    a = ap.parse_args()
    if not a.check:
        net = build_network(ROOT / "network")
        print(f"wrote {net.relative_to(ROOT)} sha256={sha256(net)} (SUMO {sumo_version()})")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        fresh = build_network(Path(tmp))
        committed = ROOT / "network" / "merge.net.xml"
        same = fresh.read_bytes() == committed.read_bytes()
        print(f"fresh {sha256(fresh)} committed {sha256(committed)} SUMO {sumo_version()} -> {'OK' if same else 'DIFFERENT'}")
        return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
