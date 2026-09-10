"""
Admin logic for desk-proxy — doctor, status, setup, purge.

All functions return plain dicts; the CLI wraps them in the ADN envelope.
No remote credentials: only local tool presence and config hygiene.
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from desk_proxy.api.screen import screen_info
from desk_proxy.config import (
    CONFIG_DIR,
    CONFIG_PATH,
    default_config,
    display_env,
    ensure_config_dir,
    load_config,
    save_config,
)


def _tool(name: str) -> bool:
    """Return True when ``name`` is on PATH.

    Args:
        name (str): Binary name, e.g. ``xdotool``.

    Returns:
        bool: Whether ``shutil.which`` finds the binary.

    Examples:
        >>> isinstance(_tool("true"), bool)
        True
        >>> _tool("definitely-missing-desk-proxy-bin-zzzz")
        False
    """
    return bool(shutil.which(name))


def doctor() -> dict[str, Any]:
    """Probe desktop tools and config layout; report actionable issues.

    Checks: xdotool, ydotool, wtype, wmctrl, tesseract, grim,
    gnome-screenshot, system python3 (portal), wl-copy/wl-paste, config dir.

    Returns:
        dict[str, Any]: ``ok``, ``issues``, ``tools``, ``config``, ``display``.

    Examples:
        >>> d = doctor()
        >>> "ok" in d and "tools" in d and "issues" in d
        True
        >>> isinstance(d["tools"]["xdotool"], bool)
        True
        >>> "config_dir" in d["config"]
        True
    """
    tools = {
        "xdotool": _tool("xdotool"),
        "ydotool": _tool("ydotool"),
        "wtype": _tool("wtype"),
        "wmctrl": _tool("wmctrl"),
        "tesseract": _tool("tesseract"),
        "grim": _tool("grim"),
        "gnome_screenshot": _tool("gnome-screenshot"),
        "portal_python3": os.path.isfile("/usr/bin/python3"),
        "wl_copy": _tool("wl-copy"),
        "wl_paste": _tool("wl-paste"),
        "xclip": _tool("xclip"),
        "ffmpeg": _tool("ffmpeg"),
    }
    config = {
        "config_dir": str(CONFIG_DIR),
        "config_dir_exists": CONFIG_DIR.is_dir(),
        "config_json": str(CONFIG_PATH),
        "config_json_exists": CONFIG_PATH.is_file(),
    }
    issues: list[str] = []
    if not tools["xdotool"] and not tools["ydotool"]:
        issues.append(
            "No input backend: install xdotool (X11/XWayland) or ydotool+ydotoold"
        )
    if not (
        tools["grim"]
        or tools["gnome_screenshot"]
        or tools["portal_python3"]
        or tools["ffmpeg"]
    ):
        issues.append(
            "No screenshot backend: install gnome-screenshot, grim, ffmpeg, "
            "or python3-dbus+python3-gi for the portal"
        )
    if not tools["tesseract"]:
        issues.append(
            "tesseract missing — OCR actions will fail "
            "(sudo apt install tesseract-ocr tesseract-ocr-eng)"
        )
    if not ((tools["wl_copy"] and tools["wl_paste"]) or tools["xclip"]):
        issues.append("No clipboard backend: install wl-clipboard or xclip")
    if not config["config_dir_exists"]:
        issues.append(
            f"Config dir missing: {CONFIG_DIR} — run `desk-proxy admin setup`"
        )

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "tools": tools,
        "config": config,
        "display": display_env(),
    }


def status() -> dict[str, Any]:
    """Return screen_info + effective config + tool availability.

    Returns:
        dict[str, Any]: Combined operational snapshot for operators/agents.

    Examples:
        >>> s = status()
        >>> "screen" in s and "config" in s and "tools" in s
        True
        >>> s["config"]["input_backend"] in ("auto", "xdotool", "ydotool")
        True
        >>> isinstance(s["screen"]["width"], int)
        True
    """
    d = doctor()
    return {
        "screen": screen_info(),
        "config": load_config(),
        "tools": d["tools"],
        "ok": d["ok"],
        "issues": d["issues"],
        "display": d["display"],
    }


def setup() -> dict[str, Any]:
    """Ensure config dir, write default ``config.json``, grant Screenshot portal.

    Returns:
        dict[str, Any]: Paths written, default settings, and portal permission
        grant result.

    Examples:
        >>> r = setup()
        >>> r["config"].endswith("config.json")
        True
        >>> r["settings"]["input_backend"]
        'auto'
        >>> "desk-proxy" in r["config_dir"]
        True
    """
    from desk_proxy.api.screenshot import ensure_screenshot_permission

    ensure_config_dir()
    path = save_config(default_config())
    portal = ensure_screenshot_permission()
    return {
        "config_dir": str(CONFIG_DIR),
        "config": str(path),
        "settings": default_config(),
        "screenshot_portal": portal,
    }


def purge() -> dict[str, Any]:
    """Remove config-dir contents (not ``/tmp`` shot or autosave dirs).

    Returns:
        dict[str, Any]: List of removed paths and the config directory.

    Examples:
        >>> # After setup, purge clears ~/.config/desk-proxy/*
        >>> r = purge()
        >>> "removed" in r and "config_dir" in r
        True
        >>> isinstance(r["removed"], list)
        True
        >>> str(r["config_dir"]).endswith("desk-proxy")
        True
    """
    removed: list[str] = []
    if CONFIG_DIR.is_dir():
        for item in sorted(CONFIG_DIR.iterdir()):
            target = str(item)
            if item.is_symlink() or item.is_file():
                item.unlink(missing_ok=True)
                removed.append(target)
            elif item.is_dir():
                shutil.rmtree(item)
                removed.append(target)
    return {"removed": removed, "config_dir": str(CONFIG_DIR)}
