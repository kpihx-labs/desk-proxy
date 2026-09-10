"""Config / display_env unit checks."""

from desk_proxy.config import default_config, display_env, load_config


def test_display_env_keys() -> None:
    env = display_env()
    for key in (
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "DBUS_SESSION_BUS_ADDRESS",
        "XDG_RUNTIME_DIR",
    ):
        assert key in env
        assert env[key]


def test_default_config_keys() -> None:
    cfg = default_config()
    assert set(cfg) == {
        "shot_dir",
        "input_backend",
        "ocr_lang",
        "hitl_timeout",
        "autosave_dir",
    }
    assert cfg["input_backend"] == "auto"


def test_load_config_merges_defaults() -> None:
    cfg = load_config()
    assert cfg["input_backend"] in ("auto", "xdotool", "ydotool")
    assert isinstance(cfg["hitl_timeout"], int)
