"""
Subprocess runner for desk-proxy desktop backends.

Merges ``display_env()`` into every spawn so tools see DISPLAY / Wayland /
DBus / XAUTHORITY even when the agent shell itself is stripped.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping

from desk_proxy.config import display_env
from desk_proxy.exceptions import DeskAPIError


def run_cmd(
    cmd: list[str],
    timeout: float = 15,
    env: Mapping[str, str] | None = None,
    *,
    check: bool = False,
    input_text: str | None = None,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a local command with the graphical-session environment merged in.

    Args:
        cmd (list[str]): argv list (no shell). Example: ``["xdotool", "getmouselocation"]``.
        timeout (float): Seconds before timeout becomes ``DeskAPIError``.
        env (Mapping[str, str] | None): Extra env vars layered on top of
            ``os.environ`` and ``display_env()``. Later keys win.
        check (bool): When True, raise ``DeskAPIError`` if returncode != 0.
        input_text (str | None): Optional stdin text (e.g. for ``wl-copy``).
        capture (bool): When True (default), capture stdout/stderr as text.
            Set False for tools that daemonize and inherit pipes (``wl-copy``),
            which would otherwise hang ``communicate()``.

    Returns:
        subprocess.CompletedProcess[str]: Captured stdout/stderr as text
        (empty strings when ``capture`` is False).

    Raises:
        DeskAPIError: When ``check`` is True and the process exits non-zero,
            when the binary cannot be executed, or when ``timeout`` expires.

    Examples:
        >>> r = run_cmd(["true"])
        >>> r.returncode
        0
        >>> run_cmd(["false"], check=True)  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        DeskAPIError: [1] Command failed: false
    """
    merged = {**os.environ, **display_env()}
    if env:
        merged.update({k: str(v) for k, v in env.items()})
    kwargs: dict = {
        "text": True,
        "timeout": timeout,
        "env": merged,
        "input": input_text,
    }
    if capture:
        kwargs["capture_output"] = True
    else:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    try:
        result = subprocess.run(cmd, check=False, **kwargs)
    except FileNotFoundError as exc:
        raise DeskAPIError(0, f"Binary not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise DeskAPIError(
            124, f"Command timed out after {timeout}s: {' '.join(cmd)}"
        ) from exc
    except OSError as exc:
        raise DeskAPIError(0, f"Cannot execute {cmd[0]}: {exc}") from exc

    if not capture:
        result = subprocess.CompletedProcess(
            result.args, result.returncode, stdout="", stderr=""
        )

    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        msg = f"Command failed: {' '.join(cmd)}"
        if detail:
            msg = f"{msg} — {detail[:400]}"
        raise DeskAPIError(result.returncode or 1, msg)
    return result
