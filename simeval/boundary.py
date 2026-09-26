"""Bisection along one parameter between a passing and a failing value."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Bisection:
    param: str
    controller: str
    pass_value: float     # value whose majority verdict is PASS
    fail_value: float     # value whose majority verdict is not PASS
    tol: float
    integer: bool = False
    history: list[dict] = field(default_factory=list)

    def done(self) -> bool:
        if abs(self.fail_value - self.pass_value) <= self.tol:
            return True
        mid = self._mid()
        return mid in (self.pass_value, self.fail_value)

    def _mid(self) -> float:
        m = (self.pass_value + self.fail_value) / 2.0
        return int(round(m)) if self.integer else round(m, 4)

    def next_value(self) -> float:
        return self._mid()

    def update(self, value: float, failed: bool, run_ids: list[str], verdicts: list[str]) -> None:
        self.history.append({"value": value, "failed": failed, "verdicts": verdicts, "run_ids": run_ids})
        if failed:
            self.fail_value = value
        else:
            self.pass_value = value

    def summary(self) -> dict:
        return {
            "param": self.param,
            "controller": self.controller,
            "last_pass": self.pass_value,
            "first_fail": self.fail_value,
            "width": round(abs(self.fail_value - self.pass_value), 4),
            "tol": self.tol,
            "converged": abs(self.fail_value - self.pass_value) <= self.tol or self.done(),
            "steps": self.history,
        }
