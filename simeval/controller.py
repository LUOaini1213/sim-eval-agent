"""System under test: ramp-metering controllers.

Controllers are pure Python (no TraCI) so their logic is unit-testable. Every control
interval the runner hands them a :class:`Measurement` and applies the returned metering
rate as a two-phase signal program (green ``GREEN_S`` then red) at the ramp meter.
"""
from __future__ import annotations

from dataclasses import dataclass

CONTROL_INTERVAL_S = 30.0
GREEN_S = 2.0          # one-car-per-green
R_MIN = 240.0          # veh/h, lowest metering rate ALINEA may command
R_MAX = 1800.0         # veh/h; at/above this the meter rests in green (no metering)


@dataclass(frozen=True)
class Measurement:
    t: float
    occupancy_pct: float     # mean downstream occupancy over the last interval, %
    ramp_queue_veh: int      # vehicles currently on the metered approach (E2 detector)


def red_time_for_rate(rate_veh_h: float) -> float | None:
    """Red duration for a one-car-per-green cycle; None means rest in green."""
    if rate_veh_h >= R_MAX:
        return None
    cycle = 3600.0 / max(rate_veh_h, 1e-6)
    return max(cycle - GREEN_S, 0.5)


class NoControl:
    name = "none"

    def initial_rate(self) -> float:
        return R_MAX

    def update(self, m: Measurement) -> float:
        return R_MAX


class FixedTime:
    """Pre-timed metering at a constant rate, chosen for the nominal ramp demand."""

    name = "fixed"

    def __init__(self, rate_veh_h: float = 720.0):
        self.rate = rate_veh_h

    def initial_rate(self) -> float:
        return self.rate

    def update(self, m: Measurement) -> float:
        return self.rate


class Alinea:
    """ALINEA (Papageorgiou et al. 1991) with a queue-override flush.

    r(k) = r(k-1) + K_R * (o_target - o_out(k)),  clipped to [R_MIN, R_MAX].
    If the ramp approach holds more than ``queue_limit_veh`` vehicles the rate is set to R_MAX for that interval
    (the integrator state is also reset there, so it does not wind up).
    """

    name = "alinea"

    def __init__(self, target_occ_pct: float = 12.0, k_r: float = 70.0,
                 queue_limit_veh: int = 25, r0: float = 900.0):
        self.target = target_occ_pct
        self.k_r = k_r
        self.queue_limit_veh = queue_limit_veh
        self.rate = r0

    def initial_rate(self) -> float:
        return self.rate

    def update(self, m: Measurement) -> float:
        r = self.rate + self.k_r * (self.target - m.occupancy_pct)
        r = min(max(r, R_MIN), R_MAX)
        if m.ramp_queue_veh > self.queue_limit_veh:
            r = R_MAX
        self.rate = r
        return r


def make(name: str):
    if name == "none":
        return NoControl()
    if name == "fixed":
        return FixedTime()
    if name == "alinea":
        return Alinea()
    raise ValueError(name)
