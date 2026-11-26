"""Builds dist/GHC-Setup.exe. Run on Windows with 32-bit Python 3.8 and PyInstaller 5.13.2.

    py -3.8-32 -m pip install pyinstaller==5.13.2
    py -3.8-32 build.py [--app ..\\app]

PyInstaller embeds the Python runtime, Tcl/Tk and the VC/UCRT DLLs, so the target PC needs
no Python installed. Build on a machine that has the Universal CRT (Win7 SP1 + KB2999226, or
Win10+) so those DLLs get bundled and the exe runs on a bare Windows 7.
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))


def pyi(*args):
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean"] + list(args))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--app", default=os.path.join(HERE, "..", "app"))
    p.add_argument("--icon", help="optional .ico for GHC.exe and the installer")
    a = p.parse_args()
    app = os.path.abspath(a.app)
    build, dist = os.path.join(HERE, "build"), os.path.join(HERE, "dist")
    shutil.rmtree(build, ignore_errors=True)
    shutil.rmtree(dist, ignore_errors=True)

    sys.path.insert(0, app)
    from harness import __version__
    icon = ["--icon", os.path.abspath(a.icon)] if a.icon else []

    print("== 1/3 GHC.exe (%s)" % __version__)
    pyi("--onedir", "--noconsole", "--name", "GHC", "--paths", app, "--distpath", os.path.join(build, "app"),
        "--workpath", os.path.join(build, "work-app"), "--specpath", build, *icon,
        os.path.join(app, "run_ghc.py"))

    print("== 2/3 payload.zip")
    payload = os.path.join(build, "payload.zip")
    src = os.path.join(build, "app", "GHC")
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, src))

    print("== 3/3 GHC-Setup.exe")
    info = os.path.join(build, "_build_info.py")
    with open(info, "w") as f:
        f.write('VERSION = "%s"\n' % __version__)
    pyi("--onefile", "--noconsole", "--name", "GHC-Setup", "--distpath", dist,
        "--workpath", os.path.join(build, "work-setup"), "--specpath", build,
        "--paths", build, "--hidden-import", "_build_info",
        "--add-data", payload + os.pathsep + ".", *icon,
        os.path.join(HERE, "installer", "installer.py"))
    print("OK:", os.path.join(dist, "GHC-Setup.exe"))


if __name__ == "__main__":
    main()
