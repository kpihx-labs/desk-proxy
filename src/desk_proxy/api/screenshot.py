"""
Screenshot capture and crop backends for desk-proxy.

Order: XDG Desktop Portal (system python3 + dbus + GLib) → gnome-screenshot
→ grim. Window/region crops use Pillow with clamped bounds.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from desk_proxy.api.run import run_cmd
from desk_proxy.api.windows import get_window
from desk_proxy.config import display_env
from desk_proxy.config import shot_dir as config_shot_dir
from desk_proxy.exceptions import DeskAPIError

# Ported from desk-mcp — keep the portal script intact for GNOME Wayland.
PORTAL_SCRIPT = """\
import sys, dbus, dbus.mainloop.glib
from gi.repository import GLib

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
loop = GLib.MainLoop()
result = {}

def on_response(response, results, **kwargs):
    if response == 0:
        result['uri'] = str(results.get('uri', ''))
    loop.quit()

def on_timeout():
    loop.quit()
    return False

try:
    portal = bus.get_object('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop')
    portal_iface = dbus.Interface(portal, 'org.freedesktop.portal.Screenshot')
    options = dbus.Dictionary({'interactive': dbus.Boolean(False)}, signature='sv')
    request_path = str(portal_iface.Screenshot('', options))
    request_obj = bus.get_object('org.freedesktop.portal.Desktop', request_path)
    request_iface = dbus.Interface(request_obj, 'org.freedesktop.portal.Request')
    request_iface.connect_to_signal('Response', on_response)
    GLib.timeout_add_seconds(15, on_timeout)
    loop.run()
except Exception:
    pass

print(result.get('uri', ''), end='')
"""


def _ts() -> str:
    """Return a compact timestamp fragment for shot filenames.

    Returns:
        str: ``HHMMSS_mmm`` style stamp (10 chars).

    Examples:
        >>> len(_ts())
        10
        >>> "_" in _ts()
        True
    """
    return datetime.now(UTC).strftime("%H%M%S_%f")[:10]


def take_screenshot(dest: Path) -> Path:
    """Capture a full-screen PNG into ``dest`` via portal / gnome / grim.

    Args:
        dest (Path): Destination PNG path (parent dirs are created).

    Returns:
        Path: Absolute path of the written screenshot.

    Raises:
        DeskAPIError: When every backend fails.

    Examples:
        >>> p = take_screenshot(Path("/tmp/desk-proxy-shots/_probe.png"))  # doctest: +SKIP
        >>> p.suffix
        '.png'
        >>> take_screenshot(Path("/tmp/desk-proxy-shots/_probe2.png")).is_file()  # doctest: +SKIP
        True
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    # 1) XDG Desktop Portal via system python3 + dbus + GLib
    try:
        r = run_cmd(["/usr/bin/python3", "-c", PORTAL_SCRIPT], timeout=20)
        uri = (r.stdout or "").strip()
        if uri.startswith("file://"):
            src = Path(uri[len("file://") :])
            if src.exists():
                shutil.copy2(src, dest)
                return dest.resolve()
        if uri:
            errors.append(f"portal uri unusable: {uri[:120]}")
        elif (r.stderr or "").strip():
            errors.append(f"portal: {(r.stderr or '').strip()[:200]}")
        else:
            errors.append("portal: empty uri")
    except DeskAPIError as exc:
        errors.append(f"portal: {exc}")

    # 2) gnome-screenshot (capture=False — it may fork/notify and hold pipes)
    if shutil.which("gnome-screenshot"):
        try:
            dest.unlink(missing_ok=True)
            r2 = run_cmd(
                ["gnome-screenshot", "-f", str(dest)],
                timeout=8,
                capture=False,
            )
            if r2.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
                return dest.resolve()
            errors.append(f"gnome-screenshot rc={r2.returncode}")
        except DeskAPIError as exc:
            errors.append(f"gnome-screenshot: {exc}")

    # 3) grim (Wayland / wlroots)
    if shutil.which("grim"):
        try:
            r3 = run_cmd(["grim", str(dest)], timeout=12)
            if r3.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
                return dest.resolve()
            errors.append(
                f"grim rc={r3.returncode}: {(r3.stderr or r3.stdout or '').strip()[:200]}"
            )
        except DeskAPIError as exc:
            errors.append(f"grim: {exc}")

    # 4) ffmpeg x11grab — XWayland root (improved fallback beyond desk-mcp)
    if shutil.which("ffmpeg"):
        try:
            w, h = 0, 0
            geom = run_cmd(["xdotool", "getdisplaygeometry"], timeout=5)
            if geom.returncode == 0:
                parts = (geom.stdout or "").strip().split()
                if len(parts) == 2 and all(p.isdigit() for p in parts):
                    w, h = int(parts[0]), int(parts[1])
            if w > 0 and h > 0:
                disp = display_env().get("DISPLAY", ":0")
                display_spec = disp if disp.endswith(".0") else f"{disp}.0"
                dest.unlink(missing_ok=True)
                r4 = run_cmd(
                    [
                        "ffmpeg",
                        "-y",
                        "-loglevel",
                        "error",
                        "-f",
                        "x11grab",
                        "-video_size",
                        f"{w}x{h}",
                        "-i",
                        display_spec,
                        "-frames:v",
                        "1",
                        str(dest),
                    ],
                    timeout=15,
                )
                if r4.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
                    return dest.resolve()
                errors.append(f"ffmpeg x11grab rc={r4.returncode}")
            else:
                errors.append("ffmpeg: display geometry unavailable")
        except DeskAPIError as exc:
            errors.append(f"ffmpeg: {exc}")

    detail = "; ".join(errors) if errors else "no backend attempted"
    raise DeskAPIError(
        500,
        "Screenshot failed (portal → gnome-screenshot → grim → ffmpeg). "
        f"{detail}. Install: sudo apt install gnome-screenshot grim "
        "ffmpeg python3-dbus python3-gi",
    )


