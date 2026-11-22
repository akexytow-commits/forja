"""Rama 7 — Empaquetado a .exe (15-build-run-despliegue.md, FR-074, ST-060).

Unitarias: rutas en modo congelado, el spec incluye ui/ y los recursos, accesos directos, registro sin consola.
Integración (si existe dist/FORJA.exe; se construye con build.bat): doble clic → ventana «FORJA», primer arranque
limpio en %APPDATA%\\FORJA con las migraciones, y sin Ollama la interfaz abre SCR-008 con la guía.
"""
from __future__ import annotations

import asyncio
import ctypes
import importlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

import pytest

from backend import config, escritorio

RAIZ = Path(__file__).resolve().parents[1]
EXE = RAIZ / "dist" / "FORJA.exe"
WINDOWS = os.name == "nt"


# --- unitarias ------------------------------------------------------------------------------------------
def test_rutas_en_modo_congelado(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    try:
        c = importlib.reload(config)
        assert c.CONGELADO and c.ROOT_DIR == tmp_path
        assert c.UI_DIR == tmp_path / "ui" and c.MIGRATIONS_DIR == tmp_path / "backend" / "migrations"
        assert c.PROMPTS_DIR == tmp_path / "backend" / "prompts"
    finally:
        monkeypatch.delattr(sys, "frozen")
        monkeypatch.delattr(sys, "_MEIPASS")
        importlib.reload(config)
    assert not config.CONGELADO and config.UI_DIR == RAIZ / "ui"


def test_el_spec_empaqueta_ui_y_recursos_sin_consola_y_con_icono():
    spec = (RAIZ / "forja.spec").read_text(encoding="utf-8")
    for d in ('("ui", "ui")', '("backend/prompts"', '("backend/migrations"', '("backend/plantillas"', "assets/forja.ico"):
        assert d in spec
    assert "console=False" in spec and 'icon="assets/forja.ico"' in spec and 'name="FORJA"' in spec
    assert "ollama" not in spec.lower().replace("ollama no va dentro", "").replace("ollama no", "")
    ico = (RAIZ / "assets/forja.ico").read_bytes()
    assert ico[:4] == b"\x00\x00\x01\x00" and int.from_bytes(ico[4:6], "little") >= 4    # ICO con varios tamaños


def test_registro_sin_consola_va_a_archivo(monkeypatch, tmp_path):
    monkeypatch.setenv("FORJA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    import logging
    antes = logging.getLogger().handlers[:]
    try:
        ruta = escritorio.configurar_registro()
        assert ruta == tmp_path / "logs" / "forja.log"
        logging.getLogger("forja.prueba").info("hola desde el exe")
        for h in logging.getLogger().handlers:
            h.flush()
        assert "hola desde el exe" in ruta.read_text(encoding="utf-8")
        assert sys.stdout is not None and sys.stderr is not None             # uvicorn podrá escribir
    finally:
        for h in logging.getLogger().handlers:
            h.close()
        logging.getLogger().handlers[:] = antes


@pytest.mark.skipif(not WINDOWS, reason="accesos directos de Windows")
def test_instalar_copia_el_exe_y_crea_accesos_con_icono(tmp_path):
    origen = tmp_path / "dist" / "FORJA.exe"
    origen.parent.mkdir()
    origen.write_bytes(b"MZ falso")
    r = escritorio.instalar(origen, tmp_path / "Programs" / "FORJA", tmp_path / "Escritorio", tmp_path / "Inicio")
    exe = Path(r["exe"])
    assert exe.read_bytes() == b"MZ falso"
    for clave in ("escritorio", "inicio"):
        lnk = Path(r[clave])
        assert lnk.exists() and lnk.suffix == ".lnk"
        info = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                               f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}'); $s.TargetPath; $s.IconLocation"],
                              capture_output=True, text=True).stdout.splitlines()
        assert Path(info[0]) == exe and info[1].endswith(",0") and Path(info[1][:-2]) == exe


