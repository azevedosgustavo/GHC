"""GHC installer / uninstaller (Tkinter, stdlib only; Python 3.8, Windows 7+).

Per-user install: no administrator rights needed (shortcuts and the Run key are per-user).
The same exe is copied to <dir>\\uninstall.exe and run with --uninstall to remove everything.
"""
import argparse
import ctypes
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from _build_info import VERSION
except ImportError:
    VERSION = "dev"

IS_WIN = sys.platform == "win32"
if IS_WIN:
    import winreg

APP_NAME = "Copilot Harness"
EXE_NAME = "GHC.exe"
DEFAULT_DIR = r"C:\GHC"
MANIFEST = "install.json"
UNINSTALLER = "uninstall.exe"
LNK_NAME = APP_NAME + ".lnk"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "GHC"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\GHC"
NOWIN = 0x08000000 if IS_WIN else 0  # CREATE_NO_WINDOW
DETACHED = 0x00000008 if IS_WIN else 0
CSIDL_PROGRAMS, CSIDL_DESKTOP = 0x02, 0x10


# --- helpers ---------------------------------------------------------
def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def run(cmd):
    # stdin must be redirected: windowed PyInstaller apps have no valid stdin handle
    return subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, creationflags=NOWIN)


def special_folder(csidl):
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return buf.value


def pinned_dir():
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Internet Explorer",
                        "Quick Launch", "User Pinned", "TaskBar")


def app_running():
    if not IS_WIN:
        return False
    out = run(["tasklist", "/FI", "IMAGENAME eq " + EXE_NAME, "/NH"]).stdout
    return EXE_NAME.lower() in out.decode("mbcs", "replace").lower()


def stop_app():
    if IS_WIN:
        run(["taskkill", "/F", "/IM", EXE_NAME])


def validate_dir(dest):
    if not os.path.isabs(dest):
        return "Informe um caminho completo, por exemplo %s." % DEFAULT_DIR
    dest = os.path.normpath(dest)
    if os.path.dirname(dest) == dest:
        return "Nao instale na raiz do disco; use uma pasta como %s." % DEFAULT_DIR
    if os.path.exists(dest):
        if not os.path.isdir(dest):
            return "O caminho informado e um arquivo."
        if os.listdir(dest) and not os.path.isfile(os.path.join(dest, MANIFEST)):
            return "A pasta nao esta vazia. Escolha uma pasta vazia ou uma instalacao existente."
    return None


def load_manifest(dest):
    try:
        with open(os.path.join(dest, MANIFEST), encoding="utf-8") as f:
            return json.load(f)
    except (IOError, ValueError):
        return None


def extract_payload(dest, progress=lambda i, n: None):
    """Extracts payload.zip into dest; returns relative file paths."""
    root = os.path.normcase(os.path.realpath(dest))
    files = []
    with zipfile.ZipFile(resource("payload.zip")) as z:
        infos = z.infolist()
        for i, info in enumerate(infos, 1):
            target = os.path.realpath(os.path.join(dest, info.filename))
            if not os.path.normcase(target).startswith(root + os.sep):
                raise ValueError("Pacote invalido: " + info.filename)
            if info.filename.endswith("/"):
                os.makedirs(target, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                files.append(os.path.relpath(target, os.path.realpath(dest)))
            progress(i, len(infos))
    return files


# --- Windows integration ---------------------------------------------
def _vq(s):
    return '"' + s.replace('"', '""') + '"'


def shortcut_vbs(lnks, target, workdir):
    """VBScript that creates every .lnk in `lnks` pointing at `target`."""
    lines = ['Set sh = CreateObject("WScript.Shell")']
    for lnk in lnks:
        lines += ["Set l = sh.CreateShortcut(%s)" % _vq(lnk),
                  "l.TargetPath = %s" % _vq(target),
                  "l.WorkingDirectory = %s" % _vq(workdir),
                  "l.Description = %s" % _vq(APP_NAME),
                  "l.IconLocation = %s" % _vq(target + ",0"),
                  "l.Save"]
    return "\r\n".join(lines) + "\r\n"


def pin_vbs(lnk, verb):
    folder, name = os.path.split(lnk)
    return ('Set app = CreateObject("Shell.Application")\r\n'
            "Set it = app.NameSpace(%s).ParseName(%s)\r\n"
            "it.InvokeVerb %s\r\n") % (_vq(folder), _vq(name), _vq(verb))


def run_vbs(text):
    fd, path = tempfile.mkstemp(suffix=".vbs")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-16") as f:  # BOM: WSH reads it as Unicode
            f.write(text)
        r = run(["cscript", "//nologo", path])
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("mbcs", "replace") or r.stdout.decode("mbcs", "replace"))
    finally:
        os.remove(path)


