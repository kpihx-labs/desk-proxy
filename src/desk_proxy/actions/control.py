"""Control group — wait, action chains, and raw backend escape hatch."""

from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from desk_proxy.api.run import run_cmd
from desk_proxy.exceptions import DeskProxyError

from .base import action_def, require_approval

RawBackend = Literal["xdotool", "ydotool", "wmctrl", "shell"]


class WaitPayload(BaseModel):
    """Sleep for a fixed duration."""

    seconds: float = Field(..., description="Seconds to sleep (>= 0)", ge=0)


class ChainStep(BaseModel):
    """One step inside a ``chain`` action."""

    action: str = Field(..., description="Registered kebab-case action name")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="JSON payload for that action"
    )


class ChainPayload(BaseModel):
    """Sequential execution of registered desk-proxy actions."""

    steps: list[ChainStep] = Field(..., description="Ordered list of {action, payload}")


class RawPayload(BaseModel):
    """Escape hatch — run a desktop backend with explicit argv."""

    backend: RawBackend = Field(..., description="xdotool | ydotool | wmctrl | shell")
    args: list[str] = Field(..., description="Arguments (or full argv for shell)")


def wait(p: WaitPayload) -> dict[str, Any]:
    """Sleep for ``seconds`` then return the duration slept.

    Parameters:
        - seconds (float): Duration in seconds (>= 0).

    Examples:
        - Short pause:
            `desk-proxy do wait '{"seconds":0.5}'`
            → {"slept": 0.5}

        - One second:
            `desk-proxy do wait '{"seconds":1}'`
            → {"slept": 1.0}

        - Zero (no-op):
            `desk-proxy do wait '{"seconds":0}'`
            → {"slept": 0.0}
    """
    time.sleep(float(p.seconds))
    return {"slept": float(p.seconds)}


@require_approval()
def chain(p: ChainPayload) -> dict[str, Any]:
    """Execute registered actions sequentially. HITL required for the whole chain.

    Unknown action names are rejected. Nested HITL is not re-prompted — the
    outer chain approval covers every step. Each step receives a validated
    payload model when the action declares one.

    Parameters:
        - steps (list): Ordered ``{action, payload}`` objects.

    Examples:
        - Info then mouse:
            `desk-proxy do chain '{"steps":[{"action":"screen-info","payload":{}},{"action":"mouse-get","payload":{}}]}'`
            → {"results": [{"action": "screen-info", "data": {"width": 1920}}, {"action": "mouse-get", "data": {"x": 10, "y": 20}}]}

        - Wait then shot:
            `desk-proxy do chain '{"steps":[{"action":"wait","payload":{"seconds":0.1}},{"action":"screen-shot","payload":{}}]}'`
            → {"results": [{"action": "wait", "data": {"slept": 0.1}}, {"action": "screen-shot", "data": {"path": "/tmp/desk-proxy-shots/full_1.png"}}]}

        - Unknown action fails:
            `desk-proxy do chain '{"steps":[{"action":"nope","payload":{}}]}'`
            → {"meta": {"status": "error"}, "data": null}
    """
    # Lazy import avoids circular registry ↔ control dependency.
    from desk_proxy.actions.registry import REGISTRY

    if not p.steps:
        raise DeskProxyError("chain requires at least one step")

    results: list[dict[str, Any]] = []
    for step in p.steps:
        action = REGISTRY.get(step.action)
        if action is None:
            raise DeskProxyError(f"Unknown action in chain: {step.action}")
        raw = step.payload if isinstance(step.payload, dict) else {}
        if action.payload is not None:
            validated: Any = action.payload(**raw)
        else:
            validated = raw
        data = action.handler(validated)
        results.append({"action": step.action, "data": data})
    return {"results": results}


@require_approval()
def raw(p: RawPayload) -> dict[str, Any]:
    """Run a desktop backend with explicit args. HITL required.

    For ``xdotool`` / ``ydotool`` / ``wmctrl`` the binary is prepended.
    For ``shell`` the ``args`` list is the full argv (no shell expansion).

    Parameters:
        - backend (str): ``xdotool`` | ``ydotool`` | ``wmctrl`` | ``shell``.
        - args (list[str]): Arguments after the backend binary (or full argv).

    Examples:
        - Display geometry via xdotool:
            `desk-proxy do raw '{"backend":"xdotool","args":["getdisplaygeometry"]}'`
            → {"backend": "xdotool", "argv": ["xdotool", "getdisplaygeometry"], "returncode": 0, "stdout": "1920 1080", "stderr": ""}

        - List windows via wmctrl:
            `desk-proxy do raw '{"backend":"wmctrl","args":["-l"]}'`
            → {"backend": "wmctrl", "argv": ["wmctrl", "-l"], "returncode": 0, "stdout": "0x01a00007  0 host Terminal", "stderr": ""}

        - Shell argv (no expansion):
            `desk-proxy do raw '{"backend":"shell","args":["true"]}'`
            → {"backend": "shell", "argv": ["true"], "returncode": 0, "stdout": "", "stderr": ""}
    """
    if p.backend == "shell":
        if not p.args:
            raise DeskProxyError("raw shell backend requires a non-empty args list")
        argv = list(p.args)
    else:
        argv = [p.backend, *p.args]
    result = run_cmd(argv, timeout=30)
    return {
        "backend": p.backend,
        "argv": argv,
        "returncode": result.returncode,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
    }


ACTIONS = [
    action_def("wait", WaitPayload, wait, group="Control"),
    action_def("chain", ChainPayload, chain, group="Control"),
    action_def("raw", RawPayload, raw, group="Control"),
]
