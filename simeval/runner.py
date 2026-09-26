"""Run one scenario headless in SUMO, driving the ramp meter and the incident via TraCI."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from . import controller as ctl
from .scenario import SIM_END, Scenario, write_inputs
from .sumo_env import binary

STEP_LENGTH = 0.5
SSM_RECORD_THRESHOLD = 3.0  # s; SSM logs conflicts below this; kpi.py counts those below 1.5
TLS_ID = "r_meter"
INCIDENT_LANE = "incident_0"
DOWN_LOOPS = ("loop_down_0", "loop_down_1")


def sumo_cmd(s: Scenario) -> list[str]:
    """SUMO command line. All file arguments are bare names inside the run directory, which
    is SUMO's working directory: some SUMO file readers cannot open non-ASCII absolute paths
    on Windows, and this repo may live under one. The net file is copied in for that reason."""
    return [
        binary("sumo"),
        "--net-file", "merge.net.xml",
        "--route-files", "routes.rou.xml",
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
        "--collision.action", "warn",
        "--collision.check-junctions", "true",
        "--time-to-teleport", "300",
        "--no-step-log", "true",
        "--no-warnings", "true",
        "--duration-log.disable", "true",
    ]


def _apply_rate(traci, rate: float) -> None:
    red = ctl.red_time_for_rate(rate)
    if red is None:
        phases = [traci.trafficlight.Phase(3600, "G")]
    else:
        phases = [traci.trafficlight.Phase(ctl.GREEN_S, "G"), traci.trafficlight.Phase(red, "r")]
    logic = traci.trafficlight.Logic("meter", 0, 0, phases)
    traci.trafficlight.setProgramLogic(TLS_ID, logic)
    traci.trafficlight.setProgram(TLS_ID, "meter")


def run_scenario(s: Scenario, net: Path, run_dir: Path, label: str | None = None) -> dict:
    """Simulate ``s``; raw outputs land in ``run_dir``. Returns run metadata (not KPIs)."""
    import traci  # imported lazily so pure-Python parts do not need SUMO

    run_dir = Path(run_dir)
    write_inputs(s, run_dir)
    shutil.copyfile(net, run_dir / "merge.net.xml")
    c = ctl.make(s.controller)
    rates: list[tuple[float, float]] = []
    t0 = time.perf_counter()
    lbl = label or f"run_{s.id}"
    cwd = os.getcwd()
    os.chdir(run_dir)
    try:
        traci.start(sumo_cmd(s), label=lbl)
    finally:
        os.chdir(cwd)
    conn = traci.getConnection(lbl)
    try:
        rate = c.initial_rate()
        _apply_rate(conn, rate)
        rates.append((0.0, rate))
        inc_on, inc_off = s.incident_start, s.incident_start + s.incident_duration
        # Event times: control updates every CONTROL_INTERVAL_S, plus incident on/off.
        events = set()
        t = ctl.CONTROL_INTERVAL_S
        while t < SIM_END:
            events.add(t)
            t += ctl.CONTROL_INTERVAL_S
        if s.incident_duration > 0:
            events.update({float(inc_on), float(min(inc_off, SIM_END))})
        occ_acc = 0.0
        for te in sorted(events):
            conn.simulationStep(te)
            now = conn.simulation.getTime()
            if s.incident_duration > 0 and now == inc_on:
                conn.lane.setDisallowed(INCIDENT_LANE, ["passenger", "truck"])
            if s.incident_duration > 0 and now == inc_off:
                conn.lane.setDisallowed(INCIDENT_LANE, [])
            if now % ctl.CONTROL_INTERVAL_S == 0:
                occ_acc = sum(conn.inductionloop.getLastIntervalOccupancy(d) for d in DOWN_LOOPS) / len(DOWN_LOOPS)
                queue = conn.lanearea.getLastStepVehicleNumber("e2_ramp")
                new_rate = c.update(ctl.Measurement(now, occ_acc, queue))
                if new_rate != rate:
                    _apply_rate(conn, new_rate)
                    rate = new_rate
                rates.append((now, rate))
        conn.simulationStep(float(SIM_END))
    finally:
        conn.close()
    wall = time.perf_counter() - t0
    return {"wall_s": round(wall, 2), "rates": rates}
