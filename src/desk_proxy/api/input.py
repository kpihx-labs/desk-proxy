"""
Keyboard / mouse injection with auto-selected backend.

Preference: xdotool when DISPLAY geometry works, else ydotool.
Typing: wtype (Unicode / Wayland) → xdotool type → ydotool type.
"""

from __future__ import annotations

import shutil
import time
from typing import Any, Literal

from desk_proxy.api.run import run_cmd
from desk_proxy.config import input_backend
from desk_proxy.exceptions import DeskAPIError, DeskProxyError

ButtonName = Literal["left", "right", "middle"]
ScrollDir = Literal["up", "down", "left", "right"]

_XDOTOOL_BTN = {"left": "1", "middle": "2", "right": "3"}
_XDOTOOL_SCROLL = {"up": "4", "down": "5", "left": "6", "right": "7"}
# ydotool click codes (button index; 0xC0 = left full click with down+up bits)
_YDO_BTN = {"left": 0x00, "right": 0x01, "middle": 0x02}
_YDO_CLICK = {"left": 0xC0, "right": 0xC1, "middle": 0xC2}

# Linux KEY_* codes for ydotool key chords (US layout).
_YDO_KEYS: dict[str, int] = {
    "ctrl": 29,
    "control": 29,
    "alt": 56,
    "shift": 42,
    "super": 125,
    "meta": 125,
    "win": 125,
    "return": 28,
    "enter": 28,
    "escape": 1,
    "esc": 1,
    "backspace": 14,
    "tab": 15,
    "space": 57,
    "f1": 59,
    "f2": 60,
    "f3": 61,
    "f4": 62,
    "f5": 63,
    "f6": 64,
    "f7": 65,
    "f8": 66,
    "f9": 67,
    "f10": 68,
    "f11": 87,
    "f12": 88,
    "a": 30,
    "b": 48,
    "c": 46,
    "d": 32,
    "e": 18,
    "f": 33,
    "g": 34,
    "h": 35,
    "i": 23,
    "j": 36,
    "k": 37,
    "l": 38,
    "m": 50,
    "n": 49,
    "o": 24,
    "p": 25,
    "q": 16,
    "r": 19,
    "s": 31,
    "t": 20,
    "u": 22,
    "v": 47,
    "w": 17,
    "x": 45,
    "y": 21,
    "z": 44,
    "1": 2,
    "2": 3,
    "3": 4,
    "4": 5,
    "5": 6,
    "6": 7,
    "7": 8,
    "8": 9,
    "9": 10,
    "0": 11,
}


def _xdotool_display_ok() -> bool:
    """Return True when ``xdotool getdisplaygeometry`` succeeds.

    Returns:
        bool: True when an X/XWayland display is usable via xdotool.

    Examples:
        >>> isinstance(_xdotool_display_ok(), bool)
        True
        >>> _xdotool_display_ok() or True
        True
    """
    if not shutil.which("xdotool"):
        return False
    r = run_cmd(["xdotool", "getdisplaygeometry"], timeout=5)
    if r.returncode != 0:
        return False
    parts = (r.stdout or "").strip().split()
    return len(parts) == 2 and all(p.isdigit() for p in parts)


def resolve_input_backend() -> str:
    """Pick the active input backend (``xdotool`` or ``ydotool``).

    Honours ``config.input_backend()`` when not ``auto``.

    Returns:
        str: ``"xdotool"`` or ``"ydotool"``.

    Raises:
        DeskProxyError: When no usable backend is available.

    Examples:
        >>> resolve_input_backend() in ("xdotool", "ydotool")
        True
        >>> isinstance(resolve_input_backend(), str)
        True
    """
    pref = input_backend()
    if pref == "xdotool":
        if not shutil.which("xdotool"):
            raise DeskProxyError(
                "DESK_INPUT_BACKEND=xdotool but xdotool is not on PATH"
            )
        return "xdotool"
    if pref == "ydotool":
        if not shutil.which("ydotool"):
            raise DeskProxyError(
                "DESK_INPUT_BACKEND=ydotool but ydotool is not on PATH"
            )
        return "ydotool"
    if _xdotool_display_ok():
        return "xdotool"
    if shutil.which("ydotool"):
        return "ydotool"
    raise DeskProxyError(
        "No input backend available. Install xdotool (X11/XWayland) or "
        "ydotool + ydotoold (Wayland)."
    )