def pin_to_taskbar(lnk):
    """Best effort. Windows 7 honours the 'taskbarpin' verb; newer versions may ignore it."""
    try:
        run_vbs(pin_vbs(lnk, "taskbarpin"))
    except (RuntimeError, OSError):
        pass
    d = pinned_dir()
    pinned = os.path.join(d, LNK_NAME)
    if not os.path.exists(pinned) and os.path.isdir(d):
        shutil.copy2(lnk, pinned)
    return os.path.exists(pinned)


def unpin_from_taskbar(lnk):
    try:
        if os.path.exists(lnk):
            run_vbs(pin_vbs(lnk, "taskbarunpin"))
    except (RuntimeError, OSError):
        pass
    try:
        os.remove(os.path.join(pinned_dir(), LNK_NAME))
    except OSError:
        pass


def set_autostart(exe, enabled):
    if not IS_WIN:
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, '"%s" --minimized' % exe)
        else:
            try:
                winreg.DeleteValue(k, RUN_VALUE)
            except OSError:
                pass


def register_uninstall(dest, size_kb):
    if not IS_WIN:
        return
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        un = os.path.join(dest, UNINSTALLER)
        for name, val in (("DisplayName", APP_NAME), ("DisplayVersion", VERSION),
                          ("Publisher", "GHC"), ("InstallLocation", dest),
                          ("DisplayIcon", os.path.join(dest, EXE_NAME)),
                          ("UninstallString", '"%s" --uninstall' % un)):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)


def unregister_uninstall():
    if IS_WIN:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
        except OSError:
            pass


# --- install / uninstall ---------------------------------------------
def remove_files(dest, rel_files):
    for rel in rel_files:
        try:
            os.remove(os.path.join(dest, rel))
        except OSError:
            pass
    for root, dirs, _ in os.walk(dest, topdown=False):
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except OSError:
                pass


def install(dest, opts, log=print, progress=lambda i, n: None):
    """opts: startmenu, desktop, taskbar, autostart (bools). Returns a list of notes."""
    dest = os.path.normpath(dest)
    err = validate_dir(dest)
    if err:
        raise ValueError(err)
    notes = []
    old = load_manifest(dest)
    if app_running():
        stop_app()
    if old:
        log("Removendo versao anterior...")
        remove_files(dest, old.get("files", []))
    os.makedirs(dest, exist_ok=True)
    log("Copiando arquivos...")
    files = extract_payload(dest, progress)
    exe = os.path.join(dest, EXE_NAME)

    if getattr(sys, "frozen", False):
        shutil.copy2(sys.executable, os.path.join(dest, UNINSTALLER))

    shortcuts = []
    if IS_WIN:
        lnks = []
        if opts.get("startmenu"):
            lnks.append(os.path.join(special_folder(CSIDL_PROGRAMS), LNK_NAME))
        if opts.get("desktop"):
            lnks.append(os.path.join(special_folder(CSIDL_DESKTOP), LNK_NAME))
        taskbar_lnk = os.path.join(dest, LNK_NAME)
        if opts.get("taskbar"):
            lnks.append(taskbar_lnk)
        if lnks:
            log("Criando atalhos...")
            run_vbs(shortcut_vbs(lnks, exe, dest))
            shortcuts = lnks
        if opts.get("taskbar") and not pin_to_taskbar(taskbar_lnk):
            notes.append("Nao foi possivel fixar na barra de tarefas automaticamente. "
                         "Abra o programa, clique com o botao direito no icone e escolha 'Fixar'.")
        set_autostart(exe, bool(opts.get("autostart")))
        size_kb = sum(os.path.getsize(os.path.join(dest, f)) for f in files) // 1024
        register_uninstall(dest, size_kb)

    with open(os.path.join(dest, MANIFEST), "w", encoding="utf-8") as f:
        json.dump({"version": VERSION, "files": files, "shortcuts": shortcuts,
                   "taskbar": bool(opts.get("taskbar"))}, f)
    return notes


