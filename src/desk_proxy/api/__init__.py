"""
Public desktop-automation API for desk-proxy.

Backends live in sibling modules; this package re-exports the stable surface
used by ``actions/`` handlers and tests.
"""

from desk_proxy.api.clipboard import clipboard_get, clipboard_set
from desk_proxy.api.input import (
    click,
    drag,
    get_mouse,
    move_mouse,
    press_key,
    resolve_input_backend,
    scroll,
    type_text,
)
from desk_proxy.api.ocr import find_text, ocr_image
from desk_proxy.api.run import run_cmd
from desk_proxy.api.screen import screen_info
from desk_proxy.api.screenshot import crop_image, screenshot, take_screenshot
from desk_proxy.api.windows import (
    close_window,
    focus_window,
    get_window,
    list_windows,
    minimize_window,
    move_window,
    resize_window,
)

__all__ = [
    "click",
    "clipboard_get",
    "clipboard_set",
    "close_window",
    "crop_image",
    "drag",
    "find_text",
    "focus_window",
    "get_mouse",
    "get_window",
    "list_windows",
    "minimize_window",
    "move_mouse",
    "move_window",
    "ocr_image",
    "press_key",
    "resize_window",
    "resolve_input_backend",
    "run_cmd",
    "screen_info",
    "screenshot",
    "scroll",
    "take_screenshot",
    "type_text",
]
