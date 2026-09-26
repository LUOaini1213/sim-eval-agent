"""Which parameter to probe next.

The action space is a closed vocabulary: ``probe:<param>`` for each scenario parameter,
plus ``stop``. A policy only ever returns one of these strings; the agent turns an action
into scenarios itself. Neither policy can emit SUMO/TraCI calls or scenario values.
"""
from __future__ import annotations

import json
import re
from typing import Callable

from .scenario import PARAMS

VOCABULARY: tuple[str, ...] = tuple(f"probe:{p}" for p in PARAMS) + ("stop",)


def candidates(oat_by_controller: dict[str, list[dict]], probed: set[str]) -> list[str]:
    """Params (ranked by max influence over controllers) with a verdict flip, not yet probed."""
    best: dict[str, float] = {}
    for rows in oat_by_controller.values():
        for r in rows:
            if r["flip_levels"]:
                best[r["param"]] = max(best.get(r["param"], 0.0), r["influence"])
    ranked = sorted(best, key=lambda p: (-best[p], p))
    return [p for p in ranked if p not in probed]


class DeterministicPolicy:
    name = "deterministic"

    def choose(self, oat_by_controller: dict[str, list[dict]], probed: set[str]) -> tuple[str, str]:
        c = candidates(oat_by_controller, probed)
        if not c:
            return "stop", "no unprobed parameter shows a verdict flip in the one-at-a-time screen"
        return f"probe:{c[0]}", f"largest paired mean-delta-margin magnitude among unprobed params with a verdict flip ({c[0]})"


class LLMPolicy:
    """Asks a model to pick one action from VOCABULARY. Off by default; never used in CI.

    ``chat`` is any callable prompt -> text (see :func:`anthropic_chat`). A reply that
    is not exactly one vocabulary item, or proposes an already-probed / flip-less
    parameter, is rejected and the deterministic choice is used instead (logged).
    """

    name = "llm"

    def __init__(self, chat: Callable[[str], str]):
        self.chat = chat
        self.fallback = DeterministicPolicy()
        self.log: list[dict] = []

    def prompt(self, oat_by_controller: dict[str, list[dict]], probed: set[str]) -> str:
        table = {
            c: [{"param": r["param"], "influence": r["influence"], "flip_levels": r["flip_levels"]} for r in rows]
            for c, rows in oat_by_controller.items()
        }
        return (
            "You steer a simulation test campaign for a ramp-metering controller.\n"
            "One-at-a-time sensitivity results (paired seeds), per controller:\n"
            f"{json.dumps(table, sort_keys=True)}\n"
            f"Already probed: {sorted(probed)}\n"
            "Choose the single next action. Reply with JSON {\"action\": <one of>} where <one of> is\n"
            f"{json.dumps(list(VOCABULARY))}. Only a parameter with a non-empty flip_levels can be probed."
        )

    def choose(self, oat_by_controller: dict[str, list[dict]], probed: set[str]) -> tuple[str, str]:
        text = self.chat(self.prompt(oat_by_controller, probed))
        action = parse_action(text)
        allowed = {f"probe:{p}" for p in candidates(oat_by_controller, probed)} | {"stop"}
        entry = {"raw": text[:500], "parsed": action}
        if action is None or action not in allowed:
            fb, why = self.fallback.choose(oat_by_controller, probed)
            entry.update(accepted=False, used=fb)
            self.log.append(entry)
            return fb, f"LLM reply rejected ({action!r}); deterministic fallback: {why}"
        entry.update(accepted=True, used=action)
        self.log.append(entry)
        return action, "chosen by LLM from the closed vocabulary"


def parse_action(text: str) -> str | None:
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        return None
    try:
        a = json.loads(m.group(0)).get("action")
    except (json.JSONDecodeError, AttributeError):
        return None
    return a if a in VOCABULARY else None


def anthropic_chat(model: str = "claude-opus-5") -> Callable[[str], str]:  # pragma: no cover - needs network
    """Adapter over the official Anthropic SDK (``pip install anthropic``)."""
    import anthropic

    client = anthropic.Anthropic()

    def chat(prompt: str) -> str:
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason == "refusal":
            return ""  # rejected by parse_action -> deterministic fallback
        return "".join(b.text for b in resp.content if b.type == "text")

    return chat
