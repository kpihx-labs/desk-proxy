"""
Window discovery and control via xdotool (+ wmctrl when useful).
"""

from __future__ import annotations

import shutil
from typing import Any

from desk_proxy.api.run import run_cmd
from desk_proxy.exceptions import DeskProxyError

_SKIP_NAMES = frozenset({"", "mutter guard window"})


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


def list_windows() -> list[dict[str, Any]]:
    """List visible XWayland/X11 windows with geometry.

    Uses xdotool search, with a ``wmctrl -lG`` enrichment when available
    (often surfaces titles xdotool alone misses).

    Returns:
        list[dict[str, Any]]: Records ``{id, name, x, y, width, height}``.
        Empty list when no backend finds windows (pure Wayland natives may
        be absent).

    Examples:
        >>> isinstance(list_windows(), list)
        True
        >>> all("id" in w and "name" in w for w in list_windows()[:3]) or list_windows() == []
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
                if wid not in by_id:
                    by_id[wid] = {
                        "id": wid,
                        "name": name,
                        "x": x,
                        "y": y,
                        "width": w,
                        "height": h,
                    }

    return list(by_id.values())


def get_window(name_or_id: str | int) -> dict[str, Any] | None:
    """Resolve a window by numeric id or partial name / class.

    Args:
        name_or_id (str | int): Window id, or substring matched against title
            then WM_CLASS via xdotool search.

    Returns:
        dict[str, Any] | None: Canonical window dict, or None when not found.

    Examples:
        >>> get_window(999999999) is None
        True
        >>> w = get_window("Cursor")  # doctest: +SKIP
        >>> w is None or "width" in w
        True
    """
    wid: str | None = None
    if isinstance(name_or_id, int) or str(name_or_id).isdigit():
        wid = str(int(name_or_id))
    else:
        needle = str(name_or_id)
        for flag in ("--name", "--class"):
            r = run_cmd(["xdotool", "search", flag, needle])
            if r.returncode == 0 and (r.stdout or "").strip():
                wid = r.stdout.strip().splitlines()[-1]
                break
        if wid is None:
            # Fallback: scan listed windows for substring match
            needle_l = needle.lower()
            for win in list_windows():
                if needle_l in str(win["name"]).lower():
                    return win
            return None

    name_r = run_cmd(["xdotool", "getwindowname", wid])
    if name_r.returncode != 0:
        return None
    geom_r = run_cmd(["xdotool", "getwindowgeometry", "--shell", wid])
    if geom_r.returncode != 0:
        return None
    return _window_dict(
        wid, (name_r.stdout or "").strip(), _parse_geometry_shell(geom_r.stdout or "")
    )


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
