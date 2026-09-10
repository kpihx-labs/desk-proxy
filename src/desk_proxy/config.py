"""
desk-proxy configuration — single source of truth in ``config.py`` + ``config.json``.

Architecture:
  - Defaults live HERE (``default_config()`` / ``DEFAULT_*`` constants).
  - Durable overrides: ``~/.config/desk-proxy/config.json`` (or ``DESK_CONFIG_DIR``).
  - Optional process env overrides (not a ``.env`` file — no secrets exist):
    ``DESK_SHOT_DIR``, ``DESK_INPUT_BACKEND``, ``DESK_OCR_LANG``,
    ``DESK_HITL_TIMEOUT``, ``DESK_AUTOSAVE_DIR``, ``DESK_CONFIG_DIR``.

There is no ``.env`` / ``.env.example``: desk-proxy has zero remote credentials.
Settings are non-secret desktop preferences written by ``admin setup``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from .exceptions import DeskProxyError

InputBackend = Literal["auto", "xdotool", "ydotool"]

_DEFAULT_CONFIG_DIR = Path.home() / ".config" / "desk-proxy"

CONFIG_DIR = Path(os.environ.get("DESK_CONFIG_DIR") or _DEFAULT_CONFIG_DIR)
CONFIG_PATH = CONFIG_DIR / "config.json"

DIR_PERMISSIONS = 0o700
FILE_PERMISSIONS = 0o600

DEFAULT_SHOT_DIR = "/tmp/desk-proxy-shots"
DEFAULT_INPUT_BACKEND: InputBackend = "auto"
DEFAULT_OCR_LANG = "eng+fra"
DEFAULT_HITL_TIMEOUT = 600
DEFAULT_AUTOSAVE_DIR = "/tmp/desk-proxy-autosave"

ENV_SHOT_DIR = "DESK_SHOT_DIR"
ENV_INPUT_BACKEND = "DESK_INPUT_BACKEND"
ENV_OCR_LANG = "DESK_OCR_LANG"
ENV_HITL_TIMEOUT = "DESK_HITL_TIMEOUT"
ENV_AUTOSAVE_DIR = "DESK_AUTOSAVE_DIR"
ENV_CONFIG_DIR = "DESK_CONFIG_DIR"

VALID_INPUT_BACKENDS: frozenset[str] = frozenset({"auto", "xdotool", "ydotool"})


def default_config() -> dict[str, Any]:
    """Return the built-in default settings dict.

    Returns:
        dict[str, Any]: Keys ``shot_dir``, ``input_backend``, ``ocr_lang``,
        ``hitl_timeout``, ``autosave_dir`` with documented defaults.

    Examples:
        >>> default_config()["input_backend"]
        'auto'
        >>> default_config()["hitl_timeout"]
        600
    """
    return {
        "shot_dir": DEFAULT_SHOT_DIR,
        "input_backend": DEFAULT_INPUT_BACKEND,
        "ocr_lang": DEFAULT_OCR_LANG,
        "hitl_timeout": DEFAULT_HITL_TIMEOUT,
        "autosave_dir": DEFAULT_AUTOSAVE_DIR,
    }


def ensure_config_dir() -> Path:
    """Create the config directory (mode 0700) if missing and return it.

    Returns:
        Path: The resolved ``CONFIG_DIR``.

    Examples:
        >>> ensure_config_dir().name in ("desk-proxy", Path(os.environ.get("DESK_CONFIG_DIR", "")).name or "desk-proxy")
        True
        >>> ensure_config_dir().is_dir()
        True
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        CONFIG_DIR.chmod(DIR_PERMISSIONS)
    except OSError:
        pass
    return CONFIG_DIR