def test_instancia_unica():
    if not WINDOWS:
        pytest.skip("mutex de Windows")
    nombre = f"Local\\FORJA-prueba-{os.getpid()}"
    assert escritorio.instancia_unica(nombre) is True
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    h = k32.CreateMutexW(None, False, nombre)                       # una "segunda FORJA"
    assert k32.GetLastError() == 183
    k32.CloseHandle(ctypes.c_void_p(h))


# --- integración: el .exe de verdad ----------------------------------------------------------------------
def _puerto() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ventanas_visibles() -> list[tuple[int, str]]:
    u32 = ctypes.windll.user32
    out: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            n = u32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(hwnd, buf, n + 1)
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.append((pid.value, buf.value))
        return True

    u32.EnumWindows(cb, 0)
    return out


def _descendientes(pid: int) -> set[int]:
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId | ConvertTo-Json"],
                       capture_output=True, text=True)
    procs = json.loads(r.stdout)
    hijos, pend = {pid}, [pid]
    while pend:
        p = pend.pop()
        for x in procs:
            if x["ParentProcessId"] == p and x["ProcessId"] not in hijos:
                hijos.add(x["ProcessId"])
                pend.append(x["ProcessId"])
    return hijos


@pytest.mark.skipif(not (WINDOWS and EXE.exists()), reason="construye antes dist/FORJA.exe con build.bat")
def test_exe_doble_clic_abre_ventana_primer_arranque_limpio_y_scr008_sin_ollama(tmp_path):
    appdata = tmp_path / "AppData" / "Roaming"           # %APPDATA% vacío: primer arranque limpio
    appdata.mkdir(parents=True)
    puerto = _puerto()
    env = {**os.environ, "APPDATA": str(appdata), "FORJA_PORT": str(puerto), "FORJA_SIN_DIALOGOS": "1",
           "FORJA_OLLAMA_URL": f"http://127.0.0.1:{_puerto()}"}           # Ollama "no está"
    env.pop("FORJA_DATA_DIR", None)
    proc = subprocess.Popen([str(EXE)], env=env, cwd=str(tmp_path))      # = doble clic (sin argumentos)
    try:
        ventana = None
        for _ in range(240):                                             # el onefile tarda en extraerse
            familia = _descendientes(proc.pid)
            ventana = next((v for v in _ventanas_visibles() if v[0] in familia and v[1] == "FORJA"), None)
            if ventana:
                break
            assert proc.poll() is None, "el .exe se cerró solo"
            time.sleep(0.5)
        assert ventana, "no apareció la ventana «FORJA»"

        datos = appdata / "FORJA"
        assert (datos / "forja.db").exists() and (datos / "logs" / "forja.log").exists()
        with sqlite3.connect(datos / "forja.db") as c:
            assert c.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] >= 11

        html = urllib.request.urlopen(f"http://127.0.0.1:{puerto}/").read().decode("utf-8")
        token = html.split('window.FORJA_TOKEN = "', 1)[1].split('"', 1)[0]
        req = urllib.request.Request(f"http://127.0.0.1:{puerto}/salud", headers={"X-Forja-Token": token})
        salud = json.loads(urllib.request.urlopen(req).read())
        assert salud["ollama"] == "caido"                                # → la UI abre SCR-008

        # Un segundo doble clic no abre otra FORJA (instancia única) y se cierra solo.
        segundo = subprocess.run([str(EXE)], env=env, cwd=str(tmp_path), timeout=120)
        assert segundo.returncode == 0
        assert "FORJA ya está abierta" in (datos / "logs" / "forja.log").read_text(encoding="utf-8")

        # La interfaz servida por el .exe muestra SCR-008 con la guía (Edge headless contra el mismo backend).
        from . import test_rama6 as t6
        if t6.EDGE.exists():
            async def pasos(ev, esperar):
                await esperar("document.querySelector('#scr-008') && !document.querySelector('#scr-008').hidden", 30)
                return await ev("document.querySelector('#scr-008').innerText")
            texto = asyncio.run(t6._cdp(f"http://127.0.0.1:{puerto}/", tmp_path / "edge", pasos))
            assert "Ollama" in texto
    finally:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
