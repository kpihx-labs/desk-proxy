"""Screen group — geometry, screenshot, OCR, text find."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from desk_proxy.api.ocr import find_text, ocr_image
from desk_proxy.api.screen import screen_info as api_screen_info
from desk_proxy.api.screenshot import screenshot as api_screenshot

from .base import action_def


class Region(BaseModel):
    """Pixel crop box ``{x, y, w, h}``."""

    x: int = Field(..., description="Left edge in pixels")
    y: int = Field(..., description="Top edge in pixels")
    w: int = Field(..., description="Width in pixels")
    h: int = Field(..., description="Height in pixels")


class ScreenShotPayload(BaseModel):
    """Optional window or region crop for a screenshot."""

    window_name: str | None = Field(None, description="Partial window title / class")
    region: Region | None = Field(None, description="Explicit {x,y,w,h} crop")


class ScreenOcrPayload(BaseModel):
    """Screenshot + OCR options."""

    window_name: str | None = Field(None, description="Partial window title / class")
    region: Region | None = Field(None, description="Explicit {x,y,w,h} crop")
    lang: str | None = Field(None, description="Tesseract langs, e.g. eng+fra")
    path: str | None = Field(
        None,
        description="Existing image path — skip capture when set",
    )


class ScreenFindPayload(BaseModel):
    """OCR text search on a fresh (optionally cropped) screenshot."""

    query: str = Field(..., description="Case-insensitive substring to find")
    window_name: str | None = Field(None, description="Partial window title / class")
    region: Region | None = Field(None, description="Explicit {x,y,w,h} crop")
    lang: str | None = Field(None, description="Tesseract langs override")
    path: str | None = Field(
        None,
        description="Existing image path — skip capture when set",
    )


def screen_info(_payload: Any = None) -> dict[str, Any]:
    """Return display geometry, session type, and backend availability flags.

    Parameters:
        - (none): Payload may be null or ``{}``.

    Examples:
        - Full display probe:
            `desk-proxy do screen-info '{}'`
            → {"width": 1920, "height": 1080, "session_type": "wayland", "xdotool": true}

        - Empty payload accepted:
            `desk-proxy do screen-info`
            → {"width": 1920, "height": 1080, "display": ":0", "grim": true}

        - Headless agent still gets flags:
            `desk-proxy do screen-info '{}'`
            → {"width": 0, "height": 0, "tesseract": true, "wl_clipboard": true}
    """
    return api_screen_info()


def screen_shot(p: ScreenShotPayload) -> dict[str, Any]:
    """Capture a PNG screenshot, optionally cropped to a window or region.

    Parameters:
        - window_name (str|null): Partial title / class for auto-crop via xdotool.
        - region (object|null): Explicit ``{x,y,w,h}`` crop (wins over window_name).

    Examples:
        - Full screen:
            `desk-proxy do screen-shot '{}'`
            → {"path": "/tmp/desk-proxy-shots/full_143022_12.png"}

        - Named window crop:
            `desk-proxy do screen-shot '{"window_name":"Firefox"}'`
            → {"path": "/tmp/desk-proxy-shots/shot_143022_12.png", "geometry": {"x": 100, "y": 80, "w": 1200, "h": 800}}

        - Explicit region:
            `desk-proxy do screen-shot '{"region":{"x":0,"y":0,"w":400,"h":300}}'`
            → {"path": "/tmp/desk-proxy-shots/shot_143055_01.png", "geometry": {"x": 0, "y": 0, "w": 400, "h": 300}}
    """
    region = p.region.model_dump() if p.region else None
    return api_screenshot(window_name=p.window_name, region=region)


def screen_ocr(p: ScreenOcrPayload) -> dict[str, Any]:
    """Take a screenshot then run tesseract OCR on it.

    Parameters:
        - window_name (str|null): Partial title / class for auto-crop.
        - region (object|null): Explicit ``{x,y,w,h}`` crop.
        - lang (str|null): Tesseract language packs (default from config).
        - path (str|null): Existing image path — skip capture when set.

    Examples:
        - Full-screen OCR:
            `desk-proxy do screen-ocr '{}'`
            → {"text": "File Edit View", "lines": [{"text": "File", "x": 12, "y": 8, "w": 28, "h": 14, "conf": 92.0}], "path": "/tmp/desk-proxy-shots/full_143100_00.png"}

        - Window OCR in English:
            `desk-proxy do screen-ocr '{"window_name":"Terminal","lang":"eng"}'`
            → {"text": "kpihx@ubuntu:~$", "lines": [], "path": "/tmp/desk-proxy-shots/shot_143101_00.png"}

        - Existing file (no capture):
            `desk-proxy do screen-ocr '{"path":"/tmp/desk-proxy-shots/ocr_probe.png","lang":"eng"}'`
            → {"text": "DESKPROXY_FIND_ME", "lines": [{"text": "DESKPROXY_FIND_ME", "x": 40, "y": 70, "w": 220, "h": 24, "conf": 90.0}], "path": "/tmp/desk-proxy-shots/ocr_probe.png"}
    """
    if p.path:
        data = ocr_image(Path(p.path), lang=p.lang)
        data["path"] = str(Path(p.path).resolve())
        return data
    region = p.region.model_dump() if p.region else None
    shot = api_screenshot(window_name=p.window_name, region=region)
    data = ocr_image(Path(str(shot["path"])), lang=p.lang)
    data["path"] = shot["path"]
    if "geometry" in shot:
        data["geometry"] = shot["geometry"]
    if "warning" in shot:
        data["warning"] = shot["warning"]
    return data


def screen_find(p: ScreenFindPayload) -> dict[str, Any]:
    """Find text on screen via screenshot + OCR word boxes.

    Parameters:
        - query (str): Case-insensitive substring to match (required).
        - window_name (str|null): Partial title / class for auto-crop.
        - region (object|null): Explicit ``{x,y,w,h}`` crop.
        - lang (str|null): Tesseract language packs override.
        - path (str|null): Existing image path — skip capture when set.

    Examples:
        - Search full screen:
            `desk-proxy do screen-find '{"query":"Save"}'`
            → {"matches": [{"text": "Save", "x": 420, "y": 310, "w": 40, "h": 16, "conf": 91.0, "path": "/tmp/desk-proxy-shots/full_143200_00.png"}], "query": "Save"}

        - Search an existing PNG:
            `desk-proxy do screen-find '{"query":"DESKPROXY","path":"/tmp/desk-proxy-shots/ocr_probe.png"}'`
            → {"matches": [{"text": "DESKPROXY_FIND_ME", "x": 150, "y": 82, "w": 220, "h": 24, "conf": 88.0, "path": "/tmp/desk-proxy-shots/ocr_probe.png"}], "query": "DESKPROXY", "path": "/tmp/desk-proxy-shots/ocr_probe.png"}

        - Region-scoped search:
            `desk-proxy do screen-find '{"query":"OK","region":{"x":0,"y":0,"w":300,"h":100},"lang":"eng"}'`
            → {"matches": [{"text": "OK", "x": 48, "y": 22, "w": 20, "h": 14, "conf": 96.0, "path": "/tmp/desk-proxy-shots/shot_143201_00.png"}], "query": "OK"}
    """
    if p.path:
        img = str(Path(p.path).resolve())
        matches = find_text(p.query, path=img, screenshot_first=False, lang=p.lang)
        return {"matches": matches, "query": p.query, "path": img}
    region = p.region.model_dump() if p.region else None
    shot = api_screenshot(window_name=p.window_name, region=region)
    matches = find_text(
        p.query,
        path=str(shot["path"]),
        screenshot_first=False,
        lang=p.lang,
    )
    return {"matches": matches, "query": p.query, "path": shot["path"]}


ACTIONS = [
    action_def("screen-info", None, screen_info, group="Screen"),
    action_def("screen-shot", ScreenShotPayload, screen_shot, group="Screen"),
    action_def("screen-ocr", ScreenOcrPayload, screen_ocr, group="Screen"),
    action_def("screen-find", ScreenFindPayload, screen_find, group="Screen"),
]
