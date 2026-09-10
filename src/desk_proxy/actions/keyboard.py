"""Keyboard group — type text and press key chords."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from desk_proxy.api import input as input_api

from .base import action_def


class KeyboardTypePayload(BaseModel):
    """Unicode text injection at the current focus."""

    text: str = Field(..., description="Text to type")
    delay_ms: int = Field(12, description="Inter-key delay in milliseconds", ge=0)


class KeyboardKeyPayload(BaseModel):
    """Single key or chord (xdotool-style)."""

    combo: str = Field(..., description="Key or chord, e.g. Return, ctrl+c, alt+F4")


def keyboard_type(p: KeyboardTypePayload) -> dict[str, Any]:
    """Type Unicode text at the current keyboard focus.

    Parameters:
        - text (str): Text to type (required).
        - delay_ms (int): Inter-key delay in ms (default 12).

    Examples:
        - Type a short string:
            `desk-proxy do keyboard-type '{"text":"hello"}'`
            → {"typed": "hello", "backend": "wtype", "delay_ms": 12}

        - Slower typing:
            `desk-proxy do keyboard-type '{"text":"slow","delay_ms":40}'`
            → {"typed": "slow", "backend": "xdotool", "delay_ms": 40}

        - Long text is preview-truncated:
            `desk-proxy do keyboard-type '{"text":"abcdefghijklmnopqrstuvwxyz0123456789EXTRA"}'`
            → {"typed": "abcdefghijklmnopqrstuvwxyz0123456789EXTR...", "backend": "wtype", "delay_ms": 12}
    """
    return input_api.type_text(p.text, delay_ms=p.delay_ms)


def keyboard_key(p: KeyboardKeyPayload) -> dict[str, Any]:
    """Press a key or chord (``ctrl+c``, ``Return``, ``alt+F4``, …).

    Parameters:
        - combo (str): xdotool-style combo string (required).

    Examples:
        - Escape:
            `desk-proxy do keyboard-key '{"combo":"Escape"}'`
            → {"combo": "Escape", "backend": "xdotool"}

        - Copy chord:
            `desk-proxy do keyboard-key '{"combo":"ctrl+c"}'`
            → {"combo": "ctrl+c", "backend": "xdotool"}

        - Enter:
            `desk-proxy do keyboard-key '{"combo":"Return"}'`
            → {"combo": "Return", "backend": "wtype"}
    """
    return input_api.press_key(p.combo)


ACTIONS = [
    action_def("keyboard-type", KeyboardTypePayload, keyboard_type, group="Keyboard"),
    action_def("keyboard-key", KeyboardKeyPayload, keyboard_key, group="Keyboard"),
]
