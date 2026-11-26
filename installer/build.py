"""Builds a versioned setup in dist. Run on Windows with Python 3.8 x86 and PyInstaller 5.13.2.

    py -3.8-32 -m pip install pyinstaller==5.13.2
    py -3.8-32 build.py [--app ..\\app]

PyInstaller bundles Python and its dependencies. The target still needs the required Windows
system components, including the Universal CRT. Validate the package on Windows 7 SP1.
"""
import argparse
from datetime import datetime
import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME_PACKAGES = ("pypdf", "python-docx", "openpyxl", "reportlab", "Pillow", "chardet",
                    "lxml", "et-xmlfile", "typing-extensions")


def pyi(*args):
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean"] + list(args))


def copy_python_runtime(destination):
    source = sys.base_prefix
    for name in ("python.exe", "python3.dll", "python%d%d.dll" % sys.version_info[:2], "Lib", "DLLs"):
        if not os.path.exists(os.path.join(source, name)):
            raise RuntimeError("Runtime Python incompleto: %s" % os.path.join(source, name))
    os.makedirs(destination)
    for name in os.listdir(source):
        if name in ("python.exe", "python3.dll", "python%d%d.dll" % sys.version_info[:2]) or (
                name.lower().startswith("vcruntime") and name.lower().endswith(".dll")):
            shutil.copy2(os.path.join(source, name), destination)
    ignore = shutil.ignore_patterns("__pycache__", "site-packages", "test", "tests")
    for name in ("Lib", "DLLs"):
        shutil.copytree(os.path.join(source, name), os.path.join(destination, name), ignore=ignore)
    site_packages = os.path.join(destination, "Lib", "site-packages")
    for package in RUNTIME_PACKAGES:
        distribution = importlib.metadata.distribution(package)
        if not distribution.files:
            raise RuntimeError("Não foi possível localizar os arquivos do pacote: %s" % package)
        for item in distribution.files:
            relative = os.path.normpath(str(item))
            if (os.path.isabs(relative) or ".." in relative.split(os.sep) or
                    "__pycache__" in relative.split(os.sep) or relative.endswith(".pyc")):
                continue
            src = distribution.locate_file(item)
            if not os.path.isfile(src):
                raise RuntimeError("Arquivo de dependência ausente: %s" % src)
            target = os.path.join(site_packages, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(src, target)


def publish_setup(source, destination, version):
    if not re.fullmatch(r"[A-Za-z0-9._-]+", version):
        raise ValueError("Versão inválida para o nome do instalador.")
    os.makedirs(destination, exist_ok=True)
    stem = "GHC-Setup-v%s-%s" % (version, datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    for number in range(1000):
        path = os.path.join(destination, stem + ("-%d" % number if number else "") + ".exe")
        try:
            target = open(path, "xb")
        except FileExistsError:
            continue
        try:
            with target, open(source, "rb") as src:
                shutil.copyfileobj(src, target)
        except (OSError, ValueError):
            os.remove(path)
            raise
        return path
    raise RuntimeError("Não foi possível criar um nome exclusivo para o instalador.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--app", default=os.path.join(HERE, "..", "app"))
    p.add_argument("--icon", help="optional .ico for GHC.exe and the installer")
    p.add_argument("--output-dir", default=HERE, help="directory for build and dist outputs")
    a = p.parse_args()
    app = os.path.abspath(a.app)
    output = os.path.abspath(a.output_dir)
    build_root, dist = os.path.join(output, "build"), os.path.join(output, "dist")
    os.makedirs(build_root, exist_ok=True)
    build = tempfile.mkdtemp(prefix="build-", dir=build_root)

    sys.path.insert(0, app)
    from harness import __version__
    assets = os.path.join(app, "assets")
    icon = ["--icon", os.path.abspath(a.icon) if a.icon else os.path.join(assets, "ghc.ico")]

    print("== 1/3 GHC.exe (%s)" % __version__)
    pyi("--onedir", "--noconsole", "--name", "GHC", "--paths", app, "--distpath", os.path.join(build, "app"),
        "--workpath", os.path.join(build, "work-app"), "--specpath", build, *icon,
        "--add-data", assets + os.pathsep + "assets",
        os.path.join(app, "run_ghc.py"))
    copy_python_runtime(os.path.join(build, "app", "GHC", "python-runtime"))

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
    setup_dist = os.path.join(build, "setup-dist")
    pyi("--onefile", "--noconsole", "--name", "GHC-Setup", "--distpath", setup_dist,
        "--workpath", os.path.join(build, "work-setup"), "--specpath", build,
        "--paths", build, "--hidden-import", "_build_info",
        "--add-data", payload + os.pathsep + ".", *icon,
        os.path.join(HERE, "installer", "installer.py"))
    result = publish_setup(os.path.join(setup_dist, "GHC-Setup.exe"), dist, __version__)
    print("OK:", result)


if __name__ == "__main__":
    main()