def _apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    """Overlay DESK_* environment variables onto a settings dict.

    Args:
        cfg (dict[str, Any]): Base settings (defaults and/or file).

    Returns:
        dict[str, Any]: A shallow copy with env overrides applied.

    Examples:
        >>> os.environ.pop("DESK_OCR_LANG", None)
        >>> _apply_env_overrides({"ocr_lang": "eng"})["ocr_lang"]
        'eng'
        >>> os.environ["DESK_OCR_LANG"] = "fra"
        >>> _apply_env_overrides({"ocr_lang": "eng"})["ocr_lang"]
        'fra'
        >>> del os.environ["DESK_OCR_LANG"]
    """
    out = dict(cfg)
    if ENV_SHOT_DIR in os.environ and os.environ[ENV_SHOT_DIR].strip():
        out["shot_dir"] = os.environ[ENV_SHOT_DIR].strip()
    if ENV_INPUT_BACKEND in os.environ and os.environ[ENV_INPUT_BACKEND].strip():
        backend = os.environ[ENV_INPUT_BACKEND].strip()
        if backend not in VALID_INPUT_BACKENDS:
            raise DeskProxyError(
                f"Invalid {ENV_INPUT_BACKEND}={backend!r}. "
                f"Expected one of: {', '.join(sorted(VALID_INPUT_BACKENDS))}."
            )
        out["input_backend"] = backend
    if ENV_OCR_LANG in os.environ and os.environ[ENV_OCR_LANG].strip():
        out["ocr_lang"] = os.environ[ENV_OCR_LANG].strip()
    if ENV_HITL_TIMEOUT in os.environ and os.environ[ENV_HITL_TIMEOUT].strip():
        try:
            out["hitl_timeout"] = int(os.environ[ENV_HITL_TIMEOUT].strip())
        except ValueError as exc:
            raise DeskProxyError(
                f"Invalid {ENV_HITL_TIMEOUT}={os.environ[ENV_HITL_TIMEOUT]!r} "
                "(expected integer seconds)."
            ) from exc
    if ENV_AUTOSAVE_DIR in os.environ and os.environ[ENV_AUTOSAVE_DIR].strip():
        out["autosave_dir"] = os.environ[ENV_AUTOSAVE_DIR].strip()
    return out


def load_config() -> dict[str, Any]:
    """Load settings from ``config.json`` then apply env overrides.

    Missing file → defaults. Malformed JSON raises ``DeskProxyError``.

    Returns:
        dict[str, Any]: Effective settings (file ∪ env ∪ defaults).

    Raises:
        DeskProxyError: When ``config.json`` exists but is not a JSON object,
            or an env override is invalid.

    Examples:
        >>> cfg = load_config()
        >>> cfg["input_backend"] in ("auto", "xdotool", "ydotool")
        True
        >>> isinstance(cfg["hitl_timeout"], int)
        True
    """
    base = default_config()
    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise DeskProxyError(f"Cannot parse {CONFIG_PATH}: {exc}") from exc
        if not isinstance(raw, dict):
            raise DeskProxyError(f"{CONFIG_PATH} must contain a JSON object.")
        for key in default_config():
            if key in raw and raw[key] is not None:
                base[key] = raw[key]
        if base["input_backend"] not in VALID_INPUT_BACKENDS:
            raise DeskProxyError(
                f"Invalid input_backend={base['input_backend']!r} in {CONFIG_PATH}."
            )
        try:
            base["hitl_timeout"] = int(base["hitl_timeout"])
        except (TypeError, ValueError) as exc:
            raise DeskProxyError(
                f"Invalid hitl_timeout={base['hitl_timeout']!r} in {CONFIG_PATH}."
            ) from exc
    return _apply_env_overrides(base)


def save_config(cfg: dict[str, Any]) -> Path:
    """Write settings to ``config.json`` (chmod 0600) and return the path.

    Args:
        cfg (dict[str, Any]): Full or partial settings. Missing keys are filled
            from ``default_config()`` before write.

    Returns:
        Path: Absolute path of the written ``config.json``.

    Raises:
        DeskProxyError: When ``input_backend`` or ``hitl_timeout`` is invalid.

    Examples:
        >>> path = save_config({"ocr_lang": "eng"})
        >>> path.name
        'config.json'
        >>> save_config(default_config()).exists()
        True
    """
    ensure_config_dir()
    merged = default_config()
    merged.update({k: v for k, v in cfg.items() if v is not None})
    if merged["input_backend"] not in VALID_INPUT_BACKENDS:
        raise DeskProxyError(
            f"Invalid input_backend={merged['input_backend']!r}. "
            f"Expected one of: {', '.join(sorted(VALID_INPUT_BACKENDS))}."
        )
    try:
        merged["hitl_timeout"] = int(merged["hitl_timeout"])
    except (TypeError, ValueError) as exc:
        raise DeskProxyError(
            f"Invalid hitl_timeout={merged['hitl_timeout']!r} (expected int)."
        ) from exc
    payload = {
        "shot_dir": str(merged["shot_dir"]),
        "input_backend": merged["input_backend"],
        "ocr_lang": str(merged["ocr_lang"]),
        "hitl_timeout": int(merged["hitl_timeout"]),
        "autosave_dir": str(merged["autosave_dir"]),
    }
    CONFIG_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        CONFIG_PATH.chmod(FILE_PERMISSIONS)
    except OSError:
        pass
    return CONFIG_PATH


