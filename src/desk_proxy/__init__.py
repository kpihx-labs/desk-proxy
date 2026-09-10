"""
desk-proxy: Non-MCP CLI proxy for Linux desktop automation.

Screenshots, keyboard/mouse input, OCR, and HITL review — ADN envelope
compatible with tick-proxy / mail-proxy / tg-proxy.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("desk-proxy")
except PackageNotFoundError:
    __version__ = "0.0.0"
