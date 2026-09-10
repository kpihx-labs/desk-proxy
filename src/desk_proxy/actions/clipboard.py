"""Clipboard group — get and set system clipboard text."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from desk_proxy.api import clipboard as clip_api

from .base import action_def, require_approval


class ClipboardSetPayload(BaseModel):
    """Text to place on the clipboard."""

    text: str = Field(..., description="Clipboard contents to write")


def clipboard_get(_payload: Any = None) -> dict[str, Any]:
    """Read the current clipboard text (wl-paste or xclip).

    Parameters:
        - (none): Payload may be null or ``{}``.

    Examples:
        - Read clipboard:
            `desk-proxy do clipboard-get '{}'`
            → {"text": "hello from clipboard"}

        - Empty clipboard:
            `desk-proxy do clipboard-get`
            → {"text": ""}

        - After a set:
            `desk-proxy do clipboard-get '{}'`
            → {"text": "desk-proxy-probe"}
    """
    return {"text": clip_api.clipboard_get()}


@require_approval()
def clipboard_set(p: ClipboardSetPayload) -> dict[str, Any]:
    """Write text to the clipboard. HITL required.

    Parameters:
        - text (str): Text to place on the clipboard (required).

    Examples:
        - Set a short string:
            `desk-proxy do clipboard-set '{"text":"hello"}'`
            → {"text": "hello"}

        - Clear clipboard:
            `desk-proxy do clipboard-set '{"text":""}'`
            → {"text": ""}

        - HITL rejection:
            `desk-proxy do clipboard-set '{"text":"secret"}'`
            → {"meta": {"status": "rejected", "comment": "not now"}, "data": null}
    """
    return {"text": clip_api.clipboard_set(p.text)}


ACTIONS = [
    action_def("clipboard-get", None, clipboard_get, group="Clipboard"),
    action_def("clipboard-set", ClipboardSetPayload, clipboard_set, group="Clipboard"),
]
