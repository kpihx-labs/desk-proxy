"""
Rich output helpers for desk-proxy.

Stdout JSON remains the machine contract; these helpers are for human-facing
admin / debug surfaces that print to the shared Rich console.
"""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_json(data: Any) -> None:
    """Print ``data`` as pretty-printed JSON via Rich.

    Args:
        data (Any): Any JSON-serialisable value (dict, list, scalar).

    Returns:
        None: Writes to the Rich console and returns nothing.

    Examples:
        >>> print_json({"path": "/tmp/shot.png"})  # doctest: +SKIP
        >>> print_json([1, 2, 3])  # doctest: +SKIP
    """
    console.print_json(data=data)


def print_table(data: list[dict] | dict) -> None:
    """Print a dict or list-of-dicts as a Rich table.

    Args:
        data (list[dict] | dict): A mapping becomes Key/Value columns; a
            non-empty list of dicts uses the first row's keys as columns.

    Returns:
        None: Writes to the Rich console and returns nothing.

    Examples:
        >>> print_table({"backend": "xdotool", "ocr_lang": "eng+fra"})  # doctest: +SKIP
        >>> print_table([{"name": "shot-take", "hitl": False}])  # doctest: +SKIP
    """
    if isinstance(data, dict):
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Key", style="dim")
        table.add_column("Value")
        for k, v in data.items():
            table.add_row(str(k), str(v))
        console.print(table)
    elif isinstance(data, list) and data:
        keys = list(data[0].keys()) if isinstance(data[0], dict) else ["Value"]
        table = Table(show_header=True, header_style="bold cyan")
        for k in keys:
            table.add_column(str(k))
        for item in data:
            if isinstance(item, dict):
                table.add_row(*[str(item.get(k, "")) for k in keys])
            else:
                table.add_row(str(item))
        console.print(table)
    else:
        console.print(data)


def print_error(message: str) -> None:
    """Print a red error line to the console.

    Args:
        message (str): Human-readable error text (no secrets).

    Returns:
        None: Writes to the Rich console and returns nothing.

    Examples:
        >>> print_error("xdotool not found")  # doctest: +SKIP
        >>> print_error("HITL rejected")  # doctest: +SKIP
    """
    console.print(f"[bold red]❌ {message}[/bold red]")


def print_meta(meta: dict) -> None:
    """Print the ``meta`` half of an ADN envelope as a coloured panel.

    Args:
        meta (dict): Envelope meta with optional ``status``, ``comment``,
            and ``edited`` keys.

    Returns:
        None: Writes to the Rich console and returns nothing.

    Examples:
        >>> print_meta({"status": "ok", "comment": "", "edited": False})  # doctest: +SKIP
        >>> print_meta({"status": "rejected", "comment": "wrong window"})  # doctest: +SKIP
    """
    status = meta.get("status", "ok")
    color = "green" if status in ("ok", "approved") else "red"
    console.print(
        Panel(
            f"[bold {color}]Status:[/] {status}\n"
            f"[bold]Comment:[/] {meta.get('comment', '') or '(empty)'}\n"
            f"[bold]Edited:[/] {'✅ Yes' if meta.get('edited') else '❌ No'}",
            title="[bold blue]Output Meta[/]",
            border_style=color,
        )
    )
