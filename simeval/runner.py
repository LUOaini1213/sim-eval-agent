"""Run one scenario headless in SUMO, driving the ramp meter via TraCI.

How the incident (right lane of ``incident`` blocked) is simulated is a :class:`SimOptions`
choice. ``traci_disallow`` is the original method; it was found to cause the collisions
behind the INVALID runs (see ``scripts/diagnose_invalid.py`` and the README), so it is only
kept to reproduce that diagnosis. The default, ``stall``, tells a vehicle already on the lane,
far enough upstream to stop with ordinary braking, to stop there until the incident ends.
"""
from __future__ import annotations

import heapq
import os
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from . import controller as ctl
from .scenario import BLOCKER_POS, INCIDENT_METHODS, SIM_END, Scenario, write_inputs
from .sumo_env import binary

STEP_LENGTH = 0.5
SSM_RECORD_THRESHOLD = 3.0  # s; SSM logs conflicts below this; kpi.py counts those below 1.5
TLS_ID = "r_meter"
INCIDENT_LANE = "incident_0"
DOWN_LOOPS = ("loop_down_0", "loop_down_1")
VSS_LANES = ("main_mid_0", "main_mid_1")   # slowed ahead of the closure in 'vss_disallow'
VSS_SPEED = 16.67                          # m/s (60 km/h)
VSS_LEAD_S = 60.0                          # slow-down starts this long before the closure
STALL_MARGIN_M = 5.0                       # extra distance required beyond v^2/(2 decel)
STALL_RETRY_S = 0.5                        # if no vehicle can stop yet, try again this much later


@dataclass(frozen=True)
class SimOptions:
    incident_method: str = "stall"
    amber_s: float = ctl.AMBER_S
    log_warnings: bool = False   # write SUMO warnings to sumo_log.txt in the run dir

    def __post_init__(self) -> None:
        if self.incident_method not in INCIDENT_METHODS:
            raise ValueError(f"unknown incident method {self.incident_method!r}")

    def as_dict(self) -> dict:
        return asdict(self)


DEFAULT_OPTIONS = SimOptions()
LEGACY_OPTIONS = SimOptions(incident_method="traci_disallow", amber_s=0.0)  # what produced results v1


def sumo_cmd(s: Scenario, opts: SimOptions = DEFAULT_OPTIONS) -> list[str]:
    """SUMO command line. All file arguments are bare names inside the run directory, which
    is SUMO's working directory: some SUMO file readers cannot open non-ASCII absolute paths
    on Windows, and this repo may live under one. The net file is copied in for that reason."""
    return [
        binary("sumo"),
        "--net-file", "merge.net.xml",
        "--route-files", "routes.rou.xml,incident.rou.xml",
        "--additional-files", "detectors.add.xml",
        "--seed", str(s.seed),
        "--step-length", str(STEP_LENGTH),
        "--begin", "0", "--end", str(SIM_END),
        "--tripinfo-output", "tripinfo.xml",
        "--tripinfo-output.write-unfinished", "true",
        "--statistic-output", "stats.xml",
        "--device.ssm.probability", "1",
        "--device.ssm.deterministic", "true",
        "--device.ssm.file", "ssm.xml",
        "--device.ssm.measures", "TTC",
        "--device.ssm.thresholds", str(SSM_RECORD_THRESHOLD),
        "--device.ssm.range", "50",
        "--device.ssm.trajectories", "false",
        "--device.ssm.filter-edges.input-file", "ssm_edges.txt",
        "--collision-output", "collisions.xml",
        "--stop-output", "stops.xml",
        "--collision.action", "warn",
        "--collision.check-junctions", "true",
        "--time-to-teleport", "300",
        "--no-step-log", "true",
        *(["--error-log", "sumo_log.txt"] if opts.log_warnings else ["--no-warnings", "true"]),
        "--duration-log.disable", "true",
    ]


def _apply_rate(traci, rate: float, amber_s: float) -> None:
    red = ctl.red_time_for_rate(rate, amber_s)
    if red is None:
        phases = [traci.trafficlight.Phase(3600, "G")]
    elif amber_s > 0:
        phases = [traci.trafficlight.Phase(ctl.GREEN_S, "G"), traci.trafficlight.Phase(amber_s, "y"),
                  traci.trafficlight.Phase(red, "r")]
    else:
        phases = [traci.trafficlight.Phase(ctl.GREEN_S, "G"), traci.trafficlight.Phase(red, "r")]
    logic = traci.trafficlight.Logic("meter", 0, 0, phases)
    traci.trafficlight.setProgramLogic(TLS_ID, logic)
    traci.trafficlight.setProgram(TLS_ID, "meter")


def incident_events(s: Scenario, opts: SimOptions) -> dict[float, list[tuple[str, object]]]:
    """TraCI actions for the incident, keyed by simulation time (empty for the blocker methods)."""
    ev: dict[float, list[tuple[str, object]]] = {}
    if s.incident_duration <= 0 or opts.incident_method in ("blocker", "blocker_insert"):
        return ev
    on, off = float(s.incident_start), float(min(s.incident_start + s.incident_duration, SIM_END))
    if opts.incident_method == "stall":
        ev.setdefault(on, []).append(("stall", off))
        return ev
    if opts.incident_method == "vss_disallow":
        ev.setdefault(on - VSS_LEAD_S, []).append(("speed", VSS_SPEED))
        ev.setdefault(off, []).append(("speed", None))
    ev.setdefault(on, []).append(("disallow", ["passenger", "truck"]))
    ev.setdefault(off, []).append(("disallow", []))
    return ev


