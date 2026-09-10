"""Mouse group — pointer query, move, click, drag, scroll."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from desk_proxy.api import input as input_api

from .base import action_def

ButtonName = Literal["left", "right", "middle"]
ScrollDir = Literal["up", "down", "left", "right"]


class MouseMovePayload(BaseModel):
    """Absolute pointer destination."""

    x: int = Field(..., description="Target X in pixels")
    y: int = Field(..., description="Target Y in pixels")


class MouseClickPayload(BaseModel):
    """Click at absolute coordinates."""

    x: int = Field(..., description="Click X")
    y: int = Field(..., description="Click Y")
    button: ButtonName = Field("left", description="left | right | middle")
    clicks: int = Field(1, description="Click count (>= 1; 2 = double-click)", ge=1)


class MouseDragPayload(BaseModel):
    """Drag from (x1,y1) to (x2,y2)."""

    x1: int = Field(..., description="Start X")
    y1: int = Field(..., description="Start Y")
    x2: int = Field(..., description="End X")
    y2: int = Field(..., description="End Y")
    button: ButtonName = Field("left", description="Button held during drag")
    duration_ms: int = Field(300, description="Approximate drag duration in ms", ge=1)


class MouseScrollPayload(BaseModel):
    """Scroll at coordinates."""

    x: int = Field(..., description="Pointer X before scrolling")
    y: int = Field(..., description="Pointer Y before scrolling")
    direction: ScrollDir = Field("down", description="up | down | left | right")
    clicks: int = Field(3, description="Number of scroll ticks", ge=1)


def mouse_get(_payload: Any = None) -> dict[str, Any]:
    """Return the current pointer position.

    Parameters:
        - (none): Payload may be null or ``{}``.

    Examples:
        - Read pointer:
            `desk-proxy do mouse-get '{}'`
            → {"x": 960, "y": 540}

        - Empty payload:
            `desk-proxy do mouse-get`
            → {"x": 12, "y": 34}

        - After a move:
            `desk-proxy do mouse-get '{}'`
            → {"x": 100, "y": 200}
    """
    return input_api.get_mouse()


def mouse_move(p: MouseMovePayload) -> dict[str, Any]:
    """Move the pointer to absolute coordinates.

    Parameters:
        - x (int): Target X in pixels.
        - y (int): Target Y in pixels.

    Examples:
        - Move to center-ish:
            `desk-proxy do mouse-move '{"x":960,"y":540}'`
            → {"x": 960, "y": 540}

        - Origin:
            `desk-proxy do mouse-move '{"x":0,"y":0}'`
            → {"x": 0, "y": 0}

        - Button corner:
            `desk-proxy do mouse-move '{"x":100,"y":200}'`
            → {"x": 100, "y": 200}
    """
    return input_api.move_mouse(p.x, p.y)


def mouse_click(p: MouseClickPayload) -> dict[str, Any]:
    """Move to ``(x, y)`` and click.

    Parameters:
        - x (int): Click X.
        - y (int): Click Y.
        - button (str): ``left`` | ``right`` | ``middle`` (default left).
        - clicks (int): Repeat count (default 1; use 2 for double-click).

    Examples:
        - Left click:
            `desk-proxy do mouse-click '{"x":100,"y":200}'`
            → {"x": 100, "y": 200, "button": "left", "clicks": 1}

        - Double-click:
            `desk-proxy do mouse-click '{"x":100,"y":200,"clicks":2}'`
            → {"x": 100, "y": 200, "button": "left", "clicks": 2}

        - Right-click:
            `desk-proxy do mouse-click '{"x":50,"y":50,"button":"right"}'`
            → {"x": 50, "y": 50, "button": "right", "clicks": 1}
    """
    return input_api.click(p.x, p.y, button=p.button, clicks=p.clicks)


def mouse_drag(p: MouseDragPayload) -> dict[str, Any]:
    """Drag from ``(x1,y1)`` to ``(x2,y2)`` with a button held.

    Parameters:
        - x1 (int): Start X.
        - y1 (int): Start Y.
        - x2 (int): End X.
        - y2 (int): End Y.
        - button (str): Button held (default left).
        - duration_ms (int): Approximate drag duration in milliseconds.

    Examples:
        - Short drag:
            `desk-proxy do mouse-drag '{"x1":10,"y1":10,"x2":100,"y2":100}'`
            → {"x1": 10, "y1": 10, "x2": 100, "y2": 100, "button": "left", "duration_ms": 300}

        - Fast drag:
            `desk-proxy do mouse-drag '{"x1":0,"y1":0,"x2":50,"y2":50,"duration_ms":50}'`
            → {"x1": 0, "y1": 0, "x2": 50, "y2": 50, "button": "left", "duration_ms": 50}

        - Middle-button drag:
            `desk-proxy do mouse-drag '{"x1":20,"y1":20,"x2":80,"y2":80,"button":"middle"}'`
            → {"x1": 20, "y1": 20, "x2": 80, "y2": 80, "button": "middle", "duration_ms": 300}
    """
    return input_api.drag(
        p.x1, p.y1, p.x2, p.y2, button=p.button, duration_ms=p.duration_ms
    )


def mouse_scroll(p: MouseScrollPayload) -> dict[str, Any]:
    """Scroll at coordinates.

    Parameters:
        - x (int): Pointer X before scrolling.
        - y (int): Pointer Y before scrolling.
        - direction (str): ``up`` | ``down`` | ``left`` | ``right`` (default down).
        - clicks (int): Number of scroll ticks (default 3).

    Examples:
        - Scroll down:
            `desk-proxy do mouse-scroll '{"x":500,"y":500}'`
            → {"x": 500, "y": 500, "direction": "down", "clicks": 3}

        - Scroll up twice:
            `desk-proxy do mouse-scroll '{"x":500,"y":500,"direction":"up","clicks":2}'`
            → {"x": 500, "y": 500, "direction": "up", "clicks": 2}

        - Horizontal:
            `desk-proxy do mouse-scroll '{"x":100,"y":100,"direction":"right","clicks":1}'`
            → {"x": 100, "y": 100, "direction": "right", "clicks": 1}
    """
    return input_api.scroll(p.x, p.y, direction=p.direction, clicks=p.clicks)


ACTIONS = [
    action_def("mouse-get", None, mouse_get, group="Mouse"),
    action_def("mouse-move", MouseMovePayload, mouse_move, group="Mouse"),
    action_def("mouse-click", MouseClickPayload, mouse_click, group="Mouse"),
    action_def("mouse-drag", MouseDragPayload, mouse_drag, group="Mouse"),
    action_def("mouse-scroll", MouseScrollPayload, mouse_scroll, group="Mouse"),
]
