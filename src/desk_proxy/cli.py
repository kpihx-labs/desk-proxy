"""
desk-proxy CLI — Single binary, two namespaces.

Usage:
    desk-proxy admin doctor|status|setup|purge
    desk-proxy do <action> [payload] [--output-file/-o]

Admin is ALWAYS JSON (no --format / -o). ``do`` prints pure ADN JSON on stdout.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel, ValidationError

from . import __version__, admin
from .actions.base import ActionDef
from .actions.registry import REGISTRY, by_group
from .config import autosave_dir
from .display import console, print_error, print_json
from .doc import get_compact_help, get_full_help
from .exceptions import DeskAPIError, DeskProxyError
from .hitl import request_approval
from .logger import setup_logging
from .models import Output, OutputMeta, ok, rejected

app = typer.Typer(
    name="desk-proxy",
    help="Desktop automation proxy — screenshots, input, OCR, windows, HITL.",
    add_completion=False,
)
app_admin = typer.Typer(
    help="Admin commands: doctor, status, setup, purge (ALWAYS JSON).",
    add_completion=False,
)
app_do = typer.Typer(
    help="RPC actions: screen-info, mouse-click, window-list, …",
    add_completion=False,
    add_help_option=False,
)
app.add_typer(app_admin, name="admin")
app.add_typer(app_do, name="do")


def parse_payload(payload_str: str | None) -> dict[str, Any]:
    """Convert a JSON string or a file path into a dict.

    Args:
        payload_str (str | None): Inline JSON, or a path to a ``.json`` file.

    Returns:
        dict[str, Any]: The parsed payload (empty when nothing was given).

    Raises:
        DeskProxyError: When the string is neither valid JSON nor an existing file.

    Examples:
        >>> parse_payload('{"x":10,"y":20}')
        {'x': 10, 'y': 20}
        >>> parse_payload(None)
        {}
        >>> parse_payload('')
        {}
    """
    if not payload_str:
        return {}
    try:
        data = json.loads(payload_str)
    except json.JSONDecodeError:
        path = Path(payload_str)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            raise DeskProxyError(
                f"Invalid JSON or file not found: {payload_str}"
            ) from None
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise DeskProxyError("Payload must be a JSON object")
    return data


def _autosave(action: str, result: dict[str, Any]) -> Path:
    """Write the envelope under the configured autosave dir and return the path.

    Args:
        action (str): Action name used in the file name.
        result (dict[str, Any]): Envelope to persist.

    Returns:
        Path: The file that was written.

    Examples:
        >>> p = _autosave("screen-info", {"meta": {}, "data": {}})
        >>> p.name.startswith("screen-info_") and p.suffix == ".json"
        True
        >>> p.is_file()
        True
    """
    base = autosave_dir()
    path = base / f"{action}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return path


def _print_error_envelope(message: str) -> None:
    """Print an ADN error envelope to stdout and exit 1.

    Args:
        message (str): Human-readable error text.

    Returns:
        None: Always raises ``typer.Exit(1)`` after printing.

    Examples:
        >>> _print_error_envelope("boom")  # doctest: +SKIP
        {"meta": {"status": "error", ...}, "data": null}
        >>> callable(_print_error_envelope)
        True
    """
    envelope = Output(
        meta=OutputMeta(status="error", comment=str(message), edited=False),
        data=None,
    ).model_dump()
    print_json(data=envelope)
    raise typer.Exit(1)


def _execute(
    action: ActionDef,
    payload_raw: str | None,
    output_file: str | None,
) -> None:
    """Run one action end-to-end: validate → HITL → call → print JSON.

    Args:
        action (ActionDef): Registry entry to run.
        payload_raw (str | None): Inline JSON or a file path.
        output_file (str | None): Optional path to also write the envelope.

    Returns:
        None: Exits 1 on error or HITL rejection.

    Examples:
        >>> _execute(REGISTRY["screen-info"], "{}", None)  # doctest: +SKIP
        {"meta": {"status": "ok", ...}, "data": {"width": 1920, ...}}
        >>> _execute(REGISTRY["wait"], '{"seconds":0}', None)  # doctest: +SKIP
        {"meta": {"status": "ok", ...}, "data": {"slept": 0.0}}
    """
    params = parse_payload(payload_raw)
    meta_status, comment, edited = "ok", "", False

    if action.hitl:
        response = request_approval(action.name, params)
        if response.status == "rejected":
            print_json(data=rejected(response.comment, response.edited))
            raise typer.Exit(1)
        if isinstance(response.payload, dict):
            params = response.payload
        meta_status, comment, edited = "approved", response.comment, response.edited

    try:
        if action.payload is not None:
            validated: BaseModel | dict[str, Any] = action.payload(**params)
        else:
            validated = params
    except ValidationError as exc:
        _print_error_envelope(f"Validation error: {exc}")

    try:
        data = action.handler(validated)
    except (DeskProxyError, DeskAPIError) as exc:
        _print_error_envelope(str(exc))

    result = ok(data, edited=edited, comment=comment, status=meta_status)  # type: ignore[arg-type]
    autosave_path = _autosave(action.name, result)
    if output_file:
        out = Path(output_file)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"📄 Written to: {out}", file=sys.stderr)
    else:
        print(f"💾 Autosave: {autosave_path}", file=sys.stderr)
    print_json(data=result)


def _version_callback(value: bool) -> None:
    """Print the version and exit when ``--version`` is passed.

    Args:
        value (bool): True when ``--version`` was passed.

    Returns:
        None

    Examples:
        >>> _version_callback(False)
        >>> _version_callback(True)  # doctest: +SKIP
        desk-proxy v0.1.0
    """
    if value:
        console.print(f"desk-proxy v{__version__}")
        raise typer.Exit()


def _do_help_callback(value: bool = True) -> None:
    """Print the compact catalog of all actions, grouped.

    Args:
        value (bool): True when help was requested.

    Returns:
        None

    Examples:
        >>> _do_help_callback(False)
        >>> callable(_do_help_callback)
        True
    """
    if not value:
        return
    console.print(
        "[bold yellow]For detailed information and examples on a specific"
        " action, run:[/bold yellow]"
    )
    console.print("  [bold]desk-proxy do <action> --help[/bold]\n")
    for group, actions in by_group().items():
        console.print(f"[bold magenta]── {group} ──[/bold magenta]")
        for action in actions:
            console.print(f"[bold cyan]{action.name}[/bold cyan]")
            console.print(get_compact_help(action.handler))
            console.print()
    raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True
    ),
) -> None:
    """Root callback — configures stderr logging.

    Args:
        version (bool | None): Handled by the eager ``--version`` callback.

    Returns:
        None

    Examples:
        >>> main(None)
        >>> callable(main)
        True
    """
    setup_logging()


def _refuse_admin_format(
    output_file: str | None = None,
    fmt: str | None = None,
) -> None:
    """Refuse ``--format`` / ``-o`` on admin commands (exit 2).

    Args:
        output_file (str | None): Value of ``-o/--output-file`` if somehow set.
        fmt (str | None): Value of ``-f/--format`` if somehow set.

    Returns:
        None

    Examples:
        >>> _refuse_admin_format(None, None)
        >>> _refuse_admin_format("x.json", None)  # doctest: +SKIP
    """
    if output_file is not None or fmt is not None:
        print_error("admin commands are ALWAYS JSON — do not pass --format/-f or -o")
        raise typer.Exit(2)


@app_admin.callback()
def admin_main(
    output_file: str | None = typer.Option(None, "--output-file", "-o", hidden=True),
    fmt: str | None = typer.Option(None, "--format", "-f", hidden=True),
) -> None:
    """Admin callback — reject non-JSON output options.

    Args:
        output_file (str | None): Forbidden on admin.
        fmt (str | None): Forbidden on admin.

    Returns:
        None

    Examples:
        >>> admin_main(None, None)
        >>> callable(admin_main)
        True
    """
    _refuse_admin_format(output_file, fmt)


@app_admin.command("doctor")
def admin_doctor() -> None:
    """Probe tools and config (ALWAYS JSON)."""
    try:
        print_json(data=ok(admin.doctor()))
    except (DeskProxyError, DeskAPIError) as exc:
        _print_error_envelope(str(exc))


@app_admin.command("status")
def admin_status() -> None:
    """Screen + config + tools snapshot (ALWAYS JSON)."""
    try:
        print_json(data=ok(admin.status()))
    except (DeskProxyError, DeskAPIError) as exc:
        _print_error_envelope(str(exc))


@app_admin.command("setup")
def admin_setup() -> None:
    """Create config dir and write default config.json (ALWAYS JSON)."""
    try:
        print_json(data=ok(admin.setup()))
    except (DeskProxyError, DeskAPIError) as exc:
        _print_error_envelope(str(exc))


@app_admin.command("purge")
def admin_purge() -> None:
    """Remove config-dir contents (ALWAYS JSON)."""
    try:
        print_json(data=ok(admin.purge()))
    except (DeskProxyError, DeskAPIError) as exc:
        _print_error_envelope(str(exc))


OUTPUT_FILE_OPT = typer.Option(
    None, "--output-file", "-o", help="Write the envelope to a file."
)


@app_do.callback(invoke_without_command=True)
def do_main(
    ctx: typer.Context,
    show_help: bool = typer.Option(
        False, "--help", "-h", help="Show help.", hidden=True
    ),
) -> None:
    """``do`` callback — prints the catalog when no action is given.

    Args:
        ctx (typer.Context): Typer context.
        show_help (bool): True when ``-h/--help`` was passed.

    Returns:
        None

    Examples:
        >>> # desk-proxy do            → prints the 24-action catalog
        >>> # desk-proxy do screen-info → runs the action
        >>> callable(do_main)
        True
    """
    if show_help or ctx.invoked_subcommand is None:
        _do_help_callback(True)


def _register(action: ActionDef) -> None:
    """Attach one registry entry as a Typer command under ``do``.

    Args:
        action (ActionDef): The action to expose.

    Returns:
        None

    Examples:
        >>> _register(REGISTRY["screen-info"])  # doctest: +SKIP
        >>> callable(_register)
        True
    """

    @app_do.command(action.name, help=get_full_help(action.handler))
    def _command(
        payload: str | None = typer.Argument(None, help="JSON payload or file path."),
        output_file: str | None = OUTPUT_FILE_OPT,
    ) -> None:
        try:
            _execute(action, payload, output_file)
        except (DeskProxyError, DeskAPIError) as exc:
            _print_error_envelope(str(exc))


for _action in REGISTRY.values():
    _register(_action)
