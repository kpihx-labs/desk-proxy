# desk-proxy — Architecture Contract

**Version:** 0.1.1 · **Actions:** 24 · **ADN:** tick-proxy / mail-proxy / tg-proxy  
**Ancestor:** `desk-mcp` v0.2.1 (MCP → non-MCP CLI refonte)  
**Stack:** Python ≥3.12 · uv · Typer · Pydantic · Rich · Pillow · system tools (xdotool / ydotool / wtype / tesseract / portals)

> Authoritative architecture contract. Code + `tests/test_registry.py` are the action-count source of truth.

---

## Mission

Give AI agents **eyes and hands on the real Linux desktop** — without MCP plumbing.

`desk-mcp` proved the gap (screenshot + xdotool). `desk-proxy` is the full proxy-family rewrite:

| Pillar | Rule |
|--------|------|
| Single binary, two namespaces | `desk-proxy do <action>` · `desk-proxy admin …` |
| Flat kebab actions | ONE level after `do` — `screen-shot`, not `screenshot` / `do screen shot` |
| `meta` + `data` envelope | Every response, always |
| Docstring = docs | `--help` is the only usage surface; ≥3 real `→` examples per action |
| HITL web UI | Destructive / escape-hatch ops need human approval (600s fail-closed) |
| Autosave | Every `do` under `/tmp/desk-proxy-autosave/` |
| No Docker · no MCP · no daemon | Fire-and-forget per invocation (same as mail/tick) |

### Mantras

- **0 Hardcoding · 100% Flexibility** — backends auto-selected; paths via env/`config.json`
- **0 Magic · 100% Transparency** — every action names its backend (`xdotool`, `portal`, `ffmpeg`, …)
- **0 Trust · 100% Control** — HITL on close / clipboard-set / chain / raw; stdout never carries secrets

---

## Envelope

```json
{
  "meta": { "status": "ok|approved|rejected|error", "comment": "", "edited": false },
  "data": { }
}
```

- **stdout** = pure JSON · **stderr** = logs / HITL / autosave paths
- Exit: success `0` · reject/error `1` · admin misuse of `--format`/`-o` → `2`

---

## Beyond desk-mcp

| desk-mcp (10 MCP tools) | desk-proxy (24 `do` actions) |
|-------------------------|------------------------------|
| `screenshot` | `screen-shot` + multi-backend chain (portal → gnome-screenshot → grim → ffmpeg) |
| `get_windows` / `get_screen` | `window-list` / `window-get` / `screen-info` |
| `click` / `double_click` / `right_click` | unified `mouse-click` (`button` + `clicks`) |
| `move_mouse` | `mouse-move` + `mouse-get` |
| `type_text` / `key` / `scroll` | `keyboard-type` / `keyboard-key` / `mouse-scroll` |
| — | `mouse-drag` |
| — | `window-focus` / `window-activate` / `window-close` (HITL) / `window-move` / `window-resize` / `window-minimize` |
| — | `screen-ocr` / `screen-find` (tesseract TSV → clickable centers) |
| — | `clipboard-get` / `clipboard-set` (HITL) |
| — | `wait` / `chain` (HITL) / `raw` escape hatch (HITL) |
| MCP stdio `serve` | **CLI only** — agents call via bash (`proxies-reflex`) |
| No HITL | HITL web UI (mail/tick ADN) |
| No admin | `admin doctor\|status\|setup\|purge` |

### Research deltas folded in (2026)

- **Wayland input reality:** xdotool (XWayland) primary; ydotool / wtype fallbacks; absolute coords via DISPLAY discovery + Mutter `XAUTHORITY`
- **Screenshot resilience:** portal often denied for non-interactive callers → gnome-screenshot → grim → ffmpeg x11grab
- **OCR as coordinate oracle:** tesseract TSV lines with centers for `screen-find` → `mouse-click` loops
- **No graphical-session systemd unit:** fire-and-forget CLI — never pull `graphical-session.target` (lesson `ISS-20260910-001` / whats-proxy)

