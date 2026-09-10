"""
The action registry — ``name → ActionDef``, built from every domain module.

Adding an action means adding ONE ``ActionDef`` to its domain module; ``cli.py``
builds its commands from here. Duplicate names raise at import time.
"""

from __future__ import annotations

from . import clipboard, control, keyboard, mouse, screen, windows
from .base import ActionDef

_MODULES = (
    screen,
    windows,
    mouse,
    keyboard,
    clipboard,
    control,
)

REGISTRY: dict[str, ActionDef] = {}
for _module in _MODULES:
    for _action in _module.ACTIONS:
        if _action.name in REGISTRY:
            raise RuntimeError(f"Duplicate action name in registry: {_action.name}")
        REGISTRY[_action.name] = _action

ACTION_COUNT = 24


def get(name: str) -> ActionDef:
    """Return one action definition by name.

    Args:
        name (str): The flat kebab-case action name.

    Returns:
        ActionDef: The matching definition.

    Raises:
        KeyError: When the action does not exist.

    Examples:
        >>> get("screen-info").group
        'Screen'
        >>> get("raw").hitl
        True
        >>> get("mouse-click").name
        'mouse-click'
    """
    return REGISTRY[name]


def by_group() -> dict[str, list[ActionDef]]:
    """Group every action by catalog group, preserving registration order.

    Returns:
        dict[str, list[ActionDef]]: ``{group_name: [ActionDef, …]}``.

    Examples:
        >>> sorted(by_group())
        ['Clipboard', 'Control', 'Keyboard', 'Mouse', 'Screen', 'Windows']
        >>> [a.name for a in by_group()["Screen"]]
        ['screen-info', 'screen-shot', 'screen-ocr', 'screen-find']
        >>> sum(len(v) for v in by_group().values()) == ACTION_COUNT
        True
    """
    groups: dict[str, list[ActionDef]] = {}
    for action in REGISTRY.values():
        groups.setdefault(action.group, []).append(action)
    return groups


if len(REGISTRY) != ACTION_COUNT:
    raise RuntimeError(
        f"Expected {ACTION_COUNT} actions, got {len(REGISTRY)}: {sorted(REGISTRY)}"
    )