def get_mouse() -> dict[str, int]:
    """Return the current pointer position.

    Returns:
        dict[str, int]: ``{"x": int, "y": int}``.

    Raises:
        DeskAPIError: When location cannot be read.

    Examples:
        >>> pos = get_mouse()
        >>> "x" in pos and "y" in pos
        True
        >>> isinstance(get_mouse()["x"], int)
        True
    """
    backend = resolve_input_backend()
    if backend == "xdotool":
        r = run_cmd(["xdotool", "getmouselocation", "--shell"], check=True)
        vals: dict[str, int] = {}
        for line in (r.stdout or "").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                if k.strip() in ("X", "Y"):
                    vals[k.strip().lower()] = int(v.strip())
        if "x" not in vals or "y" not in vals:
            raise DeskAPIError(500, "xdotool getmouselocation returned no X/Y")
        return {"x": vals["x"], "y": vals["y"]}
    # ydotool has no getmouselocation — fall back to xdotool if present
    if shutil.which("xdotool"):
        r = run_cmd(["xdotool", "getmouselocation", "--shell"])
        if r.returncode == 0:
            vals = {}
            for line in (r.stdout or "").splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() in ("X", "Y"):
                        vals[k.strip().lower()] = int(v.strip())
            if "x" in vals and "y" in vals:
                return {"x": vals["x"], "y": vals["y"]}
    raise DeskAPIError(
        501,
        "Cannot read mouse position (need xdotool getmouselocation; "
        "ydotool has no query API)",
    )


def move_mouse(x: int, y: int) -> dict[str, int]:
    """Move the pointer to absolute coordinates.

    Args:
        x (int): Target X in pixels.
        y (int): Target Y in pixels.

    Returns:
        dict[str, int]: ``{"x": x, "y": y}``.

    Raises:
        DeskAPIError: When the move command fails.

    Examples:
        >>> move_mouse(10, 10) == {"x": 10, "y": 10}  # doctest: +SKIP
        True
        >>> sorted(move_mouse(0, 0))  # doctest: +SKIP
        ['x', 'y']
    """
    backend = resolve_input_backend()
    if backend == "xdotool":
        # Prefer non-sync moves: ``--sync`` hangs on some XWayland/Mutter
        # frames when the pointer is already near the target or during drag.
        run_cmd(
            ["xdotool", "mousemove", "--", str(int(x)), str(int(y))],
            check=True,
            timeout=5,
        )
    else:
        run_cmd(
            [
                "ydotool",
                "mousemove",
                "--absolute",
                "-x",
                str(int(x)),
                "-y",
                str(int(y)),
            ],
            check=True,
        )
    return {"x": int(x), "y": int(y)}


def click(
    x: int,
    y: int,
    button: ButtonName = "left",
    clicks: int = 1,
) -> dict[str, Any]:
    """Move to ``(x, y)`` and click.

    Args:
        x (int): Click X.
        y (int): Click Y.
        button (ButtonName): ``left``, ``right``, or ``middle``.
        clicks (int): Number of clicks (>= 1). Use 2 for double-click.

    Returns:
        dict[str, Any]: Confirmation with ``x``, ``y``, ``button``, ``clicks``.

    Raises:
        DeskProxyError: When ``button`` is invalid.
        DeskAPIError: When injection fails.

    Examples:
        >>> click(100, 200, button="left")["button"]  # doctest: +SKIP
        'left'
        >>> click(0, 0, clicks=2)["clicks"]  # doctest: +SKIP
        2
    """
    btn = button.lower()  # type: ignore[assignment]
    if btn not in _XDOTOOL_BTN:
        raise DeskProxyError(f"Invalid button={button!r}; expected left|right|middle")
    clicks = max(1, int(clicks))
    move_mouse(x, y)
    backend = resolve_input_backend()
    if backend == "xdotool":
        run_cmd(
            [
                "xdotool",
                "click",
                "--repeat",
                str(clicks),
                "--delay",
                "100",
                _XDOTOOL_BTN[btn],
            ],
            check=True,
        )
    else:
        code = _YDO_CLICK[btn]
        run_cmd(
            [
                "ydotool",
                "click",
                "--repeat",
                str(clicks),
                "--next-delay",
                "100",
                hex(code),
            ],
            check=True,
        )
    return {"x": int(x), "y": int(y), "button": btn, "clicks": clicks}


