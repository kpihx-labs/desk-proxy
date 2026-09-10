# CHANGELOG — desk-proxy

## [0.1.2] — 2026-09-10

### Fixed

- **Wayland window-list root cause:** AT-SPI frames via system `/usr/bin/python3` (PyGObject) — no more XWayland-only stubs. Records include `app`, `role`, `backend`.
- **Screenshot portal denied:** auto-grant PermissionStore `screenshot` for host/`desk-proxy` (same root cause as waveterm-only `yes`); reject near-black ffmpeg X11grab frames instead of returning junk ~37KB blacks.
- **Geometry / session:** prefer GNOME Introspect `ScreenSize`; `display_env()` always injects DISPLAY/XAUTHORITY so agents need **zero** manual `export`; `session_type` reports `wayland` when WAYLAND_DISPLAY is injected.
- `admin setup` now also grants Screenshot portal permission.

### Changed

- Version bump 0.1.1 → 0.1.2.

## [0.1.1] — 2026-09-10


### Changed

- Removed useless `.env.example` — desk-proxy has **zero secrets**; settings are non-secret desktop preferences.
- Config contract clarified: source of truth = `config.py` defaults + durable `~/.config/desk-proxy/config.json` (kept); optional `DESK_*` process env overrides only — never a `.env` file.
- Docs updated: CONTRACT / README / AGENTS / `.gitignore` no longer advertise `.env.example`.
- Dual remotes live: `github` `kpihx-labs/desk-proxy` + `gitlab` `kpihx-labs/proxies/desk-proxy` (topics `proxy,desktop,cli`); `make push` wired.

## [0.1.0] — 2026-09-10

### Added

- Initial production release: **24** flat kebab `do` actions on tick/mail ADN (`meta`+`data`, HITL, autosave, docstring `--help`).
- Screen: `screen-info`, `screen-shot`, `screen-ocr`, `screen-find` (tesseract TSV centers).
- Windows: list/get/focus/activate/close/move/resize/minimize (xdotool + wmctrl).
- Mouse: get/move/click/drag/scroll with xdotool → ydotool fallback.
- Keyboard: type/key with wtype → xdotool → ydotool.
- Clipboard: get/set (wl-clipboard / xclip); set is HITL-gated.
- Control: `wait`, HITL `chain`, HITL `raw` escape hatch.
- Admin: `doctor`, `status`, `setup`, `purge` (always JSON).
- Screenshot backend chain beyond desk-mcp: XDG portal → gnome-screenshot → grim → ffmpeg x11grab.
- Display env recovery for agent shells (DISPLAY/WAYLAND/DBUS + Mutter `XAUTHORITY`).
- `make check` green: smoke (REGISTRY==24) + ruff + pyright + 16 pytest.
- Live-verified on kpihx-ubuntu Wayland: screen-info/shot/ocr/find(path), mouse move/click/drag, keyboard-key, clipboard-get, window-list, admin doctor/status/setup.
- Hardening: `screen-find`/`screen-ocr` honor `path` (no spurious recapture); xdotool moves drop hanging `--sync`; drag uses a single argv chain.

### Refonte from desk-mcp

- Dropped FastMCP stdio transport; agents call the CLI via bash.
- Renamed MCP verbs to domain-first kebab (`screenshot` → `screen-shot`, …).
- Added OCR, drag, window management, clipboard, chain, raw, HITL, admin ADN.
