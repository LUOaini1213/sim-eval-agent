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


def write_inputs(s: Scenario, run_dir: Path) -> tuple[Path, Path]:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    rou, add = run_dir / "routes.rou.xml", run_dir / "detectors.add.xml"
    rou.write_bytes(routes_xml(s).encode("utf-8"))
    add.write_bytes(DETECTORS_XML.encode("utf-8"))
    # SSM is restricted to the mainline and the metered-ramp downstream of the stop line:
    # TTC to a queue standing at a red meter is ordinary signal behaviour, not a merge conflict.
    (run_dir / "ssm_edges.txt").write_bytes("".join(f"edge:{e}\n" for e in SSM_EDGES).encode())
    (run_dir / "scenario.json").write_text(json.dumps(s.canonical(), sort_keys=True, indent=1))
    return rou, add
