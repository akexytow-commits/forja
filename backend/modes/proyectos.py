"""MOD-020 Modo Scripts/Firmware — Rama 5: proyectos (SCR-011), guardar a archivo (BTN-031, ST-040),
plantillas (BTN-032) y export de conversaciones (BTN-060, API-062).

Regla de oro de guardar a archivo (09-...md): requiere confirmación explícita y NUNCA escribe fuera de la
carpeta del proyecto. Se comprueba aquí, en el backend, no solo en la UI.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import audit
from ..config import BACKEND_DIR, ROOT_DIR, data_dir
from ..db import DB, ahora
from .seguridad import dir_export

PLANTILLAS_SERIE = BACKEND_DIR / "plantillas"
MAX_ARCHIVO = 2_000_000          # 2 MB por archivo guardado desde el chat
IGNORAR = {".git", ".venv", "venv", "node_modules", "__pycache__", ".idea", ".vscode", "build", "dist"}
RESERVADOS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
RE_PROHIBIDOS = re.compile(r'[<>:"|?*\x00-\x1f]')
RE_ID_PLANTILLA = re.compile(r"^[\w\-]{1,60}$")
EXTENSIONES = {"python": "py", "py": "py", "bash": "sh", "sh": "sh", "shell": "sh", "zsh": "sh",
               "powershell": "ps1", "ps1": "ps1", "pwsh": "ps1", "c": "c", "cpp": "cpp", "c++": "cpp", "h": "h",
               "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts", "json": "json", "yaml": "yaml",
               "yml": "yml", "toml": "toml", "ini": "ini", "html": "html", "css": "css", "sql": "sql", "rust": "rs",
               "go": "go", "java": "java", "lua": "lua", "markdown": "md", "md": "md", "makefile": "mk",
               "batch": "bat", "bat": "bat", "cmd": "cmd", "fam": "fam", "xml": "xml", "csv": "csv", "txt": "txt"}


class ProyectoError(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str, **extra: Any):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje, self.extra = status, codigo, mensaje, extra


def _slug(texto: str, largo: int = 60) -> str:
    s = re.sub(r"[^\w\-]+", "_", texto.strip(), flags=re.UNICODE).strip("_")
    return s[:largo] or "sin_nombre"


def _documentos() -> Path:
    return Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"


def _prohibidas() -> list[Path]:
    """Carpetas donde un proyecto no puede vivir (el sistema y la propia FORJA: código y datos)."""
    out = [ROOT_DIR, data_dir()]
    for var in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        if os.environ.get(var):
            out.append(Path(os.environ[var]))
    return [p.resolve() for p in out]


def _dentro(p: Path, base: Path) -> bool:
    try:
        p.relative_to(base)
        return True
    except ValueError:
        return False


class Proyectos:
    def __init__(self, db: DB):
        self.db = db

    # --- carpetas --------------------------------------------------------------
    def dir_base(self) -> Path:
        elegido = (self.db.get_setting("proyectos.dir", "") or "").strip()
        # Ojo: "Documents\FORJA" sería la carpeta de la propia app (Documents\forja) en Windows.
        return Path(elegido) if elegido else _documentos() / "FORJA proyectos"

    def carpeta_sugerida(self, nombre: str) -> str:
        return str(self.dir_base() / _slug(nombre or "proyecto"))

    @staticmethod
    def validar_carpeta(carpeta: str) -> Path:
        crudo = os.path.expandvars(os.path.expanduser((carpeta or "").strip().strip('"')))
        if not crudo:
            raise ProyectoError(400, "CARPETA_INVALIDA", "Indica la carpeta del proyecto.")
        p = Path(crudo)
        if not p.is_absolute():
            raise ProyectoError(400, "CARPETA_INVALIDA", "La carpeta debe ser una ruta completa (p. ej. C:\\…).")
        p = p.resolve()
        if p.parent == p:
            raise ProyectoError(400, "CARPETA_INVALIDA", "No uses la raíz de una unidad: crea una carpeta para el proyecto.")
        for prohibida in _prohibidas():
            if _dentro(p, prohibida) or _dentro(prohibida, p):
                raise ProyectoError(400, "CARPETA_PROHIBIDA",
                                    f"No puedo usar {p}: es (o contiene) una carpeta del sistema o de la propia FORJA.")
        if p.exists() and not p.is_dir():
            raise ProyectoError(400, "CARPETA_INVALIDA", "Esa ruta es un archivo, no una carpeta.")
        return p

    # --- CRUD (API-030) ----------------------------------------------------------
    def _resumen(self, f: dict[str, Any]) -> dict[str, Any]:
        n = self.db.one("SELECT COUNT(*) AS n FROM conversations WHERE project_id = ?", (f["id"],))["n"]
        return {**f, "n_hilos": n, "existe": Path(f["carpeta"]).is_dir()}

    def listar(self) -> list[dict[str, Any]]:
        return [self._resumen(f) for f in self.db.query(
            "SELECT * FROM projects ORDER BY COALESCE(updated_at, created_at) DESC, id DESC")]

    def ver(self, pid: int | None) -> dict[str, Any]:
        f = self.db.one("SELECT * FROM projects WHERE id = ?", (pid,)) if pid is not None else None
        if not f:
            raise ProyectoError(404, "PROYECTO_NO_EXISTE", "Ese proyecto no existe.")
        return self._resumen(f)

    def crear(self, nombre: str, carpeta: str | None, descripcion: str = "") -> dict[str, Any]:
        nombre = (nombre or "").strip()
        if not nombre:
            raise ProyectoError(400, "NOMBRE_VACIO", "Ponle nombre al proyecto.")
        p = self.validar_carpeta(carpeta or self.carpeta_sugerida(nombre))
        if self.db.one("SELECT id FROM projects WHERE lower(carpeta) = lower(?)", (str(p),)):
            raise ProyectoError(409, "CARPETA_EN_USO", "Ya hay un proyecto con esa carpeta.")
        p.mkdir(parents=True, exist_ok=True)
        pid = self.db.execute("INSERT INTO projects(nombre, carpeta, descripcion, updated_at) VALUES (?, ?, ?, ?)",
                              (nombre[:120], str(p), (descripcion or "")[:2000], ahora()))
        audit.registrar(self.db, "proyecto", {"accion": "crear", "proyecto_id": pid, "carpeta": str(p)})
        return self.ver(pid)

    def editar(self, pid: int, cambios: dict[str, Any]) -> dict[str, Any]:
        actual = self.ver(pid)
        sets: dict[str, Any] = {}
        if "nombre" in cambios:
            nombre = str(cambios["nombre"] or "").strip()
            if not nombre:
                raise ProyectoError(400, "NOMBRE_VACIO", "Ponle nombre al proyecto.")
            sets["nombre"] = nombre[:120]
        if "descripcion" in cambios:
            sets["descripcion"] = str(cambios["descripcion"] or "")[:2000]
        if "carpeta" in cambios:
            p = self.validar_carpeta(str(cambios["carpeta"] or ""))
            otro = self.db.one("SELECT id FROM projects WHERE lower(carpeta) = lower(?) AND id != ?", (str(p), pid))
            if otro:
                raise ProyectoError(409, "CARPETA_EN_USO", "Ya hay un proyecto con esa carpeta.")
            p.mkdir(parents=True, exist_ok=True)
            sets["carpeta"] = str(p)
            audit.registrar(self.db, "proyecto", {"accion": "cambiar_carpeta", "proyecto_id": pid,
                                                  "antes": actual["carpeta"], "ahora": str(p)})
        if sets:
            self.db.execute(f"UPDATE projects SET {', '.join(f'{k} = ?' for k in sets)}, updated_at = ? WHERE id = ?",
                            (*sets.values(), ahora(), pid))
        return self.ver(pid)

    def borrar(self, pid: int) -> None:
        """Borra el proyecto de FORJA; la carpeta y sus archivos se quedan donde están."""
        self.ver(pid)
        self.db.execute("DELETE FROM projects WHERE id = ?", (pid,))
        audit.registrar(self.db, "proyecto", {"accion": "borrar", "proyecto_id": pid})

    def archivos(self, pid: int, limite: int = 200) -> list[dict[str, Any]]:
        base = Path(self.ver(pid)["carpeta"])
        if not base.is_dir():
            return []
        out: list[dict[str, Any]] = []
        for raiz, dirs, ficheros in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in IGNORAR and not d.startswith("."))
            nivel = len(Path(raiz).relative_to(base).parts)
            if nivel >= 3:
                dirs[:] = []
            for f in sorted(ficheros):
                ruta = Path(raiz) / f
                try:
                    tam = ruta.stat().st_size
                except OSError:
                    continue
                out.append({"ruta": ruta.relative_to(base).as_posix(), "bytes": tam})
                if len(out) >= limite:
                    return out
        return out

    def contexto_prompt(self, pid: int | None) -> str:
        """Lo que el modelo sabe del proyecto del hilo: nombre, descripción y archivos (sin contenido)."""
        if pid is None:
            return ""
        try:
            p = self.ver(pid)
        except ProyectoError:
            return ""
        nombres = [a["ruta"] for a in self.archivos(pid, 40)]
        lineas = [f"Proyecto activo: «{p['nombre']}».",
                  "Cuando des código para un archivo, indica su ruta relativa en el proyecto (p. ej. `src/main.py`) "
                  "en la línea anterior al bloque: el usuario lo guarda con el botón Guardar."]
        if p.get("descripcion"):
            lineas.insert(1, f"Descripción: {p['descripcion'][:400]}")
        if nombres:
            lineas.append("Archivos del proyecto: " + ", ".join(nombres))
        return "\n".join(lineas)

    # --- API-031 guardar a archivo (ST-040: propuesta → confirmada → ejecutada) --------------
    @staticmethod
    def normalizar_nombre(nombre: str) -> str:
        n = (nombre or "").strip().replace("\\", "/")
        if not n:
            raise ProyectoError(400, "NOMBRE_INVALIDO", "Indica el nombre del archivo.")
        if len(n) > 200:
            raise ProyectoError(400, "NOMBRE_INVALIDO", "El nombre es demasiado largo.")
        if n.startswith("/") or re.match(r"^[A-Za-z]:", n):
            raise ProyectoError(400, "FUERA_DEL_PROYECTO", "Usa una ruta relativa a la carpeta del proyecto.")
        partes = n.split("/")
        for parte in partes:
            if parte in ("", ".", ".."):
                raise ProyectoError(400, "FUERA_DEL_PROYECTO", "La ruta no puede contener «..» ni tramos vacíos.")
            if RE_PROHIBIDOS.search(parte) or parte.endswith((".", " ")):
                raise ProyectoError(400, "NOMBRE_INVALIDO", f"«{parte}» no es un nombre válido en Windows.")
            if parte.split(".")[0].upper() in RESERVADOS:
                raise ProyectoError(400, "NOMBRE_INVALIDO", f"«{parte}» es un nombre reservado de Windows.")
        return "/".join(partes)

    def ruta_segura(self, pid: int, nombre: str) -> tuple[dict[str, Any], Path, str]:
        p = self.ver(pid)
        base = Path(p["carpeta"]).resolve()
        rel = self.normalizar_nombre(nombre)
        destino = (base / rel).resolve()          # resuelve también enlaces simbólicos
        if not _dentro(destino, base) or destino == base:
            raise ProyectoError(400, "FUERA_DEL_PROYECTO", "Solo puedo escribir dentro de la carpeta del proyecto.")
        return p, destino, rel

    def guardar_archivo(self, pid: int, nombre: str, contenido: str, confirmado: bool = False,
                        sobrescribir: bool = False) -> dict[str, Any]:
        p, destino, rel = self.ruta_segura(pid, nombre)
        datos = (contenido or "").encode("utf-8")
        if len(datos) > MAX_ARCHIVO:
            raise ProyectoError(413, "ARCHIVO_GRANDE", "El archivo pasa de 2 MB.")
        existe = destino.exists()
        if existe and destino.is_dir():
            raise ProyectoError(400, "NOMBRE_INVALIDO", "Ya hay una carpeta con ese nombre.")
        propuesta = {"ruta": str(destino), "relativa": rel, "existe": existe, "bytes": len(datos),
                     "proyecto": p["nombre"]}
        if not confirmado:
            raise ProyectoError(409, "CONFIRMACION_REQUERIDA", f"Confirma que quieres guardar {rel} en «{p['nombre']}».",
                                propuesta=propuesta)
        if existe and not sobrescribir:
            raise ProyectoError(409, "SOBRESCRIBIR", f"{rel} ya existe. Confirma que quieres sobrescribirlo.",
                                propuesta=propuesta)
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(destino.name + ".forja-tmp")
        tmp.write_bytes(datos)
        os.replace(tmp, destino)
        self.db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (ahora(), pid))
        audit.registrar(self.db, "guardar_archivo", {"proyecto_id": pid, "ruta": rel, "bytes": len(datos),
                                                     "sobrescrito": existe})
        return {**propuesta, "guardado": True, "sobrescrito": existe}


# --- BTN-032 plantillas -----------------------------------------------------------------
class Plantillas:
    """Andamiajes en `backend/plantillas/*.md` (de serie) + los tuyos en la carpeta de usuario, que mandan."""

    def __init__(self, db: DB):
        self.db = db

    def dir_usuario(self) -> Path:
        elegido = (self.db.get_setting("plantillas.dir", "") or "").strip()
        return Path(elegido) if elegido else data_dir() / "plantillas"

    @staticmethod
    def leer(ruta: Path) -> dict[str, Any] | None:
        if not RE_ID_PLANTILLA.match(ruta.stem):
            return None
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        meta: dict[str, str] = {}
        cabecera, sep, cuerpo = texto.partition("\n---\n")
        if not sep:
            cabecera, cuerpo = "", texto
        for linea in cabecera.splitlines():
            if ":" in linea:
                k, v = linea.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        return {"id": ruta.stem, "nombre": meta.get("nombre", ruta.stem), "descripcion": meta.get("descripcion", ""),
                "lenguaje": meta.get("lenguaje", ""), "orden": int(meta.get("orden", "50") or 50),
                "contenido": cuerpo.strip("\n") + "\n"}

    def listar(self) -> list[dict[str, Any]]:
        todas: dict[str, dict[str, Any]] = {}
        for origen, carpeta in (("serie", PLANTILLAS_SERIE), ("usuario", self.dir_usuario())):
            if carpeta.is_dir():
                for f in sorted(carpeta.glob("*.md")):
                    pl = self.leer(f)
                    if pl:
                        todas[pl["id"]] = {**pl, "origen": origen}
        return sorted(todas.values(), key=lambda p: (p["orden"], p["nombre"]))

    def ver(self, pid: str) -> dict[str, Any]:
        for p in self.listar():
            if p["id"] == pid:
                return p
        raise ProyectoError(404, "PLANTILLA_NO_EXISTE", "Esa plantilla no existe.")


# --- API-062 export de conversaciones ------------------------------------------------------
def conversacion_markdown(db: DB, cid: int, incluir_razonamiento: bool = True) -> tuple[dict[str, Any], str]:
    conv = db.one("SELECT * FROM conversations WHERE id = ?", (cid,))
    if conv is None:
        raise ProyectoError(404, "CONVERSACION_NO_EXISTE", "La conversación no existe.")
    msgs = db.query("SELECT * FROM messages WHERE conversation_id = ? AND rol IN ('user','assistant') ORDER BY id",
                    (cid,))
    if not msgs:
        raise ProyectoError(400, "CONVERSACION_VACIA", "La conversación no tiene mensajes.")
    titulo = conv["titulo"] or "Conversación"
    meta = [f"Modo: {conv['modo']}"]
    if conv["project_id"]:
        p = db.one("SELECT nombre FROM projects WHERE id = ?", (conv["project_id"],))
        if p:
            meta.append(f"Proyecto: {p['nombre']}")
    if conv["engagement_id"]:
        e = db.one("SELECT nombre FROM engagements WHERE id = ?", (conv["engagement_id"],))
        if e:
            meta.append(f"Engagement: {e['nombre']}")
    meta += [f"Creada: {conv['created_at'].replace('T', ' ')}", f"Exportada: {ahora().replace('T', ' ')}",
             f"{len(msgs)} mensajes"]
    partes = [f"# {titulo}", "", " · ".join(meta), "", "---", ""]
    for m in msgs:
        cuando = (m["created_at"] or "").replace("T", " ")
        if m["rol"] == "user":
            partes += [f"## Tú · {cuando}", "", m["contenido"].rstrip(), ""]
            continue
        cab = ["FORJA", m["modelo"] or "", m["tier"] or "", m["esfuerzo"] or ""]
        extra = []
        if m.get("tokens_out"):
            extra.append(f"{m['tokens_out']} tokens")
        if m.get("gen_ms"):
            extra.append(f"{m['gen_ms'] / 1000:.0f} s")
        partes += [f"## {' · '.join(x for x in cab if x)} · {cuando}" + (f" ({', '.join(extra)})" if extra else ""), ""]
        if incluir_razonamiento and m.get("thinking"):
            partes += ["<details><summary>Razonamiento</summary>", "", m["thinking"].strip(), "", "</details>", ""]
        partes += [m["contenido"].rstrip(), ""]
    return conv, "\n".join(partes).rstrip() + "\n"


def exportar_conversacion(db: DB, cid: int, incluir_razonamiento: bool = True) -> dict[str, Any]:
    conv, md = conversacion_markdown(db, cid, incluir_razonamiento)
    carpeta = dir_export(db) / "conversaciones"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{_slug(conv['titulo'] or 'conversacion', 80)}_{datetime.now():%Y%m%d-%H%M%S}.md"
    ruta.write_text(md, encoding="utf-8")
    audit.registrar(db, "export", {"tipo": "conversacion", "conversacion_id": cid, "ruta": str(ruta)})
    return {"ruta": str(ruta), "carpeta": str(carpeta), "nombre": ruta.name, "markdown": md}


def extension_para(lenguaje: str) -> str:
    return EXTENSIONES.get((lenguaje or "").strip().lower(), "txt")
