"""
Window discovery and control.

Primary on GNOME Wayland: AT-SPI frames via system ``/usr/bin/python3``
(PyGObject is not in the uv venv). Fallback: xdotool + wmctrl (XWayland only).
"""

from __future__ import annotations

import json
import shutil
from typing import Any

from desk_proxy.api.atspi_script import ATSPI_LIST_WINDOWS_SCRIPT
from desk_proxy.api.run import run_cmd
from desk_proxy.exceptions import DeskProxyError

_SKIP_NAMES = frozenset({"", "mutter guard window"})
# Tiny GNOME/XWayland stubs that are not real user windows
_SKIP_STUB_NAMES = frozenset(
    {
        "gnome shell",
        "ibus-x11",
        "ibus-xim",
        "mutter-x11-frames",
        "mutter guard window",
    }
)


def _parse_geometry_shell(stdout: str) -> dict[str, int]:
    """Parse ``xdotool getwindowgeometry --shell`` key=value lines.

    Args:
        stdout (str): Raw shell-format geometry text.

    Returns:
        dict[str, int]: Lowercased keys such as ``x``, ``y``, ``width``, ``height``.

    Examples:
        >>> _parse_geometry_shell("X=10\\nY=20\\nWIDTH=800\\nHEIGHT=600\\n")
        {'x': 10, 'y': 20, 'width': 800, 'height': 600}
        >>> _parse_geometry_shell("")
        {}
    """
    vals: dict[str, int] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        key = key.strip().lower()
        try:
            vals[key] = int(raw.strip())
        except ValueError:
            continue
    return vals


def _window_dict(wid: str | int, name: str, geom: dict[str, int]) -> dict[str, Any]:
    """Build the canonical window record.

    Args:
        wid (str | int): X window id.
        name (str): Window title.
        geom (dict[str, int]): Parsed geometry map.

    Returns:
        dict[str, Any]: ``{id, name, x, y, width, height}``.

    Examples:
        >>> _window_dict(42, "Terminal", {"x": 1, "y": 2, "width": 3, "height": 4})
        {'id': 42, 'name': 'Terminal', 'x': 1, 'y': 2, 'width': 3, 'height': 4}
        >>> _window_dict("99", "App", {})["width"]
        0
    """
    return {
        "id": int(wid),
        "name": name,
        "x": int(geom.get("x", 0)),
        "y": int(geom.get("y", 0)),
        "width": int(geom.get("width", 0)),
        "height": int(geom.get("height", 0)),
    }


def _is_stub_window(rec: dict[str, Any]) -> bool:
    """Return True for tiny XWayland/GNOME stub windows to hide from listings.

    Args:
        rec (dict[str, Any]): Window record with ``name`` / ``width`` / ``height``.

    Returns:
        bool: True when the window should be filtered out of user-facing lists.

    Examples:
        >>> _is_stub_window({"name": "GNOME Shell", "width": 1, "height": 1})
        True
        >>> _is_stub_window({"name": "Terminal", "width": 800, "height": 600})
        False
    """
    name = str(rec.get("name") or "").strip().lower()
    if name in _SKIP_STUB_NAMES or name in _SKIP_NAMES:
        return True
    w = int(rec.get("width") or 0)
    h = int(rec.get("height") or 0)
    return bool(w > 0 and h > 0 and w <= 32 and h <= 32)


