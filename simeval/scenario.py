"""Scenario space: named parameters, canonical ids, and deterministic SUMO input files."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

CONTROLLERS = ("none", "fixed", "alinea")

# Demand is given as a peak rate; the 1800 s demand window uses this profile.
DEMAND_PROFILE = ((0, 300, 0.7), (300, 1500, 1.0), (1500, 1800, 0.7))
DEMAND_END = 1800
SIM_END = 2100  # 300 s drain after demand stops; unfinished trips are still written

MAIN_ROUTE = "main_in merge main_mid incident main_out"
RAMP_ROUTE = "ramp_in ramp merge main_mid incident main_out"
SSM_EDGES = ("main_in", "ramp", "merge", "main_mid", "incident", "main_out")

# How the incident is simulated (see runner.SimOptions): a vehicle in the stream told to stop on the
# right lane ('stall', default), a dedicated stopped vehicle ('blocker', 'blocker_insert'), or a
# lane-permission change via TraCI ('traci_disallow' = v1), optionally with a slow-down ahead.
INCIDENT_METHODS = ("stall", "blocker", "blocker_insert", "vss_disallow", "traci_disallow")
BLOCKER_ID = "incident_blocker"   # excluded from all KPIs (kpi.py)
BLOCKER_POS = 100.0               # m from the start of edge 'incident' (200 m long): the stop
# Drive-in lead time: 346 m of main_mid + 100 m, cruising at 33.3 m/s and braking at 4.5 m/s^2
# takes about 17 s in free flow, so the blocker reaches its stop close to incident_start.
BLOCKER_LEAD_S = 17.0


@dataclass(frozen=True)
class Param:
    name: str
    lo: float
    hi: float
    unit: str
    integer: bool = False


# Continuous (probe-able) parameters and their admissible ranges.
PARAMS: dict[str, Param] = {
    p.name: p
    for p in (
        Param("main_demand", 2400, 4200, "veh/h", integer=True),
        Param("ramp_demand", 300, 1200, "veh/h", integer=True),
        Param("truck_share", 0.0, 0.25, "-"),
        Param("incident_start", 300, 1200, "s", integer=True),
        Param("incident_duration", 0, 900, "s", integer=True),
        Param("sigma", 0.0, 0.9, "-"),
    )
}


@dataclass(frozen=True)
class Scenario:
    main_demand: int = 3200
    ramp_demand: int = 600
    truck_share: float = 0.10
    incident_start: int = 600
    incident_duration: int = 0
    sigma: float = 0.5
    controller: str = "alinea"
    seed: int = 1

    def __post_init__(self) -> None:
        if self.controller not in CONTROLLERS:
            raise ValueError(f"unknown controller {self.controller!r}")
        for name, p in PARAMS.items():
            v = getattr(self, name)
            if not (p.lo <= v <= p.hi):
                raise ValueError(f"{name}={v} outside [{p.lo}, {p.hi}]")

    def canonical(self) -> dict:
        d = asdict(self)
        for name, p in PARAMS.items():
            d[name] = int(round(d[name])) if p.integer else round(float(d[name]), 4)
        return d

    @property
    def id(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(blob.encode()).hexdigest()[:12]

    def with_(self, **kw) -> "Scenario":
        for name, p in PARAMS.items():
            if name in kw and p.integer:
                kw[name] = int(round(kw[name]))
            elif name in kw:
                kw[name] = round(float(kw[name]), 4)
        return replace(self, **kw)

    @classmethod
    def from_dict(cls, d: dict) -> "Scenario":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


NOMINAL = Scenario()


def blocker_xml(s: Scenario, incident_method: str = "blocker") -> list[str]:
    """A vehicle that stands on incident_0 until the incident ends (``until`` is fixed).

    It is an ordinary SUMO vehicle with a stop, so upstream traffic reacts to it through
    car following and lane changing, and no lane permission changes during the run.

    * ``blocker`` (drive-in): enters main_mid lane 0 ``BLOCKER_LEAD_S`` before the incident
      start, at the speed SUMO deems safe, and brakes normally to its stop; followers see
      an ordinary braking leader.
    * ``blocker_insert``: is inserted standing at the stop. SUMO only inserts it once the
      follower on that lane could stop behind it, which in dense traffic delays the onset.

    The realised onset is read back from SUMO's stop output (kpi ``incident_onset_s``).
    """
    if s.incident_duration <= 0 or incident_method not in ("blocker", "blocker_insert"):
        return []
    until = min(s.incident_start + s.incident_duration, SIM_END)
    stop = f'        <stop lane="incident_0" endPos="{BLOCKER_POS:.1f}" until="{until}"/>'
    vt = '    <vType id="blocker_t" vClass="passenger" length="5.0" minGap="2.5" sigma="0" speedFactor="1"/>'
    if incident_method == "blocker":
        head = (f'    <vehicle id="{BLOCKER_ID}" type="blocker_t" route="r_blocker" '
                f'depart="{s.incident_start - BLOCKER_LEAD_S:.1f}" departLane="0" departPos="0" departSpeed="max">')
        route = '    <route id="r_blocker" edges="main_mid incident main_out"/>'
    else:
        head = (f'    <vehicle id="{BLOCKER_ID}" type="blocker_t" route="r_blocker" depart="{s.incident_start}" '
                f'departLane="0" departPos="{BLOCKER_POS - 1.0:.1f}" departSpeed="0">')
        route = '    <route id="r_blocker" edges="incident main_out"/>'
    return [vt, route, head, stop, "    </vehicle>"]


def incident_routes_xml(s: Scenario, incident_method: str = "stall") -> str:
    """Separate route file for the blocker: SUMO drops vehicles that are out of departure
    order within one file, and the demand flows begin at 0/300/1500 s."""
    return "\n".join(["<routes>", *blocker_xml(s, incident_method), "</routes>"]) + "\n"


def routes_xml(s: Scenario) -> str:
    """Route/demand file. Arrivals are exponential (seeded by SUMO --seed)."""
    car_p = round(1.0 - s.truck_share, 4)
    lines = [
        "<routes>",
        '    <vTypeDistribution id="mix">',
        f'        <vType id="car" vClass="passenger" length="5.0" minGap="2.5" accel="2.6" decel="4.5" '
        f'sigma="{s.sigma:.4f}" tau="1.0" maxSpeed="36.0" speedFactor="normc(1,0.1,0.8,1.2)" '
        f'probability="{car_p:.4f}"/>',
        f'        <vType id="truck" vClass="truck" length="12.0" minGap="3.0" accel="1.3" decel="4.0" '
        f'sigma="{s.sigma:.4f}" tau="1.2" maxSpeed="25.0" speedFactor="normc(1,0.05,0.9,1.1)" '
        f'probability="{s.truck_share:.4f}"/>',
        "    </vTypeDistribution>",
        f'    <route id="r_main" edges="{MAIN_ROUTE}"/>',
        f'    <route id="r_ramp" edges="{RAMP_ROUTE}"/>',
    ]
    for i, (b, e, m) in enumerate(DEMAND_PROFILE):
        for tag, rate, lane in (("main", s.main_demand, "best"), ("ramp", s.ramp_demand, "first")):
            lam = rate * m / 3600.0  # veh/s
            if lam <= 0:
                continue
            lines.append(
                f'    <flow id="{tag}_{i}" type="mix" route="r_{tag}" begin="{b}" end="{e}" '
                f'period="exp({lam:.6f})" departLane="{lane}" departSpeed="max"/>'
            )
    lines.append("</routes>")
    return "\n".join(lines) + "\n"


DETECTORS_XML = """<additional>
    <inductionLoop id="loop_merge_1" lane="merge_1" pos="165" period="60" file="e1_merge.xml"/>
    <inductionLoop id="loop_merge_2" lane="merge_2" pos="165" period="60" file="e1_merge.xml"/>
    <inductionLoop id="loop_down_0" lane="main_mid_0" pos="100" period="30" file="e1_down.xml"/>
    <inductionLoop id="loop_down_1" lane="main_mid_1" pos="100" period="30" file="e1_down.xml"/>
    <laneAreaDetector id="e2_ramp" lane="ramp_in_0" pos="0" endPos="308.0" period="60" file="e2_ramp.xml"/>
</additional>
"""


def write_inputs(s: Scenario, run_dir: Path, incident_method: str = "stall") -> tuple[Path, Path]:
    if incident_method not in INCIDENT_METHODS:
        raise ValueError(f"unknown incident method {incident_method!r}")
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    rou, add = run_dir / "routes.rou.xml", run_dir / "detectors.add.xml"
    rou.write_bytes(routes_xml(s).encode("utf-8"))
    (run_dir / "incident.rou.xml").write_bytes(incident_routes_xml(s, incident_method).encode("utf-8"))
    add.write_bytes(DETECTORS_XML.encode("utf-8"))
    # SSM is restricted to the mainline and the metered-ramp downstream of the stop line:
    # TTC to a queue standing at a red meter is ordinary signal behaviour, not a merge conflict.
    (run_dir / "ssm_edges.txt").write_bytes("".join(f"edge:{e}\n" for e in SSM_EDGES).encode())
    (run_dir / "scenario.json").write_text(json.dumps(s.canonical(), sort_keys=True, indent=1))
    return rou, add