def uninstall(dest, remove_data, log=print):
    dest = os.path.normpath(dest)
    man = load_manifest(dest) or {}
    if app_running():
        stop_app()
    log("Removendo atalhos e configuracoes...")
    if man.get("taskbar"):
        unpin_from_taskbar(os.path.join(dest, LNK_NAME))
    set_autostart(os.path.join(dest, EXE_NAME), False)
    unregister_uninstall()
    for lnk in man.get("shortcuts", []):
        try:
            os.remove(lnk)
        except OSError:
            pass
    log("Removendo arquivos...")
    remove_files(dest, man.get("files", []))
    if remove_data:
        shutil.rmtree(os.path.join(os.path.expanduser("~"), ".copilot-harness"), ignore_errors=True)
    # the running uninstaller (and manifest) can only be deleted after this process exits
    if IS_WIN:
        cmd = ('ping 127.0.0.1 -n 6 >nul & del /f /q "%s" "%s" & rmdir "%s"'
               % (os.path.join(dest, UNINSTALLER), os.path.join(dest, MANIFEST), dest))
        subprocess.Popen("cmd /c " + cmd, cwd=tempfile.gettempdir(), creationflags=NOWIN | DETACHED,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        for f in (UNINSTALLER, MANIFEST):
            try:
                os.remove(os.path.join(dest, f))
            except OSError:
                pass
        try:
            os.rmdir(dest)
        except OSError:
            pass


def launch(dest):
    subprocess.Popen([os.path.join(dest, EXE_NAME)], cwd=dest, creationflags=DETACHED,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --- GUI -------------------------------------------------------------
class Wizard(tk.Tk):
    def __init__(self, dest):
        super().__init__()
        self.title("Instalar %s %s" % (APP_NAME, VERSION))
        self.resizable(False, False)
        st = ttk.Style(self)
        if "vista" in st.theme_names():
            st.theme_use("vista")  # native Aero look on Windows
        self.q = queue.Queue()
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=APP_NAME, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(f, text="Escolha onde instalar e as opcoes desejadas.").pack(anchor="w", pady=(0, 10))
        ttk.Label(f, text="Pasta de instalacao:").pack(anchor="w")
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(2, 10))
        self.dir_var = tk.StringVar(value=dest)
        self.dir_entry = ttk.Entry(row, textvariable=self.dir_var, width=48)
        self.dir_entry.pack(side="left", fill="x", expand=True)
        self.browse = ttk.Button(row, text="Procurar...", command=self._browse)
        self.browse.pack(side="left", padx=(6, 0))
        self.vars = {}
        self.checks = []
        for key, text, default in (
                ("startmenu", "Criar atalho no Menu Iniciar", True),
                ("desktop", "Criar atalho na Area de Trabalho", True),
                ("taskbar", "Fixar na barra de tarefas", False),
                ("autostart", "Iniciar com o Windows (minimizado na bandeja)", False),
                ("launch", "Executar ao concluir", True)):
            self.vars[key] = tk.BooleanVar(value=default)
            c = ttk.Checkbutton(f, text=text, variable=self.vars[key])
            c.pack(anchor="w", pady=1)
            self.checks.append(c)
        self.bar = ttk.Progressbar(f, length=400)
        self.bar.pack(fill="x", pady=(12, 2))
        self.msg = ttk.Label(f, text="")
        self.msg.pack(anchor="w")
        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(10, 0))
        self.cancel = ttk.Button(btns, text="Cancelar", command=self.destroy)
        self.cancel.pack(side="right")
        self.go = ttk.Button(btns, text="Instalar", command=self._start)
        self.go.pack(side="right", padx=6)
        self.after(100, self._poll)

    def _browse(self):
        d = filedialog.askdirectory(initialdir=os.path.dirname(self.dir_var.get()) or "C:\\")
        if d:
            self.dir_var.set(os.path.normpath(os.path.join(d, "GHC")) if os.listdir(d) else os.path.normpath(d))

    def _start(self):
        dest = os.path.normpath(self.dir_var.get().strip())
        err = validate_dir(dest)
        if err:
            messagebox.showerror(APP_NAME, err)
            return
        if app_running() and not messagebox.askyesno(
                APP_NAME, "O %s esta em execucao e sera fechado. Continuar?" % APP_NAME):
            return
        self.opts = {k: v.get() for k, v in self.vars.items()}
        self.dest = dest
        for w in [self.go, self.browse, self.dir_entry] + self.checks:
            w.state(["disabled"])
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        try:
            notes = install(self.dest, self.opts, log=lambda s: self.q.put(("log", s)),
                            progress=lambda i, n: self.q.put(("pct", 100.0 * i / n)))
            self.q.put(("done", notes))
        except Exception as e:
            self.q.put(("error", str(e)))

    def _poll(self):
        try:
            while True:
                ev = self.q.get_nowait()
                if ev[0] == "log":
                    self.msg.config(text=ev[1])
                elif ev[0] == "pct":
                    self.bar["value"] = ev[1]
                elif ev[0] == "error":
                    messagebox.showerror(APP_NAME, "Falha na instalacao:\n" + ev[1])
                    for w in [self.go, self.browse, self.dir_entry] + self.checks:
                        w.state(["!disabled"])
                elif ev[0] == "done":
                    text = "Instalacao concluida."
                    if ev[1]:
                        text += "\n\n" + "\n".join(ev[1])
                    messagebox.showinfo(APP_NAME, text)
                    if self.opts.get("launch"):
                        launch(self.dest)
                    self.destroy()
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)


