"""Optional docstring overlap checks for the action catalog."""

from desk_proxy.actions.registry import REGISTRY
from desk_proxy.doc import get_compact_help, get_full_help


def test_compact_help_strips_examples() -> None:
    for name, action in REGISTRY.items():
        compact = get_compact_help(action.handler)
        assert "Examples:" not in compact, name
        assert compact, name


def test_full_help_wraps_arrow_json() -> None:
    doc = get_full_help(REGISTRY["screen-info"].handler)
    assert "meta" in doc
    assert "status" in doc