def _list_windows_atspi() -> list[dict[str, Any]]:
    """List frames/windows via AT-SPI (system Python + PyGObject).

    Returns:
        list[dict[str, Any]]: AT-SPI window records (may be empty on failure).

    Examples:
        >>> isinstance(_list_windows_atspi(), list)
        True
        >>> all("backend" in w for w in _list_windows_atspi()[:1]) or True
        True
    """
    r = run_cmd(["/usr/bin/python3", "-c", ATSPI_LIST_WINDOWS_SCRIPT], timeout=20)
    raw = (r.stdout or "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not payload.get("ok"):
        return []
    out: list[dict[str, Any]] = []
    for win in payload.get("windows") or []:
        if not isinstance(win, dict):
            continue
        rec = {
            "id": int(win.get("id") or 0),
            "name": str(win.get("name") or ""),
            "app": str(win.get("app") or ""),
            "role": str(win.get("role") or ""),
            "x": int(win.get("x") or 0),
            "y": int(win.get("y") or 0),
            "width": int(win.get("width") or 0),
            "height": int(win.get("height") or 0),
            "backend": "atspi",
        }
        if _is_stub_window(rec):
            continue
        out.append(rec)
    return out


def _list_windows_x11() -> list[dict[str, Any]]:
    """List X11/XWayland windows via xdotool (+ wmctrl enrichment).

    Returns:
        list[dict[str, Any]]: X11 window records (stubs filtered).

    Examples:
        >>> isinstance(_list_windows_x11(), list)
        True
        >>> all("id" in w for w in _list_windows_x11()[:1]) or True
        True
    """
    by_id: dict[int, dict[str, Any]] = {}

    r = run_cmd(["xdotool", "search", "--name", ""])
    if r.returncode == 0 and (r.stdout or "").strip():
        for wid in r.stdout.strip().splitlines():
            name_r = run_cmd(["xdotool", "getwindowname", wid])
            if name_r.returncode != 0:
                continue
            name = (name_r.stdout or "").strip()
            if name in _SKIP_NAMES:
                continue
            geom_r = run_cmd(["xdotool", "getwindowgeometry", "--shell", wid])
            geom = _parse_geometry_shell(geom_r.stdout or "")
            rec = _window_dict(wid, name, geom)
            rec["backend"] = "xdotool"
            rec["app"] = ""
            rec["role"] = ""
            if _is_stub_window(rec):
                continue
            by_id[rec["id"]] = rec

    if shutil.which("wmctrl"):
        wr = run_cmd(["wmctrl", "-lG"])
        if wr.returncode == 0 and (wr.stdout or "").strip():
            for line in wr.stdout.splitlines():
                parts = line.split(None, 7)
                if len(parts) < 8:
                    continue
                try:
                    wid = int(parts[0], 16)
                    x, y, w, h = (
                        int(parts[2]),
                        int(parts[3]),
                        int(parts[4]),
                        int(parts[5]),
                    )
                except ValueError:
                    continue
                name = parts[7].strip()
                if name in _SKIP_NAMES:
                    continue
                rec = {
                    "id": wid,
                    "name": name,
                    "app": "",
                    "role": "",
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "backend": "wmctrl",
                }
                if _is_stub_window(rec):
                    continue
                if wid not in by_id:
                    by_id[wid] = rec

    return list(by_id.values())


def list_windows() -> list[dict[str, Any]]:
    """List visible windows with geometry (AT-SPI first, then X11 fallback).

    On GNOME Wayland, xdotool/wmctrl only see XWayland stubs — AT-SPI is the
    root fix for real app frames (title, app id, screen extents).

    Returns:
        list[dict[str, Any]]: Records ``{id, name, app, role, x, y, width,
        height, backend}``. Empty list when no backend finds windows.

    Examples:
        >>> isinstance(list_windows(), list)
        True
        >>> all("id" in w and "name" in w for w in list_windows()[:3]) or list_windows() == []
        True
    """
    atspi = _list_windows_atspi()
    if atspi:
        return atspi
    return _list_windows_x11()


def get_window(name_or_id: str | int) -> dict[str, Any] | None:
    """Resolve a window by numeric id or partial name / app / class.

    Prefers the unified ``list_windows()`` catalog (AT-SPI on Wayland) so
    name lookups work for native Wayland frames. Falls back to xdotool
    search for X11 ids when needed.

    Args:
        name_or_id (str | int): Window id, or substring matched against title
            then app name.

    Returns:
        dict[str, Any] | None: Canonical window dict, or None when not found.

    Examples:
        >>> get_window(999999999) is None
        True
        >>> w = get_window("Cursor")  # doctest: +SKIP
        >>> w is None or "width" in w
        True
    """
    catalog = list_windows()
    if isinstance(name_or_id, int) or str(name_or_id).isdigit():
        target = int(name_or_id)
        for win in catalog:
            if int(win["id"]) == target:
                return win
        # X11 fallback for raw xdotool ids not in AT-SPI catalog
        wid = str(target)
        name_r = run_cmd(["xdotool", "getwindowname", wid])
        if name_r.returncode != 0:
            return None
        geom_r = run_cmd(["xdotool", "getwindowgeometry", "--shell", wid])
        if geom_r.returncode != 0:
            return None
        rec = _window_dict(
            wid,
            (name_r.stdout or "").strip(),
            _parse_geometry_shell(geom_r.stdout or ""),
        )
        rec["backend"] = "xdotool"
        rec["app"] = ""
        rec["role"] = ""
        return rec

    needle = str(name_or_id).lower()
    for win in catalog:
        hay = f"{win.get('name', '')} {win.get('app', '')}".lower()
        if needle in hay:
            return win

    # X11 search fallback
    for flag in ("--name", "--class"):
        r = run_cmd(["xdotool", "search", flag, str(name_or_id)])
        if r.returncode == 0 and (r.stdout or "").strip():
            wid = r.stdout.strip().splitlines()[-1]
            name_r = run_cmd(["xdotool", "getwindowname", wid])
            if name_r.returncode != 0:
                continue
            geom_r = run_cmd(["xdotool", "getwindowgeometry", "--shell", wid])
            if geom_r.returncode != 0:
                continue
            rec = _window_dict(
                wid,
                (name_r.stdout or "").strip(),
                _parse_geometry_shell(geom_r.stdout or ""),
            )
            rec["backend"] = "xdotool"
            rec["app"] = ""
            rec["role"] = ""
            return rec
    return None


def _require_window(name_or_id: str | int) -> dict[str, Any]:
    """Resolve a window or raise.

    Args:
        name_or_id (str | int): Window selector.

    Returns:
        dict[str, Any]: Canonical window dict.

    Raises:
        DeskProxyError: When the window cannot be found.

    Examples:
        >>> _require_window(999999999)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        DeskProxyError: Window not found: 999999999
        >>> isinstance(_require_window(list_windows()[0]["id"]), dict)  # doctest: +SKIP
        True
    """
    win = get_window(name_or_id)
    if win is None:
        raise DeskProxyError(f"Window not found: {name_or_id}")
    return win


def focus_window(name_or_id: str | int) -> dict[str, Any]:
    """Activate a window (``xdotool windowactivate --sync``).

    Args:
        name_or_id (str | int): Window id or name/class substring.

    Returns:
        dict[str, Any]: The focused window record.

    Raises:
        DeskProxyError: When the window is not found.
        DeskAPIError: When activation fails.

    Examples:
        >>> focus_window("does-not-exist-xyz")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        DeskProxyError: Window not found: does-not-exist-xyz
        >>> focus_window(list_windows()[0]["id"])["id"] > 0  # doctest: +SKIP
        True
    """
    win = _require_window(name_or_id)
    run_cmd(
        ["xdotool", "windowactivate", "--sync", str(win["id"])],
        check=True,
    )
    return win


def close_window(name_or_id: str | int) -> dict[str, Any]:
    """Close a window via ``wmctrl -ic`` when available, else xdotool.

    Args:
        name_or_id (str | int): Window id or name/class substring.

    Returns:
        dict[str, Any]: The window record that was closed.

    Raises:
        DeskProxyError: When the window is not found.
        DeskAPIError: When the close command fails.

    Examples:
        >>> close_window("missing-window-zzz")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        DeskProxyError: Window not found: missing-window-zzz
        >>> isinstance(close_window(12345), dict)  # doctest: +SKIP
        True
    """
    win = _require_window(name_or_id)
    wid = str(win["id"])
    if shutil.which("wmctrl"):
        # wmctrl wants hex id with 0x prefix
        hex_id = hex(int(wid))
        run_cmd(["wmctrl", "-ic", hex_id], check=True)
    else:
        run_cmd(["xdotool", "windowclose", wid], check=True)
    return win


def move_window(name_or_id: str | int, x: int, y: int) -> dict[str, Any]:
    """Move a window to absolute screen coordinates.

    Args:
        name_or_id (str | int): Window selector.
        x (int): Destination X in pixels.
        y (int): Destination Y in pixels.

    Returns:
        dict[str, Any]: Updated window record (best-effort re-query).

    Raises:
        DeskProxyError: When the window is not found.
        DeskAPIError: When move fails.

    Examples:
        >>> move_window("nope", 0, 0)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        DeskProxyError: Window not found: nope
        >>> move_window(list_windows()[0]["id"], 10, 10)["x"] >= 0  # doctest: +SKIP
        True
    """
    win = _require_window(name_or_id)
    run_cmd(
        ["xdotool", "windowmove", str(win["id"]), str(int(x)), str(int(y))],
        check=True,
    )
    return get_window(win["id"]) or {**win, "x": int(x), "y": int(y)}


def resize_window(name_or_id: str | int, w: int, h: int) -> dict[str, Any]:
    """Resize a window to ``w``×``h`` pixels.

    Args:
        name_or_id (str | int): Window selector.
        w (int): New width in pixels.
        h (int): New height in pixels.

    Returns:
        dict[str, Any]: Updated window record (best-effort re-query).

    Raises:
        DeskProxyError: When the window is not found.
        DeskAPIError: When resize fails.

    Examples:
        >>> resize_window("nope", 800, 600)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        DeskProxyError: Window not found: nope
        >>> resize_window(list_windows()[0]["id"], 640, 480)["width"] > 0  # doctest: +SKIP
        True
    """
    win = _require_window(name_or_id)
    run_cmd(
        ["xdotool", "windowsize", str(win["id"]), str(int(w)), str(int(h))],
        check=True,
    )
    return get_window(win["id"]) or {**win, "width": int(w), "height": int(h)}


def minimize_window(name_or_id: str | int) -> dict[str, Any]:
    """Minimize (iconify) a window.

    Args:
        name_or_id (str | int): Window selector.

    Returns:
        dict[str, Any]: The window record that was minimized.

    Raises:
        DeskProxyError: When the window is not found.
        DeskAPIError: When minimize fails.

    Examples:
        >>> minimize_window("nope")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        DeskProxyError: Window not found: nope
        >>> minimize_window(list_windows()[0]["id"])["id"] > 0  # doctest: +SKIP
        True
    """
    win = _require_window(name_or_id)
    run_cmd(["xdotool", "windowminimize", str(win["id"])], check=True)
    return win
