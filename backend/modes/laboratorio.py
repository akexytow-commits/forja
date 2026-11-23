"""MOD-091 Laboratorio Linux (19-...md): WSL2 y attack box de serie, VirtualBox opcional («pesado»).

- Autodetección + recomendación según el hardware (FR-071, TST-071).
- Instalación/arranque guiados: primero se PROPONEN los comandos; solo se ejecutan con confirmación explícita
  del usuario (ST-040: propuesta → esperando_usuario → aprobada → ejecutando → hecha | rechazada) y se auditan
  (FR-072, TST-072). La propia instalación de WSL pide además elevación de Windows (UAC).
- FORJA abre la terminal ya situada en la carpeta del ejercicio con README_LAB.md (FR-070) y NUNCA lanza
  herramientas ofensivas por su cuenta: te deja la terminal y el contexto; tú ejecutas.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .. import audit
from ..db import DB
from ..sistema import disco_libre_mb, ram_total_mb

BACKENDS = ("wsl", "attackbox", "virtualbox")
RAM_VM_COMODA_MB = 16_000   # por debajo, VirtualBox es «pesado» (19-...md: la VM sola pide 2–4 GB)
DISTROS_SUGERIDAS = ("kali-linux", "Ubuntu", "Debian")
_RE_DISTRO = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
CREAR_CONSOLA = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Puntos de enganche (las pruebas los sustituyen: nunca se lanza nada real desde los tests).
lanzar = subprocess.Popen
abrir_url = webbrowser.open


def _ejecutar(cmd: list[str], timeout: float = 8.0) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=SIN_VENTANA, check=False)
    except (OSError, subprocess.SubprocessError):
        return -1, ""
    bruto = r.stdout or b""
    # wsl.exe escribe en UTF-16LE.
    texto = bruto.decode("utf-16-le", "ignore") if b"\x00" in bruto[:64] else bruto.decode("utf-8", "ignore")
    return r.returncode, texto.replace("\x00", "")


def detectar_wsl() -> dict[str, Any]:
    exe = shutil.which("wsl.exe") or shutil.which("wsl")
    if not exe:
        return {"exe": None, "instalado": False, "distros": []}
    rc, salida = _ejecutar([exe, "-l", "-q"])
    distros = [l.strip() for l in salida.splitlines() if l.strip()]
    no_instalado = rc != 0 or "no está instalado" in salida.lower() or "not installed" in salida.lower()
    if no_instalado:
        distros = []
    return {"exe": exe, "instalado": not no_instalado, "distros": distros}


def detectar_virtualbox() -> str | None:
    cand = shutil.which("VBoxManage") or shutil.which("VBoxManage.exe")
    if cand:
        return cand
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramW6432", "")):
        if base:
            p = Path(base) / "Oracle" / "VirtualBox" / "VBoxManage.exe"
            if p.is_file():
                return str(p)
    return None


def terminal_windows() -> str | None:
    return shutil.which("wt.exe") or shutil.which("wt")


class LabError(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje = status, codigo, mensaje


class Laboratorio:
    def __init__(self, db: DB, detector: dict[str, Any] | None = None):
        self.db = db
        self._detector = detector   # para pruebas: {"wsl": {...}, "virtualbox": ..., "ram_total_mb": ...}

    # --- detección y recomendación (FR-071) -------------------------------------------------------
    def detectar(self) -> dict[str, Any]:
        d = self._detector or {}
        wsl = d.get("wsl") if "wsl" in d else detectar_wsl()
        vbox = d.get("virtualbox") if "virtualbox" in d else detectar_virtualbox()
        ram = d.get("ram_total_mb") if "ram_total_mb" in d else ram_total_mb()
        disco = d.get("disco_libre_mb") if "disco_libre_mb" in d else disco_libre_mb(self.carpeta_base_existente())
        pesado = (ram or 0) < RAM_VM_COMODA_MB
        distro = self.db.get_setting("lab.distro", "kali-linux") or "kali-linux"
        wsl_listo = bool(wsl["instalado"] and wsl["distros"])
        recomendado = "wsl" if wsl_listo else "attackbox"
        backends = [
            {"id": "wsl", "disponible": wsl_listo, "instalable": bool(wsl["exe"]), "recomendado": recomendado == "wsl"
             or not wsl_listo, "pesado": False, "distros": wsl["distros"], "distro": distro,
             "nota": ("Listo: " + ", ".join(wsl["distros"])) if wsl_listo else
             ("WSL no está instalado: FORJA te propone el comando y lo ejecuta solo con tu OK." if wsl["exe"]
              else "Esta versión de Windows no trae wsl.exe.")},
            {"id": "attackbox", "disponible": True, "instalable": False, "recomendado": True, "pesado": False,
             "url": self.db.get_setting("lab.attackbox_url", ""),
             "nota": "Coste local cero: la máquina de ataque corre en el servidor de HTB/THM y la usas desde el navegador."},
            {"id": "virtualbox", "disponible": bool(vbox), "instalable": True, "recomendado": False, "pesado": pesado,
             "nota": (f"Pesado para este equipo ({round((ram or 0) / 1024)} GB de RAM): una VM pide 2–4 GB y 20–30 GB de disco."
                      if pesado else "Soportado. Una VM pide 2–4 GB de RAM y 20–30 GB de disco.")},
        ]
        return {"backends": backends, "recomendado": recomendado, "activo": self.activo(recomendado),
                "ram_total_mb": ram, "disco_libre_mb": disco, "terminal": bool(terminal_windows())}

    def activo(self, recomendado: str | None = None) -> str:
        v = self.db.get_setting("lab.backend", "") or ""
        if v in BACKENDS:
            return v
        return recomendado or "attackbox"

    def cambiar_backend(self, backend: str) -> dict[str, Any]:
        """BTN-092: cambia settings.lab.backend al instante."""
        if backend not in BACKENDS:
            raise LabError(400, "BACKEND_INVALIDO", "Backend: wsl, attackbox o virtualbox.")
        self.db.set_setting("lab.backend", backend)
        return self.detectar()

    # --- configuración guiada con confirmación (FR-072, ST-040) ----------------------------------------
    def propuesta(self, backend: str, distro: str | None = None) -> dict[str, Any]:
        if backend == "wsl":
            distro = (distro or self.db.get_setting("lab.distro", "kali-linux") or "kali-linux").strip()
            if not _RE_DISTRO.fullmatch(distro):
                raise LabError(400, "DISTRO_INVALIDA", "Nombre de distribución no válido.")
            return {"backend": "wsl", "distro": distro,
                    "comandos": [f"wsl --install -d {distro}"],
                    "explicacion": ("Activa el Subsistema de Windows para Linux e instala la distribución. Windows "
                                    "pedirá permiso de administrador (UAC) y puede pedir reiniciar. Después, abre la "
                                    "distro una vez para crear tu usuario de Linux. Ocupa unos 1–3 GB (solo consola)."),
                    "requiere_admin": True}
        if backend == "virtualbox":
            return {"backend": "virtualbox", "comandos": ["winget install --id Oracle.VirtualBox -e"],
                    "explicacion": ("Instala VirtualBox con winget. Recuerda: en este equipo es pesado; luego tendrás "
                                    "que crear la VM a mano."),
                    "requiere_admin": True}
        if backend == "attackbox":
            return {"backend": "attackbox", "comandos": [],
                    "explicacion": "No se instala nada: solo guardas la URL del attack box (HTB Pwnbox / THM AttackBox).",
                    "requiere_admin": False}
        raise LabError(400, "BACKEND_INVALIDO", "Backend: wsl, attackbox o virtualbox.")

    def configurar(self, backend: str, confirmado: bool = False, distro: str | None = None,
                   url: str | None = None) -> dict[str, Any]:
        """Sin `confirmado` solo devuelve la propuesta (esperando_usuario). Nada se instala sin el OK."""
        p = self.propuesta(backend, distro)
        if backend == "attackbox":
            if url is not None:
                self.db.set_setting("lab.attackbox_url", self._validar_url(url))
            self.db.set_setting("lab.backend", "attackbox")
            return {**p, "estado": "hecha", "detectado": self.detectar()}
        if not confirmado:
            return {**p, "estado": "esperando_usuario"}
        audit.registrar(self.db, "lab_accion", {"accion": "instalar", "backend": backend, "comandos": p["comandos"],
                                                "confirmado": True})
        if backend == "wsl":
            self.db.set_setting("lab.distro", p["distro"])
            args = f"'--install','-d','{p['distro']}'"
            cmd = ["powershell.exe", "-NoProfile", "-Command",
                   f"Start-Process -FilePath wsl.exe -ArgumentList {args} -Verb RunAs"]
        else:
            cmd = ["powershell.exe", "-NoProfile", "-Command",
                   "Start-Process -FilePath winget -ArgumentList 'install','--id','Oracle.VirtualBox','-e' -Verb RunAs"]
        try:
            lanzar(cmd, creationflags=CREAR_CONSOLA)
        except OSError as e:
            raise LabError(500, "LANZAR_FALLO", f"No pude lanzar la instalación: {e}") from e
        self.db.set_setting("lab.backend", backend)
        return {**p, "estado": "ejecutando",
                "mensaje": "Se abrió la instalación en una ventana aparte (acepta el aviso de Windows). "
                           "Cuando termine, pulsa «Volver a detectar»."}

    @staticmethod
    def _validar_url(url: str) -> str:
        url = (url or "").strip()
        partes = urlsplit(url)
        if partes.scheme != "https" or not partes.hostname:
            raise LabError(400, "URL_INVALIDA", "La URL del attack box debe empezar por https://")
        return url

    # --- carpeta de trabajo y contexto (FR-070, BTN-091) -----------------------------------------------
    def carpeta_base(self) -> Path:
        elegido = (self.db.get_setting("lab.working_dir", "") or "").strip()
        return Path(elegido) if elegido else Path(os.environ.get("USERPROFILE", Path.home())) / "FORJA-lab"

    def carpeta_base_existente(self) -> Path:
        p = self.carpeta_base()
        while not p.exists() and p.parent != p:
            p = p.parent
        return p

    def carpeta(self, seccion: dict[str, Any]) -> Path:
        slug = re.sub(r"[^\w\-]+", "-", seccion["titulo"].lower(), flags=re.UNICODE).strip("-")[:40]
        return self.carpeta_base() / f"{seccion['id']:03d}-{slug}"

    def escribir_contexto(self, seccion: dict[str, Any], pistas: list[str], lab: dict[str, Any] | None) -> dict[str, Any]:
        carpeta = self.carpeta(seccion)
        carpeta.mkdir(parents=True, exist_ok=True)
        lineas = [f"# {seccion['titulo']}", "",
                  f"Ruta: {seccion['ruta']} · Módulo: {seccion['modulo']} ({seccion['dificultad']})", ""]
        if lab:
            lineas += [f"**Laboratorio autorizado declarado:** {lab['descripcion']} ({lab['entorno']})",
                       "Practica SOLO contra las máquinas de ese laboratorio.", ""]
        lineas += ["## Objetivo", seccion.get("contenido_guia") or "—", ""]
        if seccion.get("pregunta"):
            lineas += ["## Pregunta a responder en FORJA", seccion["pregunta"], ""]
        lineas += ["## Pistas desbloqueadas"]
        lineas += [f"{i}. {p}" for i, p in enumerate(pistas, 1)] or ["(ninguna todavía)"]
        lineas += ["", "## Notas",
                   "Escribe tus notas y salidas relevantes en `notas.md` (esta misma carpeta): el copiloto de FORJA "
                   "las lee para orientarte. FORJA no ejecuta nada aquí por su cuenta."]
        (carpeta / "README_LAB.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
        notas = carpeta / "notas.md"
        if not notas.exists():
            notas.write_text(f"# Notas — {seccion['titulo']}\n\n", encoding="utf-8")
        return {"carpeta": str(carpeta), "readme": str(carpeta / "README_LAB.md"), "notas": str(notas)}

    def leer_notas(self, seccion: dict[str, Any], maximo: int = 12_000) -> str:
        p = self.carpeta(seccion) / "notas.md"
        try:
            return p.read_text(encoding="utf-8", errors="ignore")[-maximo:]
        except OSError:
            return ""

    # --- abrir el Linux del laboratorio (BTN-089) --------------------------------------------------------
    def abrir(self, seccion: dict[str, Any], pistas: list[str], lab: dict[str, Any] | None,
              backend: str | None = None) -> dict[str, Any]:
        backend = backend or self.activo(self.detectar()["recomendado"])
        if backend not in BACKENDS:
            raise LabError(400, "BACKEND_INVALIDO", "Backend: wsl, attackbox o virtualbox.")
        ctx = self.escribir_contexto(seccion, pistas, lab)
        resultado: dict[str, Any] = {"backend": backend, **ctx}
        if backend == "wsl":
            wsl = (self._detector or {}).get("wsl") or detectar_wsl()
            if not wsl["instalado"] or not wsl["distros"]:
                raise LabError(409, "WSL_NO_LISTO", "WSL no está instalado todavía. Configúralo en Laboratorio Linux "
                                                    "(te enseño el comando y lo ejecuto solo con tu OK).")
            distro = self.db.get_setting("lab.distro", "") or ""
            base = ["wsl.exe"] + (["-d", distro] if distro in wsl["distros"] else []) + ["--cd", ctx["carpeta"]]
            wt = terminal_windows()
            cmd = [wt, "new-tab", "--title", "FORJA lab", *base] if wt else base
            try:
                lanzar(cmd, creationflags=CREAR_CONSOLA)
            except OSError as e:
                raise LabError(500, "LANZAR_FALLO", f"No pude abrir la terminal: {e}") from e
            resultado["comando"] = " ".join(base)
        elif backend == "attackbox":
            url = self._validar_url(self.db.get_setting("lab.attackbox_url", "") or "")
            abrir_url(url)
            resultado["url"] = url
        else:
            if hasattr(os, "startfile"):
                os.startfile(ctx["carpeta"])  # noqa: S606 — carpeta propia de FORJA
            resultado["mensaje"] = "Arranca tu VM en VirtualBox y comparte esta carpeta con ella."
        audit.registrar(self.db, "lab_accion", {"accion": "abrir", "backend": backend, "seccion_id": seccion["id"],
                                                "carpeta": ctx["carpeta"]})
        return resultado
