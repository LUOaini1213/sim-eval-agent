"""Script-generated freeway merge network.

Layout (mainline flows left to right; lane lengths as built by netconvert 1.24.0):

    main_in (2 ln, 912 m) -> merge (3 ln, 331 m, lane 0 = acceleration lane)
    -> main_mid (2 ln, 346 m) -> incident (2 ln, 200 m) -> main_out (2 ln, 700 m)

    ramp_in (1 ln, 308 m, 60 km/h) -> [ramp meter TLS at node r_meter]
    -> ramp (1 ln, 101 m) -> merge lane 0

The acceleration lane has no successor (lane drop at the end of ``merge``), so ramp
traffic must merge inside it. ``incident`` is the edge whose right lane can be closed.
``ramp_in`` is the queue storage upstream of the meter (about 40 cars).

The plain-XML inputs are written deterministically and converted with netconvert.
netconvert prepends a comment header containing the generation timestamp; we strip
that header so the committed ``.net.xml`` is byte-reproducible for a fixed SUMO version.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from .sumo_env import binary

MAIN_SPEED = 33.33  # m/s (120 km/h)
RAMP_SPEED = 16.67  # m/s (60 km/h) on the metered ramp approach
RAMP_LEN = 300.0    # ramp_in length: queue storage upstream of the meter

NODES = [
    # id, x, y, type
    ("n_start", 0.0, 0.0, "priority"),
    ("n_merge", 1000.0, 0.0, "priority"),
    ("n_accend", 1250.0, 0.0, "priority"),
    ("n_inc", 1600.0, 0.0, "priority"),
    ("n_inc_end", 1800.0, 0.0, "priority"),
    ("n_end", 2500.0, 0.0, "priority"),
    ("r_start", 520.0, -120.0, "priority"),
    ("r_meter", 810.0, -14.0, "traffic_light"),
]

EDGES = [
    # id, from, to, lanes, speed, priority
    ("main_in", "n_start", "n_merge", 2, MAIN_SPEED, 3),
    ("merge", "n_merge", "n_accend", 3, MAIN_SPEED, 3),
    ("main_mid", "n_accend", "n_inc", 2, MAIN_SPEED, 3),
    ("incident", "n_inc", "n_inc_end", 2, MAIN_SPEED, 3),
    ("main_out", "n_inc_end", "n_end", 2, MAIN_SPEED, 3),
    ("ramp_in", "r_start", "r_meter", 1, RAMP_SPEED, 1),
    ("ramp", "r_meter", "n_merge", 1, 22.22, 1),
]

CONNECTIONS = [
    # from, to, fromLane, toLane
    ("main_in", "merge", 0, 1),
    ("main_in", "merge", 1, 2),
    ("ramp", "merge", 0, 0),
    ("merge", "main_mid", 1, 0),
    ("merge", "main_mid", 2, 1),
    ("main_mid", "incident", 0, 0),
    ("main_mid", "incident", 1, 1),
    ("incident", "main_out", 0, 0),
    ("incident", "main_out", 1, 1),
    ("ramp_in", "ramp", 0, 0),
]


def _nodes_xml() -> str:
    rows = [f'    <node id="{i}" x="{x:.2f}" y="{y:.2f}" type="{t}"/>' for i, x, y, t in NODES]
    return "<nodes>\n" + "\n".join(rows) + "\n</nodes>\n"


def _edges_xml() -> str:
    rows = []
    for eid, fr, to, lanes, speed, prio in EDGES:
        rows.append(
            f'    <edge id="{eid}" from="{fr}" to="{to}" numLanes="{lanes}" '
            f'speed="{speed:.2f}" priority="{prio}"/>'
        )
    return "<edges>\n" + "\n".join(rows) + "\n</edges>\n"


def _connections_xml() -> str:
    rows = [
        f'    <connection from="{f}" to="{t}" fromLane="{fl}" toLane="{tl}"/>'
        for f, t, fl, tl in CONNECTIONS
    ]
    return "<connections>\n" + "\n".join(rows) + "\n</connections>\n"


_HEADER_RE = re.compile(r"<!-- generated on.*?-->\s*", re.DOTALL)


def strip_generated_header(text: str) -> str:
    """Remove netconvert's timestamped comment header (the only non-deterministic part)."""
    return _HEADER_RE.sub("", text, count=1)


def build_network(out_dir: Path) -> Path:
    """Write plain XML + run netconvert; return path to the byte-reproducible net file."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    nod, edg, con = out_dir / "merge.nod.xml", out_dir / "merge.edg.xml", out_dir / "merge.con.xml"
    for path, text in ((nod, _nodes_xml()), (edg, _edges_xml()), (con, _connections_xml())):
        path.write_bytes(text.encode("utf-8"))
    net = out_dir / "merge.net.xml"
    cmd = [
        binary("netconvert"),
        "--node-files", str(nod),
        "--edge-files", str(edg),
        "--connection-files", str(con),
        "--output-file", str(net),
        "--no-turnarounds", "true",
        "--tls.default-type", "static",
        "--offset.disable-normalization", "true",
        "--no-warnings", "true",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    net.write_bytes(strip_generated_header(net.read_text(encoding="utf-8")).encode("utf-8"))
    return net


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
