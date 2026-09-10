"""
Action framework — declarative approval policy for desk-proxy.

Same ADN contract as tick/mail: an ``ActionDef`` carries the action name, its
colocated Pydantic payload model and the handler. ``@require_approval`` derives
HITL policy from the handler — ``cli.py`` has no separate policy table.

Handler signature (local desktop — no remote client)::

    handler(payload) -> dict
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class ActionDef:
    """One ``do`` action: name, payload model, handler and its policies.

    Attributes:
        name (str): The flat kebab-case action name, e.g. ``shot-take``.
        payload (type[BaseModel] | None): Pydantic model validating the payload
            (None when the action takes no payload).
        handler (Callable): ``handler(payload) -> dict`` — no client argument.
        hitl (bool): Derived from the handler's ``@require_approval`` declaration.
        group (str): Catalog group used by ``do --help``, e.g. ``"Screen"``.
        aliases (tuple[str, ...]): Optional command aliases.

    Examples:
        >>> ActionDef("shot-take", None, lambda p: {}, group="Screen").name
        'shot-take'
        >>> ActionDef("shot-take", None, lambda p: {}).hitl
        False
    """

    name: str
    payload: type[BaseModel] | None
    handler: Callable[..., Any]
    hitl: bool = False
    group: str = "Misc"
    aliases: tuple[str, ...] = field(default_factory=tuple)


def require_approval() -> Callable:
    """Declare a handler's mandatory centralized HITL review policy.

    Returns:
        Callable: A decorator carrying auditable review metadata.

    Examples:
        >>> @require_approval()
        ... def click(payload): return {}
        >>> click.__require_approval__
        True
        >>> click.__review_mode__
        'default'
        >>> callable(click)
        True
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper.__require_approval__ = True  # type: ignore[attr-defined]
        wrapper.__review_mode__ = "default"  # type: ignore[attr-defined]
        return wrapper

    return decorator


def action_def(
    name: str,
    payload: type[BaseModel] | None,
    handler: Callable[..., Any],
    *,
    group: str = "Misc",
    aliases: tuple[str, ...] = (),
) -> ActionDef:
    """Build an action definition from visible handler decorators.

    Args:
        name (str): Flat registered action name.
        payload (type[BaseModel] | None): Pydantic payload model.
        handler (Callable[..., Any]): Decorated implementation
            (``handler(payload) -> dict``).
        group (str): Help catalog group.
        aliases (tuple[str, ...]): Optional command aliases.

    Returns:
        ActionDef: HITL policy derived from ``__require_approval__``.

    Examples:
        >>> @require_approval()
        ... def type_text(payload): return {}
        >>> action_def("type-text", None, type_text).hitl
        True
        >>> action_def("shot-take", None, lambda p: {}).hitl
        False
        >>> action_def("raw", None, lambda p: {}, group="Escape hatch").group
        'Escape hatch'
    """
    return ActionDef(
        name=name,
        payload=payload,
        handler=handler,
        hitl=bool(getattr(handler, "__require_approval__", False)),
        group=group,
        aliases=aliases,
    )
