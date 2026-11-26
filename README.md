# GHC — Copilot Harness

Cliente de chat para GitHub Copilot (GUI Tkinter, bandeja, tema claro/escuro) e seu instalador para Windows 7+.

- `app/` — o harness (Python 3.8, sem dependências). Veja `app/README.md`.
- `installer/` — instalador `GHC-Setup.exe` (padrão `C:\GHC`; atalhos Menu Iniciar/Desktop/barra de tarefas; iniciar com o Windows; desinstalador).

O `.exe` é autocontido (PyInstaller): **Python, Tcl/Tk e runtimes vão dentro do instalador**, o usuário não precisa instalar nada.

## Baixar
Releases → `GHC-Setup.exe` (ou `GHC-portable.zip`).

## Instalação silenciosa
```
GHC-Setup.exe --silent --dir C:\GHC --startmenu --desktop --taskbar --autostart --launch
```
Desinstalar: `C:\GHC\uninstall.exe` (ou Adicionar/Remover Programas).

## Build
O build é feito pelo GitHub Actions (`.github/workflows/build.yml`, Python 3.8 x86). Local, no Windows: `python installer/build.py --app app`.