def crop_image(src: Path, region: dict[str, int], dest: Path) -> Path:
    """Crop ``src`` to ``region`` ``{x,y,w,h}`` with Pillow, clamping bounds.

    Args:
        src (Path): Source image path.
        region (dict[str, int]): Crop box with keys ``x``, ``y``, ``w``, ``h``.
        dest (Path): Destination path for the cropped PNG.

    Returns:
        Path: ``dest`` when crop succeeded, otherwise ``src`` unchanged when the
        clamped box is empty / outside the image.

    Raises:
        DeskAPIError: When Pillow cannot open ``src``.

    Examples:
        >>> from PIL import Image as PILImage
        >>> tmp = Path("/tmp/desk-proxy-shots/_crop_src.png")
        >>> PILImage.new("RGB", (100, 80), "red").save(tmp)
        >>> out = crop_image(tmp, {"x": 10, "y": 10, "w": 40, "h": 30}, Path("/tmp/desk-proxy-shots/_crop_dst.png"))
        >>> out.name
        '_crop_dst.png'
        >>> crop_image(tmp, {"x": 999, "y": 999, "w": 10, "h": 10}, Path("/tmp/desk-proxy-shots/_crop_oob.png")) == tmp
        True
    """
    from PIL import Image as PILImage

    src = Path(src)
    dest = Path(dest)
    try:
        with PILImage.open(src) as img:
            box = (
                int(region["x"]),
                int(region["y"]),
                int(region["x"]) + int(region["w"]),
                int(region["y"]) + int(region["h"]),
            )
            box = (
                max(0, box[0]),
                max(0, box[1]),
                min(img.width, box[2]),
                min(img.height, box[3]),
            )
            if box[2] <= box[0] or box[3] <= box[1]:
                return src
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.crop(box).save(dest)
    except OSError as exc:
        raise DeskAPIError(500, f"Cannot crop image {src}: {exc}") from exc
    return dest.resolve()


def screenshot(
    window_name: str | None = None,
    region: dict[str, int] | None = None,
    shot_dir: Path | None = None,
) -> dict[str, Any]:
    """Take a screenshot, optionally cropped to a window or explicit region.

    Args:
        window_name (str | None): Partial window title / class for auto-crop
            via xdotool geometry (XWayland-visible windows).
        region (dict[str, int] | None): Explicit ``{x,y,w,h}`` crop. Wins over
            ``window_name`` when both are set.
        shot_dir (Path | None): Override output directory; defaults to
            ``config.shot_dir()``.

    Returns:
        dict[str, Any]: Keys ``path`` (str), optional ``geometry``, optional
        ``warning`` when a named window was not found.

    Raises:
        DeskAPIError: When capture fails entirely.

    Examples:
        >>> data = screenshot()  # doctest: +SKIP
        >>> data["path"].endswith(".png")
        True
        >>> screenshot(region={"x": 0, "y": 0, "w": 100, "h": 80})["geometry"]["w"]  # doctest: +SKIP
        100
    """
    base = Path(shot_dir) if shot_dir is not None else config_shot_dir()
    base.mkdir(parents=True, exist_ok=True)
    stamp = _ts()
    full_path = base / f"full_{stamp}.png"
    final_path = base / f"shot_{stamp}.png"

    take_screenshot(full_path)

    crop: dict[str, int] | None = None
    geom_used: dict[str, int] | None = None
    warning: str | None = None

    if region:
        crop = {k: int(region[k]) for k in ("x", "y", "w", "h")}
        geom_used = crop
    elif window_name:
        win = get_window(window_name)
        if win:
            pad = 4
            crop = {
                "x": max(0, int(win["x"]) - pad),
                "y": max(0, int(win["y"]) - pad),
                "w": int(win["width"]) + pad * 2,
                "h": int(win["height"]) + pad * 2,
            }
            geom_used = {
                "x": int(win["x"]),
                "y": int(win["y"]),
                "w": int(win["width"]),
                "h": int(win["height"]),
            }
        else:
            warning = (
                f"Window '{window_name}' not found via xdotool — "
                "full screenshot returned"
            )

    if crop:
        crop_image(full_path, crop, final_path)
        full_path.unlink(missing_ok=True)
        out = final_path
    else:
        out = full_path

    result: dict[str, Any] = {"path": str(out.resolve())}
    if geom_used:
        result["geometry"] = geom_used
    if warning:
        result["warning"] = warning
    return result
