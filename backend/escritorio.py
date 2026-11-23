"""Rama 7 — FORJA como app de escritorio empaquetada (15-build-run-despliegue.md, FR-074).

- Sin consola (.exe --windowed): el registro va a %APPDATA%\\FORJA\\logs\\forja.log y los errores de arranque
  se enseñan en un cuadro de diálogo de Windows (el usuario nunca necesita una terminal).
- Una sola instancia (mutex con nombre): un segundo doble clic avisa en vez de abrir otra ventana.
- `FORJA.exe --instalar`: copia el .exe a %LOCALAPPDATA%\\Programs\\FORJA y crea los accesos directos con icono
  en el Escritorio y en el menú Inicio.
"""
from __future__ import annotations

import ctypes
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import APP_NAME, CONGELADO, data_dir

log = logging.getLogger("forja.escritorio")
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_mutex = None        # se mantiene vivo mientras corre la app


def ruta_log() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "forja.log"


def configurar_registro() -> Path | None:
    """En el .exe sin consola, sys.stdout/stderr son None: todo (FORJA, uvicorn) va a un archivo rotativo."""
    sin_consola = sys.stdout is None or sys.stderr is None
    if not (CONGELADO or sin_consola):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
        return None
    ruta = ruta_log()
    manejador = logging.handlers.RotatingFileHandler(ruta, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    raiz = logging.getLogger()
    raiz.handlers[:] = [manejador]
    raiz.setLevel(logging.INFO)
    if sin_consola:
        flujo = open(ruta.with_name("salida.log"), "a", encoding="utf-8", buffering=1)   # noqa: SIM115
        sys.stdout = sys.stdout or flujo
        sys.stderr = sys.stderr or flujo
    return ruta


def mensaje(texto: str, titulo: str = APP_NAME, error: bool = False) -> None:
    """Cuadro de diálogo nativo (no hay consola donde escribir)."""
    log.info("mensaje: %s", texto)
    if os.environ.get("FORJA_SIN_DIALOGOS") == "1":    # pruebas automáticas: un diálogo bloquearía
        return
    if os.name != "nt":
        print(texto, file=sys.stderr)
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x10 if error else 0x40)
    except Exception:  # noqa: BLE001, S110 — sin cuadro de diálogo no hay otra salida
        pass


def instancia_unica(nombre: str = "Local\\FORJA-instancia-unica") -> bool:
    """True si somos la única FORJA abierta en esta sesión de Windows."""
    global _mutex
    if os.name != "nt":
        return True
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    _mutex = k32.CreateMutexW(None, False, nombre)
    return k32.GetLastError() != 183            # ERROR_ALREADY_EXISTS


# ---------------------------------------------------------------- instalar + accesos directos
def carpeta_instalacion() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / APP_NAME


def _carpeta_especial(nombre: str) -> Path:
    """Escritorio / menú Inicio reales (pueden estar redirigidos, p. ej. a OneDrive)."""
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                            f"[Environment]::GetFolderPath('{nombre}')"], capture_output=True, text=True,
                           timeout=30, creationflags=SIN_VENTANA, check=False)
        if r.stdout.strip():
            return Path(r.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    base = Path(os.environ.get("USERPROFILE", Path.home()))
    return base / "Desktop" if nombre == "Desktop" else base / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs"


def crear_acceso(destino_lnk: Path, exe: Path, descripcion: str = "FORJA — IA local") -> None:
    """Acceso directo .lnk con el icono incrustado en el .exe (WScript.Shell, sin dependencias)."""
    destino_lnk.parent.mkdir(parents=True, exist_ok=True)
    ps = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:FORJA_LNK); "
          "$s.TargetPath = $env:FORJA_EXE; $s.WorkingDirectory = $env:FORJA_DIR; "
          "$s.IconLocation = $env:FORJA_EXE + ',0'; $s.Description = $env:FORJA_DESC; $s.Save()")
    env = {**os.environ, "FORJA_LNK": str(destino_lnk), "FORJA_EXE": str(exe), "FORJA_DIR": str(exe.parent),
           "FORJA_DESC": descripcion}
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps], env=env,
                       capture_output=True, text=True, timeout=60, creationflags=SIN_VENTANA, check=False)
    if r.returncode != 0 or not destino_lnk.exists():
        raise OSError(f"No pude crear el acceso directo {destino_lnk}: {r.stderr.strip()[:300]}")


def instalar(origen: Path | None = None, destino: Path | None = None,
             escritorio: Path | None = None, inicio: Path | None = None) -> dict[str, str]:
    """Copia el .exe a su carpeta de programas del usuario (sin admin) y crea los dos accesos directos."""
    origen = Path(origen or sys.executable).resolve()
    destino = Path(destino or carpeta_instalacion())
    destino.mkdir(parents=True, exist_ok=True)
    exe = destino / f"{APP_NAME}.exe"
    if origen != exe.resolve():
        shutil.copy2(origen, exe)
    accesos = {
        "escritorio": (escritorio or _carpeta_especial("Desktop")) / f"{APP_NAME}.lnk",
        "inicio": (inicio or _carpeta_especial("Programs")) / f"{APP_NAME}.lnk",
    }
    for lnk in accesos.values():
        crear_acceso(lnk, exe)
    log.info("Instalado en %s; accesos: %s", exe, accesos)
    return {"exe": str(exe), **{k: str(v) for k, v in accesos.items()}}
