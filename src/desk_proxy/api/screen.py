"""
Screen / session introspection for desk-proxy.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Any

from desk_proxy.api.atspi_script import GNOME_SCREEN_SIZE_SCRIPT
from desk_proxy.api.run import run_cmd
from desk_proxy.config import display_env


def screen_info() -> dict[str, Any]:
    """Return display geometry, session type, and available backend flags.

    Geometry preference: GNOME Introspect ``ScreenSize`` (logical desktop
    spanning monitors) → xdotool. Session env comes from ``display_env()``
    so stripped agent shells still report the real GUI session.

    Returns:
        dict[str, Any]: Keys ``width``, ``height``, ``session_type``, ``display``,
        ``wayland_display``, ``geometry_backend``, plus boolean flags for
        portal/gnome/grim/xdotool/ydotool/wtype/wmctrl/tesseract/clipboard.

    Examples:
        >>> info = screen_info()
        >>> info["width"] >= 0 and info["height"] >= 0
        True
        >>> "session_type" in info and "xdotool" in info
        True
    """
    denv = display_env()
    width, height = 0, 0
    geometry_backend = "none"

    gr = run_cmd(["/usr/bin/python3", "-c", GNOME_SCREEN_SIZE_SCRIPT], timeout=5)
    try:
        gpayload = json.loads((gr.stdout or "").strip() or "{}")
        if gpayload.get("ok"):
            width, height = int(gpayload["width"]), int(gpayload["height"])
            geometry_backend = "gnome-introspect"
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass

    if (width <= 0 or height <= 0) and shutil.which("xdotool"):
        r = run_cmd(["xdotool", "getdisplaygeometry"], timeout=5)
        if r.returncode == 0:
            parts = (r.stdout or "").strip().split()
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                width, height = int(parts[0]), int(parts[1])
                geometry_backend = "xdotool"

    # Prefer Wayland when display_env injected it — agent shells often keep XDG_SESSION_TYPE=tty
    if denv.get("WAYLAND_DISPLAY"):
        session_type = "wayland"
    else:
        session_type = os.environ.get("XDG_SESSION_TYPE") or "x11"

    return {
        "width": width,
        "height": height,
        "geometry_backend": geometry_backend,
        "session_type": session_type,
        "display": denv.get("DISPLAY", ""),
        "wayland_display": denv.get("WAYLAND_DISPLAY", ""),
        "xauthority": denv.get("XAUTHORITY", ""),
        "portal": os.path.isfile("/usr/bin/python3"),
        "gnome_screenshot": bool(shutil.which("gnome-screenshot")),
        "grim": bool(shutil.which("grim")),
        "xdotool": bool(shutil.which("xdotool")),
        "ydotool": bool(shutil.which("ydotool")),
        "wtype": bool(shutil.which("wtype")),
        "wmctrl": bool(shutil.which("wmctrl")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "tesseract": bool(shutil.which("tesseract")),
        "wl_clipboard": bool(shutil.which("wl-copy") and shutil.which("wl-paste")),
        "xclip": bool(shutil.which("xclip")),
        "atspi": os.path.isfile("/usr/bin/python3"),
    }
