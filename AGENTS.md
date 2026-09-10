# AGENTS.md — desk-proxy

Project context for all AI agents working in this repository.

## KpihX Mantras

Exploration: Problem First, Why before How, Visualization  
Architecture: 0 Trust, 100% Control, 0 Magic, 100% Transparency, 0 Hardcoding, 100% Flexibility

## Project Overview

Purpose: Desktop automation **proxy** (non-MCP CLI) — screenshot, input, windows, OCR, clipboard, HITL  
Stack: Python (uv), Typer, Pydantic, Rich, Pillow + system tools (xdotool, ydotool, wtype, tesseract, portals)  
Status: Production v0.1.1 — 24 actions  
Binary: `desk-proxy` → `do` + `admin`  
ADN: tick-proxy / mail-proxy / tg-proxy  
Ancestor: `$HOME/Work/AI/MCPs/desk_mcp` (`desk-mcp` MCP, archived as content reference)  
Path: `$HOME/KpihX-Labs/Proxies/desk-proxy/`

## Architecture Rules

* stdout = pure JSON envelope `{meta,data}` · stderr = logs / HITL / autosave
* Flat kebab actions only · registry is the sole catalog (`actions/registry.py`)
* Docstrings ARE `--help` — Parameters + Examples with ≥3 `→` (raw / chain still ≥3)
* HITL: `window-close`, `clipboard-set`, `chain`, `raw` — 600s fail-closed · `DESK_PROXY_NO_BROWSER=1` for CI
* No Docker · no MCP · no systemd daemon · no `Wants=graphical-session.target`
* Never teach agents to read source for usage — use `desk-proxy do <action> --help`
* Config: defaults in `src/desk_proxy/config.py` · durable `~/.config/desk-proxy/config.json` · **no `.env`** (zero secrets) · shots/autosave under `/tmp/`
* Inject DISPLAY/WAYLAND/DBUS when the agent shell is headless

## Core files

| Path | Role |
|------|------|
| `CONTRACT.md` | Architecture + action tables + MCP drop list |
| `src/desk_proxy/config.py` | Defaults + load/save `config.json` (no `.env`) |
| `src/desk_proxy/cli.py` | Typer `do` / `admin` |
| `src/desk_proxy/actions/*` | Domain handlers + REGISTRY |
| `src/desk_proxy/api/*` | Backends (screenshot, input, windows, ocr, clipboard) |
| `src/desk_proxy/hitl.py` | Local review UI |
| `tests/test_registry.py` | Action count + HITL set + docstring gate |

## Evolution Rules

* New action: add ONE `ActionDef` in a domain module · bump smoke assert · update CONTRACT table
* Breaking change: bump version + CHANGELOG entry
* `make check` before claiming done
* Skill updates (`k-desk` etc.): propose only unless KπX grants skill write in-session

## Sibling proxies

Prefer specialized tools when they fit: `browser-proxy` (web), `mail-proxy`, `whats-proxy`, `tg-proxy`, `tick-proxy`.
