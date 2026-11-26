"""Entry point used to build GHC.exe with PyInstaller."""
import sys
import os


def self_test(report):
    try:
        import ssl
        import tkinter
        import harness.agent
        import harness.attachments
        import harness.auth
        import harness.cli
        import harness.client
        import harness.gui
        import harness.model_router
        import harness.resources
        import harness.storage
        import pypdf
        import docx
        import openpyxl
        import harness.theme
        import harness.tools
        import harness.tray
        import subprocess

        tkinter.Tcl().eval("info patchlevel")
        for name in ("logo.png", "logo-small.png", "ghc.ico", "tray.ico",
                     "attach-light.png", "attach-dark.png", "erase-light.png", "erase-dark.png"):
            path = harness.resources.asset_path(name)
            if not os.path.isfile(path):
                raise RuntimeError("Recurso de imagem ausente: " + path)
        ssl.create_default_context()
        result = subprocess.run(
            [harness.tools.python_executable(), "-c",
             "import json, ssl, sqlite3, docx, openpyxl, pypdf; "
             "from reportlab.pdfgen import canvas; from PIL import Image; print('OK')"],
            env=harness.tools._python_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30, creationflags=0x08000000 if sys.platform == "win32" else 0)
        if result.returncode or result.stdout.strip() != b"OK":
            raise RuntimeError("Falha no runtime Python: " + result.stderr.decode("utf-8", "replace"))
    except Exception as e:
        with open(report, "w", encoding="utf-8") as f:
            f.write("%s: %s" % (type(e).__name__, e))
        return 1
    with open(report, "w", encoding="utf-8") as f:
        f.write("OK")
    return 0

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        raise SystemExit(self_test(sys.argv[2]))
    from harness.cli import main
    raise SystemExit(main())
