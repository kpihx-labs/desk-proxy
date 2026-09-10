"""Registry integrity — the anti-drift gate for the 24 actions."""

from __future__ import annotations

import re

from desk_proxy.actions.registry import ACTION_COUNT, REGISTRY, by_group

HITL = {"window-close", "clipboard-set", "chain", "raw"}


def test_action_count() -> None:
    """Registry must expose exactly 24 actions."""
    assert len(REGISTRY) == 24
    assert ACTION_COUNT == 24
    assert len(REGISTRY) == len(set(REGISTRY))


def test_unique_kebab_names() -> None:
    """Every action name is unique kebab-case."""
    for name in REGISTRY:
        assert name == name.lower()
        assert " " not in name and "_" not in name
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name), name


def test_hitl_set() -> None:
    """HITL policy matches the explicit review set."""
    declared = {n for n, a in REGISTRY.items() if a.hitl}
    assert declared == HITL
    for name in HITL:
        assert getattr(REGISTRY[name].handler, "__require_approval__", False)


def test_every_handler_has_parameters_examples_and_arrows() -> None:
    """Every handler docstring carries Parameters, Examples, and ≥3 → lines."""
    for name, action in REGISTRY.items():
        doc = action.handler.__doc__ or ""
        assert doc.strip(), f"{name} has no docstring"
        assert "Parameters:" in doc, f"{name} docstring lacks Parameters:"
        assert "Examples:" in doc, f"{name} docstring lacks Examples:"
        arrows = [line for line in doc.splitlines() if "→" in line]
        assert len(arrows) >= 3, f"{name} needs ≥3 → examples, got {len(arrows)}"


def test_groups_cover_every_action() -> None:
    """by_group partitions the full registry without loss."""
    assert sum(len(v) for v in by_group().values()) == ACTION_COUNT
    assert set(by_group()) == {
        "Screen",
        "Windows",
        "Mouse",
        "Keyboard",
        "Clipboard",
        "Control",
    }
