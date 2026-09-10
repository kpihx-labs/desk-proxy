# desk-proxy

> **0 Trust – 100% Control | 0 Magic – 100% Transparency | 0 Hardcoding – 100% Flexibility**

Desktop automation **proxy** for AI agents — screenshot, mouse, keyboard, windows, OCR, clipboard, HITL.
Non-MCP CLI on the ADN of `tick-proxy` / `mail-proxy` / `tg-proxy`. Refonte of [`desk-mcp`](https://github.com/KpihX/desk-mcp).

```
Agent (bash) ──► desk-proxy do <action> ['{json}']
                      ├── screen-*     portal / grim / ffmpeg + tesseract
                      ├── mouse-*      xdotool → ydotool
                      ├── keyboard-*   wtype → xdotool → ydotool
                      ├── window-*     xdotool + wmctrl
                      ├── clipboard-*  wl-clipboard / xclip
                      └── chain / raw  HITL-gated composition / escape hatch
```

---

## Install

### Prerequisites (Ubuntu)

```bash
sudo apt install xdotool wmctrl ydotool wtype tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra \
  gnome-screenshot grim wl-clipboard xclip ffmpeg python3-gi python3-dbus
```

### Editable

```bash
cd ~/KpihX-Labs/Proxies/desk-proxy
uv tool install --editable . --force
desk-proxy admin setup
desk-proxy admin doctor
```

### Display env (agent shells)

Agent terminals often lack GUI env. Export before `do`:

```bash
export DISPLAY=:0
export WAYLAND_DISPLAY=wayland-0
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$UID/bus
export XDG_RUNTIME_DIR=/run/user/$UID
```

`desk-proxy` also auto-fills sane defaults and discovers Mutter `XAUTHORITY`.

---

## Quick start

```bash
desk-proxy do screen-info '{}'
desk-proxy do screen-shot '{}'
desk-proxy do window-list '{}'
desk-proxy do mouse-move '{"x":400,"y":300}'
desk-proxy do mouse-click '{"x":400,"y":300,"button":"left","clicks":1}'
desk-proxy do keyboard-type '{"text":"hello from desk-proxy"}'
desk-proxy do screen-find '{"query":"Save"}'
desk-proxy do --help
desk-proxy do screen-shot --help
```

HITL actions (`window-close`, `clipboard-set`, `chain`, `raw`) open a local review URL (600s fail-closed). Set `DESK_PROXY_NO_BROWSER=1` to print the URL only.

---

## Actions (24)

| Group | Actions |
|-------|---------|
| Screen | `screen-info` `screen-shot` `screen-ocr` `screen-find` |
| Windows | `window-list` `window-get` `window-focus` `window-activate` `window-close` `window-move` `window-resize` `window-minimize` |
| Mouse | `mouse-get` `mouse-move` `mouse-click` `mouse-drag` `mouse-scroll` |
| Keyboard | `keyboard-type` `keyboard-key` |
| Clipboard | `clipboard-get` `clipboard-set` |
| Control | `wait` `chain` `raw` |

Full tables, backends, and MCP→proxy mapping: **[CONTRACT.md](./CONTRACT.md)**.

---

## Admin

```bash
desk-proxy admin doctor   # tools + issues
desk-proxy admin status   # screen + config + display env
desk-proxy admin setup    # ~/.config/desk-proxy/
desk-proxy admin purge    # wipe config dir
```

---

## Config

Defaults live in **`src/desk_proxy/config.py`**. Durable overrides:

```
~/.config/desk-proxy/config.json
```

created by `desk-proxy admin setup`. **No `.env` / `.env.example`** — there are no secrets.
Optional process env overrides: `DESK_SHOT_DIR`, `DESK_INPUT_BACKEND`, `DESK_OCR_LANG`,
`DESK_HITL_TIMEOUT`, `DESK_AUTOSAVE_DIR`, `DESK_CONFIG_DIR`.

---

## Make

```bash
make check        # smoke + ruff + pyright + pytest
make uv-link      # editable install
```

---

## vs browser-proxy

| | desk-proxy | browser-proxy |
|--|------------|---------------|
| Target | Whole desktop (any app) | Edge + CDP + extension |
| When | Native apps, GNOME UI, OCR click loops | Web pages, bookmarks, tabs |
| HITL | Local review page (600s) | In-page overlay (~20s) |

Prefer the specialized proxy when it covers the task (`proxies-reflex`).
