# TODO — desk-proxy

## Next

- [ ] Optional AT-SPI accessibility tree actions (`a11y-list`, `a11y-click`) when `python3-pyatspi` is available — semantic clicks without OCR.
- [ ] `screen-shot` option `scale` for downscaled overview frames (computer-use pattern).
- [ ] Persist RemoteDesktop portal restore token if/when libei path is added (portal-use / Open-ALO style).
- [ ] Dual remotes `github` + `gitlab` under `kpihx-labs/desk-proxy` + first `make push`.
- [ ] Propose `k-desk` skill (Bash(desk-proxy *)) after KπX validation.

## Known limitations

- Pure Wayland-native windows may be missing from `window-list` (xdotool/XWayland limit) — use `screen-find` / region shots.
- `ydotoold` must be running for ydotool fallback; default path uses xdotool when DISPLAY works.
- Portal screenshot often returns denied for non-interactive callers; ffmpeg/gnome-screenshot cover the gap.
- HITL opens a browser; headless CI must set `DESK_PROXY_NO_BROWSER=1` and not exercise HITL actions.

## Post-0.1

- [ ] Live E2E script `scripts/live.py` (OCR find → click) gated outside `make check`.
- [ ] Benchmark portal vs ffmpeg latency on kpihx-ubuntu.
