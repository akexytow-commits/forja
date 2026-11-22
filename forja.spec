# -*- mode: python ; coding: utf-8 -*-
# Rama 7 — FORJA.exe (15-build-run-despliegue.md): PyInstaller --onefile, sin consola, con icono.
# Recursos como datos (se extraen en sys._MEIPASS; ver backend/config.py). Ollama NO va dentro: es
# dependencia externa y la app guía si falta (SCR-008). Construir con build.bat.
from PyInstaller.utils.hooks import collect_submodules

datas = [
    ("ui", "ui"),
    ("backend/prompts", "backend/prompts"),
    ("backend/migrations", "backend/migrations"),
    ("backend/plantillas", "backend/plantillas"),
    ("assets/forja.ico", "assets"),
]
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("backend")
    + ["keyring.backends.Windows", "webview.platforms.winforms", "webview.platforms.edgechromium"]
)

a = Analysis(
    ["forja_app.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "_pytest", "tests", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FORJA",
    icon="assets/forja.ico",
    console=False,            # sin terminal: los mensajes van a un cuadro de diálogo y el log a %APPDATA%\FORJA\logs
    upx=False,
    runtime_tmpdir=None,
    debug=False,
    strip=False,
)
