"""
Screen / session introspection for desk-proxy.
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from desk_proxy.api.run import run_cmd


def screen_info() -> dict[str, Any]:
    """Return display geometry, session type, and available backend flags.

    Returns:
        dict[str, Any]: Keys ``width``, ``height``, ``session_type``, ``display``,
        ``wayland_display``, plus boolean flags for portal/gnome/grim/xdotool/
        ydotool/wtype/wmctrl/tesseract/wl-clipboard/xclip.

    Examples:
        >>> info = screen_info()
        >>> info["width"] >= 0 and info["height"] >= 0
        True
        >>> "session_type" in info and "xdotool" in info
        True
    """
    width, height = 0, 0
    if shutil.which("xdotool"):
        r = run_cmd(["xdotool", "getdisplaygeometry"], timeout=5)
        if r.returncode == 0:
            parts = (r.stdout or "").strip().split()
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                width, height = int(parts[0]), int(parts[1])

    return {
        "width": width,
        "height": height,
        "session_type": os.environ.get("XDG_SESSION_TYPE", "unknown"),
        "display": os.environ.get("DISPLAY", ""),
        "wayland_display": os.environ.get("WAYLAND_DISPLAY", ""),
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
    }