def drag(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    button: ButtonName = "left",
    duration_ms: int = 300,
) -> dict[str, Any]:
    """Drag from ``(x1,y1)`` to ``(x2,y2)`` with the given button held.

    Args:
        x1 (int): Start X.
        y1 (int): Start Y.
        x2 (int): End X.
        y2 (int): End Y.
        button (ButtonName): Button held during the drag.
        duration_ms (int): Approximate drag duration in milliseconds.

    Returns:
        dict[str, Any]: Start/end coordinates and button used.

    Raises:
        DeskProxyError: When ``button`` is invalid.
        DeskAPIError: When injection fails.

    Examples:
        >>> drag(10, 10, 50, 50)["button"]  # doctest: +SKIP
        'left'
        >>> drag(0, 0, 1, 1, duration_ms=50)["x2"]  # doctest: +SKIP
        1
    """
    btn = button.lower()  # type: ignore[assignment]
    if btn not in _XDOTOOL_BTN:
        raise DeskProxyError(f"Invalid button={button!r}; expected left|right|middle")
    duration_ms = max(1, int(duration_ms))
    backend = resolve_input_backend()
    if backend == "xdotool":
        # One argv chain keeps button state consistent and avoids --sync hangs.
        run_cmd(
            [
                "xdotool",
                "mousemove",
                "--",
                str(int(x1)),
                str(int(y1)),
                "mousedown",
                _XDOTOOL_BTN[btn],
                "mousemove",
                "--",
                str(int(x2)),
                str(int(y2)),
                "mouseup",
                _XDOTOOL_BTN[btn],
            ],
            check=True,
            timeout=max(10.0, duration_ms / 1000.0 + 5.0),
        )
        time.sleep(min(duration_ms / 1000.0, 0.05))
    else:
        down = 0x40 | _YDO_BTN[btn]
        up = 0x80 | _YDO_BTN[btn]
        run_cmd(["ydotool", "click", hex(down)], check=True)
        steps = max(2, duration_ms // 30)
        for i in range(1, steps + 1):
            xi = int(x1 + (x2 - x1) * i / steps)
            yi = int(y1 + (y2 - y1) * i / steps)
            run_cmd(
                ["ydotool", "mousemove", "--absolute", "-x", str(xi), "-y", str(yi)],
                check=True,
            )
            time.sleep(duration_ms / 1000.0 / steps)
        run_cmd(["ydotool", "click", hex(up)], check=True)
    return {
        "x1": int(x1),
        "y1": int(y1),
        "x2": int(x2),
        "y2": int(y2),
        "button": btn,
        "duration_ms": duration_ms,
    }


def scroll(
    x: int,
    y: int,
    direction: ScrollDir = "down",
    clicks: int = 3,
) -> dict[str, Any]:
    """Scroll at coordinates.

    Args:
        x (int): Pointer X before scrolling.
        y (int): Pointer Y before scrolling.
        direction (ScrollDir): ``up``, ``down``, ``left``, or ``right``.
        clicks (int): Number of scroll ticks.

    Returns:
        dict[str, Any]: Confirmation payload.

    Raises:
        DeskProxyError: When ``direction`` is invalid.
        DeskAPIError: When injection fails.

    Examples:
        >>> scroll(100, 100, direction="down", clicks=2)["direction"]  # doctest: +SKIP
        'down'
        >>> scroll(0, 0, "up")["clicks"]  # doctest: +SKIP
        3
    """
    direction_l = direction.lower()  # type: ignore[assignment]
    if direction_l not in _XDOTOOL_SCROLL:
        raise DeskProxyError(
            f"Invalid direction={direction!r}; expected up|down|left|right"
        )
    clicks = max(1, int(clicks))
    move_mouse(x, y)
    backend = resolve_input_backend()
    if backend == "xdotool":
        btn = _XDOTOOL_SCROLL[direction_l]
        for _ in range(clicks):
            run_cmd(["xdotool", "click", btn], check=True)
    else:
        # ydotool wheel: positive = up, negative = down (common convention)
        delta = {
            "up": clicks,
            "down": -clicks,
            "left": -clicks,
            "right": clicks,
        }[direction_l]
        if direction_l in ("left", "right"):
            # Horizontal wheel not uniformly supported — emulate via vertical
            # when horizontal is requested on ydotool by repeating vertical.
            pass
        run_cmd(
            ["ydotool", "mousemove", "--wheel", "--", "0", str(int(delta))],
            check=True,
        )
    return {
        "x": int(x),
        "y": int(y),
        "direction": direction_l,
        "clicks": clicks,
    }


def type_text(text: str, delay_ms: int = 12) -> dict[str, Any]:
    """Type Unicode text at the current keyboard focus.

    Prefers ``wtype`` on Wayland for proper Unicode, then xdotool, then ydotool.

    Args:
        text (str): Text to type.
        delay_ms (int): Inter-key delay in milliseconds.

    Returns:
        dict[str, Any]: ``{"typed": preview, "backend": tool, "delay_ms": int}``.

    Raises:
        DeskAPIError: When no typing backend works.

    Examples:
        >>> type_text("hi")["delay_ms"]  # doctest: +SKIP
        12
        >>> "backend" in type_text("ok")  # doctest: +SKIP
        True
    """
    delay_ms = max(0, int(delay_ms))
    preview = text[:40] + ("..." if len(text) > 40 else "")

    if shutil.which("wtype"):
        run_cmd(["wtype", "-d", str(delay_ms), "--", text], check=True)
        return {"typed": preview, "backend": "wtype", "delay_ms": delay_ms}

    backend = resolve_input_backend()
    if backend == "xdotool" or shutil.which("xdotool"):
        run_cmd(
            ["xdotool", "type", "--delay", str(delay_ms), "--", text],
            check=True,
        )
        return {"typed": preview, "backend": "xdotool", "delay_ms": delay_ms}

    if shutil.which("ydotool"):
        run_cmd(
            ["ydotool", "type", "--key-delay", str(delay_ms), "--", text],
            check=True,
        )
        return {"typed": preview, "backend": "ydotool", "delay_ms": delay_ms}

    raise DeskAPIError(0, "No typing backend (need wtype, xdotool, or ydotool)")


def _combo_to_ydotool(combo: str) -> list[str]:
    """Convert an xdotool-style combo (``ctrl+c``) to ydotool keycode events.

    Args:
        combo (str): Key chord using ``+`` separators (case-insensitive).

    Returns:
        list[str]: ``keycode:1`` / ``keycode:0`` tokens for ``ydotool key``.

    Raises:
        DeskProxyError: When a token has no known keycode mapping.

    Examples:
        >>> _combo_to_ydotool("ctrl+c")
        ['29:1', '46:1', '46:0', '29:0']
        >>> _combo_to_ydotool("Return")
        ['28:1', '28:0']
    """
    parts = [p.strip().lower() for p in combo.replace("-", "+").split("+") if p.strip()]
    if not parts:
        raise DeskProxyError("Empty key combo")
    codes: list[int] = []
    for part in parts:
        if part not in _YDO_KEYS:
            raise DeskProxyError(
                f"Cannot map key {part!r} to a ydotool keycode. "
                "Use xdotool backend or a mapped name (ctrl, alt, a-z, F1-F12, …)."
            )
        codes.append(_YDO_KEYS[part])
    events: list[str] = [f"{c}:1" for c in codes]
    events.extend(f"{c}:0" for c in reversed(codes))
    return events


def press_key(combo: str) -> dict[str, str]:
    """Press a key or chord (``ctrl+c``, ``Return``, ``alt+F4``, …).

    Args:
        combo (str): xdotool-style combo string.

    Returns:
        dict[str, str]: ``{"combo": combo, "backend": ...}``.

    Raises:
        DeskAPIError: When injection fails.
        DeskProxyError: When ydotool cannot map the combo.

    Examples:
        >>> press_key("Escape")["combo"]  # doctest: +SKIP
        'Escape'
        >>> press_key("ctrl+a")["backend"] in ("xdotool", "ydotool", "wtype")  # doctest: +SKIP
        True
    """
    backend = resolve_input_backend()
    if backend == "xdotool":
        run_cmd(["xdotool", "key", "--clearmodifiers", combo], check=True)
        return {"combo": combo, "backend": "xdotool"}

    # Prefer wtype for simple chords on Wayland when available
    if shutil.which("wtype") and "+" in combo:
        parts = [p.strip() for p in combo.split("+") if p.strip()]
        mods = [p for p in parts[:-1]]
        key = parts[-1]
        argv = ["wtype"]
        for m in mods:
            argv.extend(["-M", m.lower()])
        argv.extend(["-k", key])
        for m in reversed(mods):
            argv.extend(["-m", m.lower()])
        run_cmd(argv, check=True)
        return {"combo": combo, "backend": "wtype"}

    events = _combo_to_ydotool(combo)
    run_cmd(["ydotool", "key", *events], check=True)
    return {"combo": combo, "backend": "ydotool"}