def stall_candidates(vehicles: list[tuple[str, str, float, float, float]], mid_len: float,
                     stop_pos: float = BLOCKER_POS, margin: float = None) -> list[tuple[float, str]]:
    """Vehicles that can reach a stop at ``stop_pos`` on incident_0 braking at most ``decel``.

    vehicles: (id, lane, lane position, speed, decel). Returns (distance, id), nearest first.
    Only vehicles on main_mid_0 or incident_0 upstream of the stop qualify; the stopping distance
    v^2 / (2 decel) plus ``margin`` must fit, so the stall never needs more than ordinary braking.
    """
    margin = STALL_MARGIN_M if margin is None else margin
    out = []
    for vid, lane, pos, speed, decel in vehicles:
        if lane == INCIDENT_LANE:
            dist = stop_pos - pos
        elif lane == "main_mid_0":
            dist = (mid_len - pos) + stop_pos
        else:
            continue
        if dist > 0 and dist >= speed * speed / (2.0 * decel) + margin:
            out.append((round(dist, 3), vid))
    return sorted(out)


def _stall(conn, until: float) -> str | None:
    """Give the nearest vehicle that can brake comfortably a stop on incident_0 until ``until``."""
    import traci

    mid_len = conn.lane.getLength("main_mid_0")
    vehs = []
    for lane in ("main_mid_0", INCIDENT_LANE):
        for vid in conn.lane.getLastStepVehicleIDs(lane):
            vehs.append((vid, lane, conn.vehicle.getLanePosition(vid), conn.vehicle.getSpeed(vid),
                         conn.vehicle.getDecel(vid)))
    for _, vid in stall_candidates(vehs, mid_len):
        try:
            conn.vehicle.setStop(vid, "incident", pos=BLOCKER_POS, laneIndex=0, duration=0.0, until=until)
            return vid
        except traci.TraCIException:
            continue
    return None


def run_scenario(s: Scenario, net: Path, run_dir: Path, label: str | None = None,
                 opts: SimOptions = DEFAULT_OPTIONS) -> dict:
    """Simulate ``s``; raw outputs land in ``run_dir``. Returns run metadata (not KPIs)."""
    import traci  # imported lazily so pure-Python parts do not need SUMO

    run_dir = Path(run_dir)
    write_inputs(s, run_dir, incident_method=opts.incident_method)
    shutil.copyfile(net, run_dir / "merge.net.xml")
    c = ctl.make(s.controller)
    rates: list[tuple[float, float]] = []
    t0 = time.perf_counter()
    lbl = label or f"run_{s.id}"
    cwd = os.getcwd()
    os.chdir(run_dir)
    try:
        traci.start(sumo_cmd(s, opts), label=lbl)
    finally:
        os.chdir(cwd)
    conn = traci.getConnection(lbl)
    try:
        rate = c.initial_rate()
        _apply_rate(conn, rate, opts.amber_s)
        rates.append((0.0, rate))
        inc_events = incident_events(s, opts)
        # Event times: control updates every CONTROL_INTERVAL_S, plus incident actions.
        events = set(inc_events)
        t = ctl.CONTROL_INTERVAL_S
        while t < SIM_END:
            events.add(t)
            t += ctl.CONTROL_INTERVAL_S
        pending = sorted(events)  # a sorted list is a valid heap
        vss_default = {ln: conn.lane.getMaxSpeed(ln) for ln in VSS_LANES}
        occ_acc = 0.0
        stalled = None
        while pending:
            te = heapq.heappop(pending)
            conn.simulationStep(te)
            now = conn.simulation.getTime()
            for kind, arg in inc_events.get(te, []):
                if kind == "disallow":
                    conn.lane.setDisallowed(INCIDENT_LANE, arg)
                elif kind == "speed":
                    for ln in VSS_LANES:
                        conn.lane.setMaxSpeed(ln, vss_default[ln] if arg is None else arg)
                elif kind == "stall" and stalled is None:
                    stalled = _stall(conn, arg)
                    retry = now + STALL_RETRY_S
                    if stalled is None and retry < arg:
                        inc_events.setdefault(retry, []).append(("stall", arg))
                        heapq.heappush(pending, retry)
            if now % ctl.CONTROL_INTERVAL_S == 0:
                occ_acc = sum(conn.inductionloop.getLastIntervalOccupancy(d) for d in DOWN_LOOPS) / len(DOWN_LOOPS)
                ramp_q = conn.lanearea.getLastStepVehicleNumber("e2_ramp")
                new_rate = c.update(ctl.Measurement(now, occ_acc, ramp_q))
                if new_rate != rate:
                    _apply_rate(conn, new_rate, opts.amber_s)
                    rate = new_rate
                rates.append((now, rate))
        conn.simulationStep(float(SIM_END))
    finally:
        conn.close()
    wall = time.perf_counter() - t0
    return {"wall_s": round(wall, 2), "rates": rates, "stalled_vehicle": stalled}