---

## Action catalog (24)

### Screen (4)

| Action | HITL | Backend |
|--------|------|---------|
| `screen-info` | no | xdotool geometry + tool probes |
| `screen-shot` | no | portal / gnome-screenshot / grim / ffmpeg |
| `screen-ocr` | no | screenshot + tesseract |
| `screen-find` | no | OCR match → `{text,x,y,w,h,conf}` |

### Windows (8)

| Action | HITL | Backend |
|--------|------|---------|
| `window-list` | no | xdotool (+ wmctrl enrich) |
| `window-get` | no | xdotool |
| `window-focus` | no | xdotool windowactivate |
| `window-activate` | no | alias of focus |
| `window-close` | **yes** | wmctrl / xdotool |
| `window-move` | no | xdotool / wmctrl |
| `window-resize` | no | xdotool / wmctrl |
| `window-minimize` | no | xdotool / wmctrl |

### Mouse (5)

| Action | HITL | Backend |
|--------|------|---------|
| `mouse-get` | no | xdotool getmouselocation |
| `mouse-move` | no | xdotool / ydotool |
| `mouse-click` | no | xdotool / ydotool |
| `mouse-drag` | no | xdotool / ydotool |
| `mouse-scroll` | no | xdotool / ydotool |

### Keyboard (2)

| Action | HITL | Backend |
|--------|------|---------|
| `keyboard-type` | no | wtype → xdotool → ydotool |
| `keyboard-key` | no | xdotool / ydotool |

### Clipboard (2)

| Action | HITL | Backend |
|--------|------|---------|
| `clipboard-get` | no | wl-paste / xclip |
| `clipboard-set` | **yes** | wl-copy / xclip |

### Control (3)

| Action | HITL | Backend |
|--------|------|---------|
| `wait` | no | sleep |
| `chain` | **yes** | sequential registry dispatch |
| `raw` | **yes** | xdotool / ydotool / wmctrl / shell argv |

---

## Admin

| Command | Role |
|---------|------|
| `admin doctor` | Tool + portal + config health (`ok` + `issues[]`) |
| `admin status` | Screen + config + tools + resolved display env |
| `admin setup` | `~/.config/desk-proxy/` + default `config.json` |
| `admin purge` | Wipe config dir (shots under `/tmp` kept) |

Admin is **always JSON**. `--format` / `-o` → exit 2.

---

## Config

Source of truth: **`src/desk_proxy/config.py`** (defaults + load/save) + durable JSON:

```
~/.config/desk-proxy/
  config.json     # shot_dir, input_backend, ocr_lang, hitl_timeout, autosave_dir
```

No `.env` / `.env.example` — desk-proxy has **zero secrets**. Optional process env
overrides only (same keys as JSON): `DESK_SHOT_DIR`, `DESK_INPUT_BACKEND`,
`DESK_OCR_LANG`, `DESK_HITL_TIMEOUT`, `DESK_AUTOSAVE_DIR`, `DESK_CONFIG_DIR`.

Display injection for headless agent shells: `DISPLAY`, `WAYLAND_DISPLAY`,
`DBUS_SESSION_BUS_ADDRESS`, `XDG_RUNTIME_DIR`, auto-discovered `XAUTHORITY` (Mutter).

CI / no-browser HITL: `DESK_PROXY_NO_BROWSER=1`.

---

## What is dropped from desk-mcp

| Dropped | Why |
|--------|-----|
| FastMCP `serve` / stdio tools | CLI *is* the interface |
| MCP host env registration tables | Agents use bash + `--help` |
| Separate `desk-mcp status` Rich TUI as primary | `admin status` JSON ADN |
| Single-backend assumption (portal-only / xdotool-only) | Explicit fallback chains |

---

## Quality gate

```
make check  →  smoke (REGISTRY==24) + ruff + py_compile + pyright + pytest
```

Install: `uv tool install --editable .` → `~/.local/bin/desk-proxy`.