def shot_dir() -> Path:
    """Return the effective screenshot directory (creates it if needed).

    Returns:
        Path: Absolute shot directory from config/env.

    Examples:
        >>> shot_dir().is_absolute()
        True
        >>> str(shot_dir()).endswith("desk-proxy-shots") or "shot" in str(shot_dir())
        True
    """
    path = Path(str(load_config()["shot_dir"])).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def input_backend() -> InputBackend:
    """Return the effective input backend setting.

    Returns:
        InputBackend: ``auto``, ``xdotool``, or ``ydotool``.

    Examples:
        >>> input_backend() in ("auto", "xdotool", "ydotool")
        True
        >>> isinstance(input_backend(), str)
        True
    """
    return load_config()["input_backend"]  # type: ignore[return-value]


def ocr_lang() -> str:
    """Return the effective OCR language string.

    Returns:
        str: Tesseract language pack list, e.g. ``eng+fra``.

    Examples:
        >>> "+" in ocr_lang() or ocr_lang().isalpha()
        True
        >>> len(ocr_lang()) > 0
        True
    """
    return str(load_config()["ocr_lang"])


def hitl_timeout() -> int:
    """Return the HITL review timeout in seconds.

    Returns:
        int: Seconds to wait for HITL (default 600).

    Examples:
        >>> hitl_timeout() >= 0
        True
        >>> isinstance(hitl_timeout(), int)
        True
    """
    return int(load_config()["hitl_timeout"])


def autosave_dir() -> Path:
    """Return the effective autosave directory (creates it if needed).

    Returns:
        Path: Absolute autosave directory from config/env.

    Examples:
        >>> autosave_dir().is_absolute()
        True
        >>> autosave_dir().is_dir()
        True
    """
    path = Path(str(load_config()["autosave_dir"])).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _discover_xauthority(uid: int) -> str | None:
    """Locate an Xauthority file usable with Mutter/XWayland.

    Args:
        uid (int): Target user id (normally ``os.getuid()``).

    Returns:
        str | None: Absolute path to an Xauthority file, or None when none
        can be found.

    Examples:
        >>> path = _discover_xauthority(os.getuid())
        >>> path is None or path.startswith("/run/user/") or path.endswith("Xauthority")
        True
        >>> isinstance(_discover_xauthority(os.getuid()), (str, type(None)))
        True
    """
    if os.environ.get("XAUTHORITY") and Path(os.environ["XAUTHORITY"]).is_file():
        return os.environ["XAUTHORITY"]
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}")
    # Mutter writes a rotating cookie: /run/user/$UID/.mutter-Xwaylandauth.XXXXXX
    if runtime.is_dir():
        candidates = sorted(
            runtime.glob(".mutter-Xwaylandauth.*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for cand in candidates:
            if cand.is_file():
                return str(cand)
    home_auth = Path.home() / ".Xauthority"
    if home_auth.is_file():
        return str(home_auth)
    return None


def display_env() -> dict[str, str]:
    """Build a display/session env dict for spawning desktop tools.

    Reads ``DISPLAY``, ``WAYLAND_DISPLAY``, ``DBUS_SESSION_BUS_ADDRESS``,
    ``XDG_RUNTIME_DIR``, and ``XAUTHORITY`` from ``os.environ``, with
    documented fallbacks for headless or stripped agent shells. On GNOME
    Wayland, ``XAUTHORITY`` is resolved from Mutter's
    ``.mutter-Xwaylandauth.*`` cookie so xdotool can talk to XWayland.

    Returns:
        dict[str, str]: Keys suitable for ``subprocess`` ``env=`` merges.

    Examples:
        >>> env = display_env()
        >>> "DISPLAY" in env and env["DISPLAY"]
        True
        >>> env["XDG_RUNTIME_DIR"].startswith("/run/user/")
        True
    """
    uid = os.getuid()
    env = {
        "DISPLAY": os.environ.get("DISPLAY") or ":0",
        "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY") or "wayland-0",
        "DBUS_SESSION_BUS_ADDRESS": os.environ.get("DBUS_SESSION_BUS_ADDRESS")
        or f"unix:path=/run/user/{uid}/bus",
        "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}",
    }
    xauth = _discover_xauthority(uid)
    if xauth:
        env["XAUTHORITY"] = xauth
    return env
