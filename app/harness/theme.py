"""Light/dark palettes and Windows system detection (Aero accent, app dark mode)."""
import json
import os
import sys

from .auth import CONFIG_DIR

SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
MODES = ("system", "light", "dark")
MODE_LABELS = {"system": "Sistema", "light": "Claro", "dark": "Escuro"}

# Values inside one palette must be distinct: the GUI maps widget colours back to roles by value.
DARK = {"bg": "#212121", "side": "#171717", "panel": "#2f2f2f", "fg": "#ececec",
        "dim": "#9b9b9b", "accent": "#10a37f", "code": "#0d0d0d", "sel": "#343541",
        "err": "#ff6b6b", "danger": "#c0392b"}
LIGHT = {"bg": "#ffffff", "side": "#f0f0f0", "panel": "#e6e6e6", "fg": "#1f1f1f",
         "dim": "#6b6b6b", "accent": "#10a37f", "code": "#f7f7f7", "sel": "#d4dff0",
         "err": "#c0392b", "danger": "#d9534f"}


def load_mode():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            m = json.load(f).get("theme")
        return m if m in MODES else "system"
    except (IOError, ValueError):
        return "system"


def save_mode(mode):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"theme": mode}, f)
    except IOError:
        pass


def system_prefers_dark():
    """Windows 10+ app dark mode; Windows 7 has none, so it is always light."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except (OSError, ImportError):
        return False


def aero_accent():
    """Aero glass colour as '#rrggbb' when DWM composition is on, else None."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        dwm = ctypes.WinDLL("dwmapi")
        enabled = ctypes.c_int(0)
        if dwm.DwmIsCompositionEnabled(ctypes.byref(enabled)) != 0 or not enabled.value:
            return None
        color, opaque = ctypes.c_uint32(0), ctypes.c_int(0)
        if dwm.DwmGetColorizationColor(ctypes.byref(color), ctypes.byref(opaque)) != 0:
            return None
        c = color.value
        return readable((c >> 16) & 255, (c >> 8) & 255, c & 255)
    except (OSError, AttributeError):
        return None


def readable(r, g, b):
    """Darkens pale glass tints so white button text stays legible."""
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    if lum > 0.5:
        k = 0.5 / lum
        r, g, b = int(r * k), int(g * k), int(b * k)
    return "#%02x%02x%02x" % (r, g, b)


def resolve(mode):
    """Returns (palette, is_dark) for a mode, with the Aero accent applied when available."""
    dark = system_prefers_dark() if mode == "system" else mode == "dark"
    pal = dict(DARK if dark else LIGHT)
    accent = aero_accent()
    if accent and accent not in pal.values():
        pal["accent"] = accent
    return pal, dark
