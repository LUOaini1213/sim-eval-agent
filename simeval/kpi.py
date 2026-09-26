"""KPIs parsed from SUMO output files of one run directory.

All KPIs come from files SUMO wrote (tripinfo, statistic, E1/E2 detectors, SSM);
nothing is taken from TraCI state, so any number can be re-derived from the raw files.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .scenario import DEMAND_END

TTC_COUNT_THRESHOLD = 1.5  # s; a conflict counts if its minimum TTC is strictly below this
MERGE_LOOPS = ("loop_merge_1", "loop_merge_2")


def _f(x: str | None) -> float | None:
    if x is None or x in ("", "NA", "-1"):
        return None
    return float(x)


def _p95(xs: list[float]) -> float:
    """Nearest-rank 95th percentile (no interpolation, so it is an observed value)."""
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = max(0, -(-95 * len(xs) // 100) - 1)  # ceil(0.95 n) - 1
    return xs[k]


def parse_tripinfo(path: Path) -> dict:
    n = arrived = 0
    delay = 0.0
    ramp_delays: list[float] = []
    for ev, el in ET.iterparse(path):
        if el.tag != "tripinfo":
            continue
        n += 1
        # timeLoss: loss while driving; departDelay: waiting before insertion (queue spilled
        # out of the network). Both count as delay experienced by the traveller.
        d = float(el.get("timeLoss", 0.0)) + float(el.get("departDelay", 0.0))
        delay += d
        if el.get("id", "").startswith("ramp_"):
            ramp_delays.append(d)
        if float(el.get("arrival", -1)) >= 0:
            arrived += 1
        el.clear()
    return {"vehicles": n, "arrived": arrived, "total_delay_s": delay,
            "ramp_vehicles": len(ramp_delays), "ramp_p95_delay_s": _p95(ramp_delays)}


def parse_stats(path: Path) -> dict:
    root = ET.parse(path).getroot()
    veh = root.find("vehicles")
    tel = root.find("teleports")
    saf = root.find("safety")
    return {
        "loaded": int(veh.get("loaded")),
        "inserted": int(veh.get("inserted")),
        "not_inserted": int(veh.get("waiting")),
        "teleports": int(tel.get("total")),
        "collisions": int(saf.get("collisions")),
        "emergency_braking": int(saf.get("emergencyBraking", 0)),
    }


def parse_merge_speed(path: Path, until: float = DEMAND_END) -> float | None:
    """Flow-weighted mean spot speed (km/h) on the mainline lanes inside the merge area."""
    num = den = 0.0
    for el in ET.parse(path).getroot().iter("interval"):
        if el.get("id") not in MERGE_LOOPS or float(el.get("begin")) >= until:
            continue
        n = int(el.get("nVehContrib"))
        sp = _f(el.get("speed"))
        if n > 0 and sp is not None:
            num += n * sp
            den += n
    return None if den == 0 else 3.6 * num / den


def parse_ramp_queue(path: Path) -> int:
    """Maximum number of vehicles present on the metered ramp approach (308 m, ~40 cars)."""
    vals = [int(el.get("maxVehicleNumber")) for el in ET.parse(path).getroot().iter("interval")]
    return max(vals) if vals else 0


def parse_ssm(path: Path, threshold: float = TTC_COUNT_THRESHOLD) -> int:
    """Number of conflicts whose minimum TTC is strictly below ``threshold``."""
    count = 0
    for conflict in ET.parse(path).getroot().iter("conflict"):
        el = conflict.find("minTTC")
        if el is None:
            continue
        v = _f(el.get("value"))
        if v is not None and v < threshold:
            count += 1
    return count


def parse_collisions(path: Path) -> list[str]:
    """Lanes on which collisions happened (one entry per collision, in file order)."""
    if not Path(path).exists():
        return []
    return [el.get("lane") for el in ET.parse(path).getroot().iter("collision")]


def compute_kpis(run_dir: Path) -> dict:
    d = Path(run_dir)
    trip = parse_tripinfo(d / "tripinfo.xml")
    stats = parse_stats(d / "stats.xml")
    ttc = parse_ssm(d / "ssm.xml")
    n = max(trip["vehicles"], 1)
    speed = parse_merge_speed(d / "e1_merge.xml")
    return {
        "vehicles": trip["vehicles"],
        "throughput_veh": trip["arrived"],
        "total_delay_veh_h": round(trip["total_delay_s"] / 3600.0, 3),
        "mean_delay_s": round(trip["total_delay_s"] / n, 2),
        "merge_speed_kmh": None if speed is None else round(speed, 2),
        "ramp_queue_max_veh": parse_ramp_queue(d / "e2_ramp.xml"),
        "ramp_p95_delay_s": round(trip["ramp_p95_delay_s"], 2),
        "ttc_conflicts": ttc,
        "ttc_per_1000veh": round(1000.0 * ttc / n, 3),
        "teleports": stats["teleports"],
        "collisions": stats["collisions"],
        "not_inserted": stats["not_inserted"],
        "emergency_braking": stats["emergency_braking"],
        "collision_lanes": parse_collisions(d / "collisions.xml"),
    }
