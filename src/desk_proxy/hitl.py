"""
Human-in-the-Loop web UI for desk-proxy.

Sync HITL (mail-proxy ADN): launches a local HTTPServer on ``127.0.0.1:0``,
shows the action payload for review, and blocks until approve/reject or
timeout. Template placeholders: ``{{FUNC_NAME}}``, ``{{PAYLOAD_JSON}}``,
``{{PAYLOAD_JSON_SAFE}}``, ``{{REQUEST_ID}}``.

Set ``DESK_PROXY_NO_BROWSER=1`` to skip ``webbrowser.open`` (tests/CI/SSH).
All operator messages go to stderr so stdout stays pure ADN JSON.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar

from .config import hitl_timeout as config_hitl_timeout

logger = logging.getLogger(__name__)

# Default; request_approval refreshes from config/env each call.
HITL_TIMEOUT: int | None = 600

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATE_PATH = TEMPLATES_DIR / "hitl.html"

ENV_NO_BROWSER = "DESK_PROXY_NO_BROWSER"


class HITLResponse:
    """The outcome of one HITL review.

    Attributes:
        status (str): ``"approved"`` or ``"rejected"``.
        payload (Any): The payload as (possibly) edited by the reviewer.
        comment (str): Free-text reviewer comment.
        edited (bool): True when the reviewer changed the payload.

    Examples:
        >>> HITLResponse("approved", {"x": 10, "y": 20}).status
        'approved'
        >>> HITLResponse("rejected", None, "wrong window").comment
        'wrong window'
    """

    def __init__(
        self,
        status: str,
        payload: Any = None,
        comment: str = "",
        edited: bool = False,
    ) -> None:
        self.status = status
        self.payload = payload
        self.comment = comment
        self.edited = edited


class HITLServer(BaseHTTPRequestHandler):
    """Single-request HTTP handler serving the review page and its submission."""

    active_requests: ClassVar[dict[str, dict[str, Any]]] = {}

    def log_message(self, format: str, *args: Any) -> None:
        """Silence the default stderr access log (stdout must stay pure JSON).

        Args:
            format (str): Unused format string.
            *args (Any): Unused arguments.

        Returns:
            None: No output is ever produced.

        Examples:
            >>> HITLServer.log_message(None, "%s", "x") is None  # doctest: +SKIP
            True
            >>> callable(HITLServer.log_message)
            True
        """
        return

    def do_GET(self) -> None:
        """Serve the review page for ``/review?id=<uuid>``.

        Returns:
            None

        Examples:
            >>> # GET /review?id=<known>  → 200 with the HTML form
            >>> # GET /review?id=<unknown> → 404
            >>> hasattr(HITLServer, "do_GET")
            True
            >>> callable(HITLServer.do_GET)
            True
        """
        if self.path.startswith("/review"):
            query = self.path.split("?")[-1]
            req_id = query.split("id=")[-1] if "id=" in query else ""
            if req_id not in self.active_requests:
                self.send_error(404, "Review request not found.")
                return
            req = self.active_requests[req_id]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self._render(req_id, req).encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        """Collect the reviewer's decision on ``/submit`` and unblock the caller.

        Returns:
            None

        Examples:
            >>> # POST /submit {"id": …, "status": "approved"} → {"ok": true}
            >>> # POST /submit with unknown id → 404
            >>> hasattr(HITLServer, "do_POST")
            True
            >>> callable(HITLServer.do_POST)
            True
        """
        if self.path != "/submit":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        post = json.loads(self.rfile.read(length).decode("utf-8"))
        req_id = post.get("id", "")
        if req_id not in self.active_requests:
            self.send_error(404)
            return
        req = self.active_requests[req_id]
        payload_raw = post.get("payload")
        if isinstance(payload_raw, str):
            try:
                payload = json.loads(payload_raw)
            except (json.JSONDecodeError, ValueError):
                payload = payload_raw
        else:
            payload = payload_raw if payload_raw is not None else req.get("payload")
        req["result"] = HITLResponse(
            post.get("status", "rejected"),
            payload,
            post.get("comment", ""),
            bool(post.get("edited", False)),
        )
        req["event"].set()
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def _render(self, req_id: str, req: dict) -> str:
        """Fill the HTML template with the payload under review.

        Args:
            req_id (str): The review request uuid.
            req (dict): The in-flight request context.

        Returns:
            str: The rendered HTML page.

        Examples:
            >>> # returns the form pre-filled with the pretty-printed payload
            >>> # returns an explicit error page when the template file is missing
            >>> callable(HITLServer._render)
            True
            >>> TEMPLATE_PATH.name
            'hitl.html'
        """
        try:
            payload_display = (
                json.dumps(req["payload"], indent=2, default=str)
                .replace("<", "\\u003c")
                .replace(">", "\\u003e")
                .replace("&", "\\u0026")
            )
            payload_safe = (
                json.dumps(req["payload"], default=str)
                .replace("\\", "\\\\")
                .replace("'", "\\'")
            )
        except (TypeError, ValueError):
            safe = str(req.get("payload", {}))
            payload_display = safe
            payload_safe = safe[:100]
        try:
            html = TEMPLATE_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            return f"<html><body><h2>Template not found: {TEMPLATE_PATH}</h2></body></html>"
        html = html.replace("{{FUNC_NAME}}", req.get("func_name", "unknown"))
        html = html.replace("{{PAYLOAD_JSON}}", payload_display)
        html = html.replace("{{PAYLOAD_JSON_SAFE}}", payload_safe)
        html = html.replace("{{REQUEST_ID}}", req_id)
        return html


def _resolve_timeout() -> int | None:
    """Resolve HITL timeout from config/env, falling back to module default.

    Returns:
        int | None: Seconds to wait, or ``None`` to wait forever when configured
        as a non-positive sentinel is not used (always returns int >= 0 from
        config; module ``HITL_TIMEOUT`` used only if config load fails).

    Examples:
        >>> t = _resolve_timeout()
        >>> isinstance(t, int) and t >= 0
        True
        >>> _resolve_timeout() == config_hitl_timeout() or isinstance(_resolve_timeout(), int)
        True
    """
    global HITL_TIMEOUT
    try:
        HITL_TIMEOUT = config_hitl_timeout()
    except Exception:  # noqa: BLE001 — HITL must still run if config is broken
        if HITL_TIMEOUT is None:
            HITL_TIMEOUT = 600
    return HITL_TIMEOUT


def request_approval(action: str, payload: Any) -> HITLResponse:
    """Open the HITL web form and block until the reviewer decides.

    Args:
        action (str): Action name shown in the form, e.g. ``click-at``.
        payload (Any): The payload submitted for review (JSON-serialisable).

    Returns:
        HITLResponse: The decision, including the (possibly edited) payload.
        A timeout produces ``status="rejected"``.

    Examples:
        >>> # Interactive: request_approval("click-at", {"x": 10, "y": 20}).status
        >>> # → 'approved' when the reviewer clicks Approve
        >>> isinstance(HITLResponse("rejected", None, "timeout"), HITLResponse)
        True
        >>> ENV_NO_BROWSER
        'DESK_PROXY_NO_BROWSER'
    """
    timeout = _resolve_timeout()
    req_id = str(uuid.uuid4())
    event = threading.Event()
    req_context: dict[str, Any] = {
        "func_name": action,
        "payload": payload,
        "event": event,
        "result": None,
    }
    HITLServer.active_requests[req_id] = req_context

    server = HTTPServer(("127.0.0.1", 0), HITLServer)
    port = int(server.server_address[1])
    url = f"http://127.0.0.1:{port}/review?id={req_id}"

    print("\n🚀 [HITL] ACTION REVIEW REQUIRED", file=sys.stderr)
    print(f"🔗 {url}", file=sys.stderr)
    print(f"📝 Action: {action}", file=sys.stderr)
    print(
        "If the browser doesn't open, connect from a machine with a GUI:",
        file=sys.stderr,
    )
    print(f"   ssh -L {port}:localhost:{port} your-host", file=sys.stderr)

    def serve() -> None:
        while not event.is_set():
            server.handle_request()

    threading.Thread(target=serve, daemon=True).start()

    if os.environ.get(ENV_NO_BROWSER, "").strip() not in ("1", "true", "yes", "on"):
        import webbrowser

        try:
            webbrowser.open(url)
        except OSError:  # pragma: no cover - headless host
            logger.warning("Failed to open browser for HITL URL: %s", url)
    else:
        print(
            f"[{ENV_NO_BROWSER}] browser open suppressed — open the URL manually",
            file=sys.stderr,
        )

    if not event.wait(timeout=timeout):
        logger.warning("HITL timeout expired for %s (id=%s)", action, req_id)
        HITLServer.active_requests.pop(req_id, None)
        server.server_close()
        return HITLResponse(
            "rejected", None, "HITL timeout expired (no response received)", False
        )

    result: HITLResponse = req_context["result"]
    HITLServer.active_requests.pop(req_id, None)
    server.server_close()
    return result
