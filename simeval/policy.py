"""Which parameter, in which direction, to probe next.

The action space is a closed vocabulary: ``probe:<param>:<lo|hi>`` for each scenario
parameter and direction (bisect between nominal and that end of the range), plus ``stop``.
A policy only ever returns one of these strings; the agent turns an action into scenarios
itself. Neither policy can emit SUMO/TraCI calls or scenario values.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Callable

from .scenario import PARAMS

LEVELS = ("lo", "hi")
VOCABULARY: tuple[str, ...] = tuple(f"probe:{p}:{lv}" for p in PARAMS for lv in LEVELS) + ("stop",)


def candidates(oat_by_controller: dict[str, list[dict]], probed: set[str]) -> list[str]:
    """Actions ``probe:<param>:<level>`` whose end flips the majority verdict for at least one
    controller, not yet probed, ranked by the largest |paired mean delta margin| at that end."""
    best: dict[str, float] = {}
    for rows in oat_by_controller.values():
        for r in rows:
            for lv in r["flip_levels"]:
                a = f"probe:{r['param']}:{lv}"
                score = abs(r["levels"][lv]["mean_delta_margin"]) if "levels" in r else r["influence"]
                best[a] = max(best.get(a, 0.0), score)
    ranked = sorted(best, key=lambda a: (-best[a], a))
    return [a for a in ranked if a not in probed]


class DeterministicPolicy:
    name = "deterministic"

    def choose(self, oat_by_controller: dict[str, list[dict]], probed: set[str],
               context: dict | None = None) -> tuple[str, str]:
        c = candidates(oat_by_controller, probed)
        if not c:
            return "stop", "no unprobed parameter/direction shows a verdict flip in the one-at-a-time screen"
        return c[0], f"largest paired |mean delta margin| among unprobed directions with a verdict flip ({c[0]})"


def oat_table(oat_by_controller: dict[str, list[dict]]) -> dict:
    """The compact view of the one-at-a-time results that the LLM sees."""
    out = {}
    for c, rows in oat_by_controller.items():
        out[c] = []
        for r in rows:
            lv = {k: {"value": v["value"], "mean_delta_margin": v["mean_delta_margin"],
                      "majority_fails": v["majority_fails"]} for k, v in r.get("levels", {}).items()}
            out[c].append({"param": r["param"], "nominal_fails": r.get("nominal_fails", False),
                           "levels": lv, "flip_levels": r["flip_levels"]})
    return out


class LLMPolicy:
    """Asks a model to pick one action from VOCABULARY. Off by default; never used in CI.

    ``chat`` is any callable prompt -> text (see :func:`ollama_chat`). A reply that is not
    exactly one vocabulary item, or proposes an already-probed / flip-less direction, is
    rejected and the deterministic choice is used instead. Every prompt and reply is logged.
    """

    name = "llm"

    def __init__(self, chat: Callable[[str], str]):
        self.chat = chat
        self.fallback = DeterministicPolicy()
        self.log: list[dict] = []

    def prompt(self, oat_by_controller: dict[str, list[dict]], probed: set[str], context: dict | None = None) -> str:
        ctx = context or {}
        return (
            "You steer a simulation test campaign for a freeway ramp-metering controller.\n"
            "Goal: locate pass/fail boundaries. A probe bisects one parameter between its nominal value and\n"
            "one end of its range (lo or hi), for every controller whose majority verdict flips at that end.\n"
            "One-at-a-time results (paired seeds; mean_delta_margin < 0 means the move hurts):\n"
            f"{json.dumps(oat_table(oat_by_controller), sort_keys=True)}\n"
            f"Already probed: {sorted(probed)}\n"
            f"Simulation runs used so far: {ctx.get('runs_used', '?')} of a budget of {ctx.get('budget', '?')}; "
            f"a probe costs about {ctx.get('probe_cost', '?')} runs.\n"
            "Choose the single next action. Reply with JSON {\"action\": <one of>} where <one of> is\n"
            f"{json.dumps(list(VOCABULARY))}.\n"
            "Only a direction listed in that parameter's flip_levels (for some controller) can be probed."
        )

    def choose(self, oat_by_controller: dict[str, list[dict]], probed: set[str],
               context: dict | None = None) -> tuple[str, str]:
        prompt = self.prompt(oat_by_controller, probed, context)
        t0 = time.perf_counter()
        try:
            text = self.chat(prompt)
            error = None
        except Exception as e:  # network / model failure counts as an invalid output
            text, error = "", f"{type(e).__name__}: {e}"
        latency = round(time.perf_counter() - t0, 2)
        action, why_bad = parse_action(text)
        allowed = set(candidates(oat_by_controller, probed)) | {"stop"}
        if action is not None and action not in allowed:
            why_bad = "not_allowed_now"
        entry = {"prompt": prompt, "response": text, "parsed": action, "latency_s": latency,
                 "error": error, "allowed": sorted(allowed)}
        det, _ = self.fallback.choose(oat_by_controller, probed)
        entry["deterministic_choice"] = det
        if why_bad is not None or error is not None:
            entry.update(accepted=False, rejection=why_bad or "error", used=det)
            self.log.append(entry)
            return det, f"LLM reply rejected ({why_bad or 'error'}: {action!r}); deterministic fallback"
        entry.update(accepted=True, rejection=None, used=action)
        self.log.append(entry)
        return action, "chosen by LLM from the closed vocabulary"


def parse_action(text: str) -> tuple[str | None, str | None]:
    """(action, None) if the reply holds a JSON object whose "action" is in VOCABULARY,
    else (None or the raw action, reason)."""
    m = re.search(r"\{.*?\}", text or "", re.DOTALL)
    if not m:
        return None, "no_json"
    try:
        a = json.loads(m.group(0)).get("action")
    except (json.JSONDecodeError, AttributeError):
        return None, "bad_json"
    if a not in VOCABULARY:
        return None, "not_in_vocabulary"
    return a, None


def ollama_chat(model: str = "qwen2.5:3b", host: str = "http://127.0.0.1:11434", temperature: float = 0.0,
                seed: int = 0, num_gpu: int = 0, timeout: float = 600.0) -> Callable[[str], str]:  # pragma: no cover
    """Adapter over a local Ollama server (no extra dependency). ``num_gpu=0`` keeps the model
    on the CPU. The reply format is not constrained (no JSON mode), so format errors count."""

    def chat(prompt: str) -> str:
        body = json.dumps({
            "model": model, "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"num_gpu": num_gpu, "temperature": temperature, "seed": seed},
        }).encode()
        req = urllib.request.Request(f"{host}/api/chat", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["message"]["content"]

    return chat
