"""Windows group — list, resolve, focus, move, resize, minimize, close."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from desk_proxy.api import windows as win_api
from desk_proxy.exceptions import DeskProxyError

from .base import action_def, require_approval


class WindowRefPayload(BaseModel):
    """Select a window by numeric id or partial name/class."""

    name: str | None = Field(None, description="Partial window title or WM_CLASS")
    id: int | None = Field(None, description="X window id")

    @model_validator(mode="after")
    def _require_one(self) -> WindowRefPayload:
        if self.id is None and not (self.name and str(self.name).strip()):
            raise ValueError("Provide name or id")
        return self


class WindowMovePayload(WindowRefPayload):
    """Move a window to absolute screen coordinates."""

    x: int = Field(..., description="Destination X in pixels")
    y: int = Field(..., description="Destination Y in pixels")


class WindowResizePayload(WindowRefPayload):
    """Resize a window to width × height."""

    width: int = Field(..., description="New width in pixels", ge=1)
    height: int = Field(..., description="New height in pixels", ge=1)


def _ref(p: WindowRefPayload) -> str | int:
    """Resolve name/id payload to the API selector.

    Args:
        p (WindowRefPayload): Validated window reference.

    Returns:
        str | int: Numeric id when set, otherwise the name string.

    Examples:
        >>> _ref(WindowRefPayload(id=42))
        42
        >>> _ref(WindowRefPayload(name="Firefox"))
        'Firefox'
    """
    if p.id is not None:
        return p.id
    if p.name and str(p.name).strip():
        return str(p.name).strip()
    raise DeskProxyError("Provide name or id")


def window_list(_payload: Any = None) -> dict[str, Any]:
    """List visible windows with geometry (AT-SPI on Wayland, else X11).

    Parameters:
        - (none): Payload may be null or ``{}``.

    Examples:
        - List everything visible:
            `desk-proxy do window-list '{}'`
            → {"windows": [{"id": 12345678, "name": "Terminal", "app": "org.gnome.Terminal", "x": 10, "y": 40, "width": 900, "height": 600, "backend": "atspi"}]}

        - Empty desktop:
            `desk-proxy do window-list`
            → {"windows": []}

        - Multiple clients:
            `desk-proxy do window-list '{}'`
            → {"windows": [{"id": 1, "name": "Edge", "app": "Microsoft Edge", "x": 0, "y": 0, "width": 1920, "height": 1080, "backend": "atspi"}, {"id": 2, "name": "Bitwarden", "app": "bitwarden-app", "x": 5, "y": 134, "width": 950, "height": 790, "backend": "atspi"}]}
    """
    return {"windows": win_api.list_windows()}


def window_get(p: WindowRefPayload) -> dict[str, Any]:
    """Resolve one window by id or partial name/class.

    Parameters:
        - name (str|null): Partial title / WM_CLASS substring.
        - id (int|null): Absolute X window id.

    Examples:
        - By name:
            `desk-proxy do window-get '{"name":"Firefox"}'`
            → {"id": 8388614, "name": "Mozilla Firefox", "x": 120, "y": 80, "width": 1280, "height": 800}

        - By id:
            `desk-proxy do window-get '{"id":8388614}'`
            → {"id": 8388614, "name": "Mozilla Firefox", "x": 120, "y": 80, "width": 1280, "height": 800}

        - Missing window:
            `desk-proxy do window-get '{"name":"no-such-window-zzz"}'`
            → {"window": null}
    """
    win = win_api.get_window(_ref(p))
    return win if win is not None else {"window": None}


def window_focus(p: WindowRefPayload) -> dict[str, Any]:
    """Activate (raise + focus) a window.

    Parameters:
        - name (str|null): Partial title / WM_CLASS substring.
        - id (int|null): Absolute X window id.

    Examples:
        - Focus by name:
            `desk-proxy do window-focus '{"name":"Terminal"}'`
            → {"id": 12345678, "name": "Terminal", "x": 10, "y": 40, "width": 900, "height": 600}

        - Focus by id:
            `desk-proxy do window-focus '{"id":12345678}'`
            → {"id": 12345678, "name": "Terminal", "x": 10, "y": 40, "width": 900, "height": 600}

        - Unknown target fails:
            `desk-proxy do window-focus '{"name":"missing-xyz"}'`
            → {"meta": {"status": "error"}, "data": null}
    """
    return win_api.focus_window(_ref(p))


def window_activate(p: WindowRefPayload) -> dict[str, Any]:
    """Alias of ``window-focus`` — activate a window.

    Parameters:
        - name (str|null): Partial title / WM_CLASS substring.
        - id (int|null): Absolute X window id.

    Examples:
        - Activate by name:
            `desk-proxy do window-activate '{"name":"Cursor"}'`
            → {"id": 999, "name": "Cursor", "x": 0, "y": 0, "width": 1920, "height": 1080}

        - Activate by id:
            `desk-proxy do window-activate '{"id":999}'`
            → {"id": 999, "name": "Cursor", "x": 0, "y": 0, "width": 1920, "height": 1080}

        - Same result as window-focus:
            `desk-proxy do window-activate '{"name":"Firefox"}'`
            → {"id": 8388614, "name": "Mozilla Firefox", "x": 120, "y": 80, "width": 1280, "height": 800}
    """
    return win_api.focus_window(_ref(p))


@require_approval()
def window_close(p: WindowRefPayload) -> dict[str, Any]:
    """Close a window (wmctrl preferred, else xdotool). HITL required.

    Parameters:
        - name (str|null): Partial title / WM_CLASS substring.
        - id (int|null): Absolute X window id.

    Examples:
        - Close by name:
            `desk-proxy do window-close '{"name":"Untitled Document"}'`
            → {"id": 555, "name": "Untitled Document", "x": 200, "y": 200, "width": 640, "height": 480}

        - Close by id:
            `desk-proxy do window-close '{"id":555}'`
            → {"id": 555, "name": "Untitled Document", "x": 200, "y": 200, "width": 640, "height": 480}

        - HITL rejection:
            `desk-proxy do window-close '{"name":"Firefox"}'`
            → {"meta": {"status": "rejected", "comment": "not now"}, "data": null}
    """
    return win_api.close_window(_ref(p))


def window_move(p: WindowMovePayload) -> dict[str, Any]:
    """Move a window to absolute ``(x, y)`` screen coordinates.

    Parameters:
        - name (str|null): Partial title / WM_CLASS substring.
        - id (int|null): Absolute X window id.
        - x (int): Destination X in pixels.
        - y (int): Destination Y in pixels.

    Examples:
        - Move by name:
            `desk-proxy do window-move '{"name":"Terminal","x":50,"y":50}'`
            → {"id": 12345678, "name": "Terminal", "x": 50, "y": 50, "width": 900, "height": 600}

        - Move by id:
            `desk-proxy do window-move '{"id":12345678,"x":0,"y":0}'`
            → {"id": 12345678, "name": "Terminal", "x": 0, "y": 0, "width": 900, "height": 600}

        - Corner snap:
            `desk-proxy do window-move '{"name":"Firefox","x":100,"y":80}'`
            → {"id": 8388614, "name": "Mozilla Firefox", "x": 100, "y": 80, "width": 1280, "height": 800}
    """
    return win_api.move_window(_ref(p), p.x, p.y)


def window_resize(p: WindowResizePayload) -> dict[str, Any]:
    """Resize a window to ``width`` × ``height`` pixels.

    Parameters:
        - name (str|null): Partial title / WM_CLASS substring.
        - id (int|null): Absolute X window id.
        - width (int): New width (>= 1).
        - height (int): New height (>= 1).

    Examples:
        - Resize by name:
            `desk-proxy do window-resize '{"name":"Terminal","width":800,"height":600}'`
            → {"id": 12345678, "name": "Terminal", "x": 10, "y": 40, "width": 800, "height": 600}

        - Resize by id:
            `desk-proxy do window-resize '{"id":12345678,"width":640,"height":480}'`
            → {"id": 12345678, "name": "Terminal", "x": 10, "y": 40, "width": 640, "height": 480}

        - Half-screen width:
            `desk-proxy do window-resize '{"name":"Firefox","width":960,"height":1080}'`
            → {"id": 8388614, "name": "Mozilla Firefox", "x": 0, "y": 0, "width": 960, "height": 1080}
    """
    return win_api.resize_window(_ref(p), p.width, p.height)


def window_minimize(p: WindowRefPayload) -> dict[str, Any]:
    """Minimize (iconify) a window.

    Parameters:
        - name (str|null): Partial title / WM_CLASS substring.
        - id (int|null): Absolute X window id.

    Examples:
        - Minimize by name:
            `desk-proxy do window-minimize '{"name":"Calculator"}'`
            → {"id": 777, "name": "Calculator", "x": 400, "y": 300, "width": 320, "height": 240}

        - Minimize by id:
            `desk-proxy do window-minimize '{"id":777}'`
            → {"id": 777, "name": "Calculator", "x": 400, "y": 300, "width": 320, "height": 240}

        - Unknown target fails:
            `desk-proxy do window-minimize '{"name":"nope"}'`
            → {"meta": {"status": "error"}, "data": null}
    """
    return win_api.minimize_window(_ref(p))


ACTIONS = [
    action_def("window-list", None, window_list, group="Windows"),
    action_def("window-get", WindowRefPayload, window_get, group="Windows"),
    action_def("window-focus", WindowRefPayload, window_focus, group="Windows"),
    action_def("window-activate", WindowRefPayload, window_activate, group="Windows"),
    action_def("window-close", WindowRefPayload, window_close, group="Windows"),
    action_def("window-move", WindowMovePayload, window_move, group="Windows"),
    action_def("window-resize", WindowResizePayload, window_resize, group="Windows"),
    action_def("window-minimize", WindowRefPayload, window_minimize, group="Windows"),
]