def run_uninstall_gui(dest):
    root = tk.Tk()
    root.withdraw()
    if messagebox.askyesno(APP_NAME, "Desinstalar %s de %s?" % (APP_NAME, dest)):
        data = messagebox.askyesno(APP_NAME, "Remover tambem o login e as conversas salvas?")
        try:
            uninstall(dest, data)
            messagebox.showinfo(APP_NAME, "Desinstalado com sucesso.")
        except Exception as e:
            messagebox.showerror(APP_NAME, "Falha ao desinstalar:\n%s" % e)
    root.destroy()


def main(argv=None):
    p = argparse.ArgumentParser(prog="GHC-Setup")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--silent", action="store_true", help="instala sem interface")
    p.add_argument("--dir", default=DEFAULT_DIR)
    p.add_argument("--startmenu", action="store_true")
    p.add_argument("--desktop", action="store_true")
    p.add_argument("--taskbar", action="store_true")
    p.add_argument("--autostart", action="store_true")
    p.add_argument("--launch", action="store_true", help="(silent) executar ao concluir")
    a = p.parse_args(argv)

    frozen_uninstaller = getattr(sys, "frozen", False) and \
        os.path.basename(sys.executable).lower() == UNINSTALLER
    if a.uninstall or frozen_uninstaller:
        dest = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else a.dir
        if a.silent:
            uninstall(dest, False)
        else:
            run_uninstall_gui(dest)
        return 0
    if a.silent:
        opts = {k: getattr(a, k) for k in ("startmenu", "desktop", "taskbar", "autostart")}
        try:
            for note in install(a.dir, opts):
                print(note)
        except ValueError as e:
            print("Erro: %s" % e, file=sys.stderr)
            return 1
        if a.launch:
            launch(a.dir)
        return 0
    Wizard(a.dir).mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
