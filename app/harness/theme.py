"""Light/dark palettes and Windows system detection (Aero accent, app dark mode)."""
import sys

from .settings import load_settings, save_settings

MODES = ("system", "light", "dark")
MODE_LABELS = {"system": "Sistema", "light": "Claro", "dark": "Escuro"}

# Values inside one palette must be distinct: the GUI maps widget colours back to roles by value.
DARK = {"bg": "#1c2128", "side": "#161b22", "panel": "#252c35", "fg": "#e6edf3",
        "dim": "#a7b3c2", "accent": "#3164b6", "link": "#80b7ff", "code": "#0d1117", "sel": "#344253",
        "edge": "#465366", "err": "#ff9b96", "danger": "#a73436"}
LIGHT = {"bg": "#ffffff", "side": "#f4f6f9", "panel": "#f8fafc", "fg": "#1f2937",
         "dim": "#526174", "accent": "#315da8", "link": "#315da9", "code": "#edf2f7", "sel": "#dce8f6",
         "edge": "#c2cfdd", "err": "#a72d2d", "danger": "#a33136"}


def load_mode():
    m = load_settings().get("theme")
    return m if m in MODES else "system"


def save_mode(mode):
    settings = load_settings()
    settings["theme"] = mode
    save_settings(settings)


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
    """Darken the accent until it has at least 4.5:1 contrast with white."""
    def luminance(values):
        linear = []
        for value in values:
            c = value / 255.0
            linear.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    while luminance((r, g, b)) > (1.05 / 4.5 - 0.05):
        r, g, b = int(r * 0.95), int(g * 0.95), int(b * 0.95)
    return "#%02x%02x%02x" % (r, g, b)


def blend(base, accent, amount):
    a = [int(base[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(accent[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x * (1 - amount) + y * amount) for x, y in zip(a, b))


def contrast(first, second):
    def luminance(color):
        values = [int(color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
        values = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in values]
        return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def resolve(mode):
    """Returns (palette, is_dark) for a mode, with the Aero accent applied when available."""
    dark = system_prefers_dark() if mode == "system" else mode == "dark"
    pal = dict(DARK if dark else LIGHT)
    accent = aero_accent()
    if accent and accent not in pal.values():
        pal["accent"] = accent
        pal["side"] = blend(pal["side"], accent, 0.07 if dark else 0.04)
        pal["sel"] = blend(pal["sel"], accent, 0.12 if dark else 0.09)
        pal["edge"] = blend(pal["edge"], accent, 0.22)
        link = accent
        while contrast(link, pal["bg"]) < 4.5:
            link = blend(link, "#ffffff" if dark else "#000000", 0.08)
        if link not in pal.values():
            pal["link"] = link
    return pal, dark
