"""
Clipboard get/set via wl-clipboard (preferred) or xclip.
"""

from __future__ import annotations

import shutil

from desk_proxy.api.run import run_cmd
from desk_proxy.exceptions import DeskAPIError


def clipboard_get() -> str:
    """Read the current clipboard text.

    Prefers ``wl-paste`` on Wayland, falls back to ``xclip -o``.

    Returns:
        str: Clipboard contents (may be empty).

    Raises:
        DeskAPIError: When neither backend is available or both fail.

    Examples:
        >>> clipboard_set("desk-proxy-probe"); clipboard_get()  # doctest: +SKIP
        'desk-proxy-probe'
        >>> isinstance(clipboard_get(), str)  # doctest: +SKIP
        True
    """
    errors: list[str] = []
    if shutil.which("wl-paste"):
        try:
            r = run_cmd(["wl-paste", "--no-newline"], timeout=3)
            if r.returncode == 0:
                return r.stdout or ""
            errors.append((r.stderr or r.stdout or "wl-paste failed").strip())
        except DeskAPIError as exc:
            errors.append(str(exc))
    if shutil.which("xclip"):
        try:
            r = run_cmd(["xclip", "-selection", "clipboard", "-o"], timeout=3)
            if r.returncode == 0:
                return r.stdout or ""
            errors.append((r.stderr or r.stdout or "xclip failed").strip())
        except DeskAPIError as exc:
            errors.append(str(exc))
    detail = "; ".join(errors) if errors else "install wl-clipboard or xclip"
    raise DeskAPIError(500, f"clipboard_get failed — {detail}")


def clipboard_set(text: str) -> str:
    """Write ``text`` to the clipboard.

    Prefers ``wl-copy``, falls back to ``xclip -i``. Uses ``capture=False``
    so daemonized clipboard helpers do not hang on inherited pipes.

    Args:
        text (str): Text to place on the clipboard.

    Returns:
        str: The same ``text`` that was set (echo for callers).

    Raises:
        DeskAPIError: When neither backend is available or both fail.

    Examples:
        >>> clipboard_set("hello")  # doctest: +SKIP
        'hello'
        >>> clipboard_set("")  # doctest: +SKIP
        ''
    """
    errors: list[str] = []
    if shutil.which("wl-copy"):
        try:
            # Prefer argv form for short strings; stdin for large / binary-ish text
            if len(text) < 2000 and "\x00" not in text:
                r = run_cmd(
                    ["wl-copy", "--", text],
                    timeout=3,
                    capture=False,
                )
            else:
                r = run_cmd(
                    ["wl-copy"],
                    timeout=3,
                    input_text=text,
                    capture=False,
                )
            if r.returncode == 0:
                return text
            errors.append("wl-copy failed")
        except DeskAPIError as exc:
            errors.append(str(exc))
    if shutil.which("xclip"):
        try:
            r = run_cmd(
                ["xclip", "-selection", "clipboard", "-i", "-loops", "1"],
                timeout=3,
                input_text=text,
                capture=False,
            )
            if r.returncode == 0:
                return text
            errors.append("xclip failed")
        except DeskAPIError as exc:
            errors.append(str(exc))
    detail = "; ".join(errors) if errors else "install wl-clipboard or xclip"
    raise DeskAPIError(500, f"clipboard_set failed — {detail}")
