"""Discover registered Windows browsers without changing system defaults."""
import os
import re
import subprocess
import sys
import webbrowser


def installed_browsers():
    if sys.platform != "win32":
        return []
    import winreg
    result = {}
    path = r"Software\Clients\StartMenuInternet"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                root = winreg.OpenKey(hive, path, 0, winreg.KEY_READ | view)
            except OSError:
                continue
            with root:
                for i in range(winreg.QueryInfoKey(root)[0]):
                    name = winreg.EnumKey(root, i)
                    try:
                        with winreg.OpenKey(root, name) as key:
                            display = winreg.QueryValueEx(key, "")[0] or name
                        with winreg.OpenKey(root, name + r"\shell\open\command") as key:
                            command = os.path.expandvars(winreg.QueryValueEx(key, "")[0])
                    except OSError:
                        continue
                    match = re.match(r'\s*"([^"]+\.exe)"|\s*(.+?\.exe)(?:\s|$)', command, re.I)
                    if match:
                        executable = match.group(1) or match.group(2)
                        if os.path.isfile(executable):
                            result[os.path.normcase(executable)] = (display, executable)
    return sorted(result.values(), key=lambda item: item[0].lower())


def open_url(url, executable=""):
    if executable:
        if not os.path.isfile(executable):
            raise OSError("Navegador configurado não foi encontrado: %s" % executable)
        subprocess.Popen([executable, url], stdin=subprocess.DEVNULL)
    elif not webbrowser.open(url):
        raise OSError("Não foi possível abrir o navegador padrão.")
