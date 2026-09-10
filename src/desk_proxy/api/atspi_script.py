"""
AT-SPI helper script source — executed by system ``/usr/bin/python3``.

desk-proxy's uv venv has no PyGObject; GNOME a11y lives in system Python.
This module only exports the script text — never import ``gi`` here.
"""

from __future__ import annotations

# Printed as JSON list of window/frame records on stdout.
ATSPI_LIST_WINDOWS_SCRIPT = r"""
import json
import sys

try:
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
except Exception as exc:
    print(json.dumps({"ok": False, "error": f"Atspi unavailable: {exc}"}))
    sys.exit(0)

Atspi.init()
desktop = Atspi.get_desktop(0)
windows = []
apps = []

for i in range(desktop.get_child_count()):
    app = desktop.get_child_at_index(i)
    if app is None:
        continue
    app_name = app.get_name() or f"app-{i}"
    apps.append(app_name)
    n = app.get_child_count()
    for j in range(n):
        child = app.get_child_at_index(j)
        if child is None:
            continue
        try:
            role = child.get_role_name() or ""
        except Exception:
            role = ""
        try:
            name = child.get_name() or ""
        except Exception:
            name = ""
        extents = None
        try:
            comp = child.get_component_iface()
            if comp is not None:
                e = comp.get_extents(Atspi.CoordType.SCREEN)
                extents = {
                    "x": int(e.x),
                    "y": int(e.y),
                    "width": int(e.width),
                    "height": int(e.height),
                }
        except Exception:
            extents = None
        if role not in ("frame", "window", "dialog"):
            if not (extents and extents["width"] > 80 and extents["height"] > 80):
                continue
        if extents is None:
            extents = {"x": 0, "y": 0, "width": 0, "height": 0}
        # Stable synthetic id: hash of app+name+geometry (AT-SPI has no X wid)
        key = f"{app_name}|{name}|{extents['x']}|{extents['y']}|{extents['width']}|{extents['height']}"
        wid = abs(hash(key)) % (10**12)
        windows.append(
            {
                "id": wid,
                "name": name or app_name,
                "app": app_name,
                "role": role,
                "x": extents["x"],
                "y": extents["y"],
                "width": extents["width"],
                "height": extents["height"],
                "backend": "atspi",
            }
        )

print(json.dumps({"ok": True, "windows": windows, "apps": apps}))
"""

GNOME_SCREEN_SIZE_SCRIPT = r"""
import json
import sys

try:
    import dbus
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
    sys.exit(0)

try:
    bus = dbus.SessionBus()
    obj = bus.get_object(
        "org.gnome.Shell.Introspect", "/org/gnome/Shell/Introspect"
    )
    props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
    size = props.Get("org.gnome.Shell.Introspect", "ScreenSize")
    w, h = int(size[0]), int(size[1])
    print(json.dumps({"ok": True, "width": w, "height": h, "backend": "gnome-introspect"}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
"""

PORTAL_PERMISSION_SCRIPT = r"""
import json
import sys

try:
    import dbus
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
    sys.exit(0)

try:
    bus = dbus.SessionBus()
    obj = bus.get_object(
        "org.freedesktop.impl.portal.PermissionStore",
        "/org/freedesktop/impl/portal/PermissionStore",
    )
    store = dbus.Interface(obj, "org.freedesktop.impl.portal.PermissionStore")
    # Ensure non-interactive Screenshot portal works for host/agent callers.
    for app in ("", "desk-proxy"):
        store.SetPermission("screenshot", True, "screenshot", app, ["yes"])
    print(json.dumps({"ok": True, "granted": ["", "desk-proxy"]}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
"""
