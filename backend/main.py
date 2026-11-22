"""MOD-001 App Shell (lado backend): API local FastAPI + ventana pywebview.

Arranque (ST-060): backend arriba → la UI llama a /salud → SCR-008 si falta algo → shell.
"""
from __future__ import annotations

import argparse
import asyncio
import hmac
import json
import logging
import os
import secrets
import socket
import threading
import time
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import audit, cloud_client
from . import apariencia, verificador
from .modes import lenguaje
from .modes import tareas as tareas_mod
from .modes.tareas import Organizador, TareasError
from .modes.seguridad import SeguridadError
from .modes.academia import Academia, AcademiaError
from .modes.laboratorio import BACKENDS as LAB_BACKENDS, Laboratorio, LabError
from .modes import proyectos as proy_mod
from .modes.proyectos import Plantillas, ProyectoError
from .cloud_client import MODELOS_NUBE, ClienteNube, NubeError
from .chat import MotorChat, sse
from .config import HOST, OLLAMA_URL, PORT, TOKEN_HEADER, UI_DIR, data_dir
from .db import DB, ahora
from .ollama_client import (ModeloFaltante, OllamaCaido, OllamaClient, OllamaError,
                            arrancar_ollama, ejecutable_ollama, normalizar)
from .router import FAMILIA, OVERRIDE_ESFUERZO
from .sistema import disco_libre_mb, ram_libre_mb

log = logging.getLogger("forja")

# Modelos sin los que la Rama 1 no funciona (Scripts + Pequeño). El resto son opcionales.
NECESARIOS = {"pequeno-codigo"}
PREFIJOS_AJUSTES_EDITABLES = ("ui.", "estado.", "umbral.", "plan.", "tareas.")
CLAVES_ACADEMIA = {"seguridad.enfoque": ("ofensivo", "defensivo"), "seguridad.actividad": ("trabajo", "aprender"),
                   "lab.backend": LAB_BACKENDS, "lab.distro": None, "lab.working_dir": None,
                   "lab.attackbox_url": None, "academia.seccion": None, "academia.xp_por_dificultad": None}
CLAVES_NUBE = {"nube.activada", "nube.modelo", "nube.api_key", "nube.backend", "nube.claude_bin"}
# Rama 5 (SCR-007 completo): rutas (deben ser absolutas; '' = la de serie) y opciones con valores cerrados.
CLAVES_RUTA = {"proyectos.dir", "plantillas.dir", "export.dir"}
CLAVES_CERRADAS = {
    "modelos.precargar": ("0", "1"),
    # ui.tema, ui.acento, ui.densidad, ui.tipografia, ui.base, ui.fondo… → backend/apariencia.py (Rama 8).
    "ui.razonamiento": ("plegar", "mostrar"),
    "ui.telemetria": ("0", "1"),
    # Rama 6 — Protocolo de Personalización (doc 13): una clave por pregunta PREGUNTAR.
    "ui.pestanas": ("icono+texto", "texto", "icono"),                       # S1
    "ui.esfuerzo_control": ("segmentos", "deslizador"),                     # S2
    "ui.mostrar_modelo": ("tier+tooltip", "tier+modelo"),                   # S3
    "ui.proyectos": ("desplegable", "fijo"),                                # SC1
    "ui.codigo_tema": ("acorde", "oscuro", "alto-contraste"),               # SC2
    "ui.gate": ("pantalla_completa", "asistente"),                          # SG1
    "ui.hallazgos": ("tabla", "tarjetas"),                                  # SG2
    "ui.informe_plantilla": ("hackerone", "bugcrowd", "breve", "personalizada"),   # SG3
    "ui.tareas_vista": ("tablero", "lista"),                                # ST1
    "ui.tareas_carga": ("0", "1"),                                          # ST2
    "ui.aviso_escalado": ("modal-nube+banner-justo", "modal", "banner"),    # SE1
    "ui.ajustes": ("pestanas", "pagina"),                                   # SA1
}
MAX_INFORME_ESTRUCTURA = 4000   # SG3 "editable": estructura propia del informe (Markdown)


class ApiError(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str):
        self.status, self.codigo, self.mensaje = status, codigo, mensaje


def _err(status: int, codigo: str, mensaje: str) -> JSONResponse:
    return JSONResponse({"error": {"codigo": codigo, "mensaje": mensaje}}, status_code=status)


class TokenMiddleware:
    """Cabecera X-Forja-Token: impide que otra app del equipo hable con el backend (07-...md)."""

    ABIERTAS = ("/ui/",)

    def __init__(self, app, token: str):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope["path"]
            if path != "/" and not path.startswith(self.ABIERTAS):
                recibido = dict(scope["headers"]).get(TOKEN_HEADER.lower().encode(), b"").decode()
                if not hmac.compare_digest(recibido, self.token):
                    await _err(401, "NO_AUTORIZADO", "Falta o no coincide el token local.")(scope, receive, send)
                    return
        await self.app(scope, receive, send)


# --- cuerpos de petición -----------------------------------------------------
Modo = Literal["scripts", "seguridad", "tareas"]
Tier = Literal["pequeno", "grande", "nube"]
Esfuerzo = Literal["bajo", "medio", "extra"]


class ChatIn(BaseModel):
    sesion_id: int | None = None
    modo: Modo
    tier: Tier
    esfuerzo: Esfuerzo
    texto: str = Field(max_length=200_000)
    adjuntos: list[Any] = []
    engagement_id: int | None = None
    forzar: bool = False  # el usuario ya decidió seguir pese al aviso del estimador


class PreviaIn(BaseModel):
    """Rama 8: estado ui.* a previsualizar (sin guardar) y el tema que ve el usuario si es «sistema»."""
    estado: dict[str, Any] = Field(default_factory=dict)
    tema_efectivo: str | None = None


class VerificarIn(BaseModel):
    lenguaje: str | None = Field(default=None, max_length=40)
    codigo: str = Field(max_length=verificador.MAX_CODIGO)


class InstalarVerifIn(BaseModel):
    id: str = Field(max_length=40)
    confirmado: bool = False


class ErrorVerif(BaseModel):
    linea: int | None = None
    columna: int | None = None
    mensaje: str = Field(default="", max_length=2000)
    severidad: str = "error"


class CorregirIn(BaseModel):
    sesion_id: int | None = None
    tier: Tier
    esfuerzo: Esfuerzo
    lenguaje: str | None = Field(default=None, max_length=40)
    codigo: str = Field(max_length=verificador.MAX_CODIGO)
    errores: list[ErrorVerif] = Field(default_factory=list, max_length=200)


class EstimarIn(BaseModel):
    sesion_id: int | None = None
    modo: Modo
    tier: Tier
    esfuerzo: Esfuerzo
    texto: str = Field(max_length=200_000)


class TrocearIn(BaseModel):
    modo: Modo = "scripts"
    texto: str = Field(min_length=1, max_length=200_000)


class EngagementIn(BaseModel):
    nombre: str = Field(max_length=120)
    alcance: str = Field(max_length=5000)
    notas: str = Field(default="", max_length=5000)


class AnalizarIn(BaseModel):
    datos_recon: str = Field(max_length=2_000_000)
    tier: Tier = "pequeno"
    esfuerzo: Esfuerzo = "medio"


class InformeIn(BaseModel):
    enfoques: list[str] = []
    tier: Tier = "pequeno"
    esfuerzo: Esfuerzo = "medio"


class ExportIn(BaseModel):
    tipo: Literal["informe", "conversacion"]
    id: int
    incluir_razonamiento: bool = True


class ProyectoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    carpeta: str | None = Field(default=None, max_length=1000)
    descripcion: str = Field(default="", max_length=2000)


class GuardarArchivoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    contenido: str = Field(max_length=3_000_000)
    confirmado: bool = False      # ST-040: la UI lo pone a true solo tras el modal de confirmación
    sobrescribir: bool = False


class ElegirCarpetaIn(BaseModel):
    inicial: str | None = Field(default=None, max_length=1000)


class ListaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)


class TareasIn(BaseModel):
    lista_id: int
    texto: str = Field(min_length=1, max_length=50_000)
    parent_id: int | None = None


class InterpretarIn(BaseModel):
    texto: str = Field(max_length=50_000)


class OrganizarIn(BaseModel):
    lista_id: int
    esfuerzo: Esfuerzo = "medio"
    tier: Tier = "pequeno"


class LabDeclaraIn(BaseModel):
    entorno: Literal["htb", "thm", "local", "ctf", "otro"]
    descripcion: str = Field(max_length=300)
    declaracion: bool = False


class SeccionIn(BaseModel):
    seccion_id: int
    tier: Tier = "pequeno"
    esfuerzo: Esfuerzo = "medio"


class PistaIn(SeccionIn):
    duda: str = Field(default="", max_length=2000)


class ComprobarIn(SeccionIn):
    respuesta: str = Field(max_length=2000)


class GenerarIn(BaseModel):
    tier: Tier = "pequeno"
    esfuerzo: Esfuerzo = "medio"


class CopilotoIn(BaseModel):
    seccion_id: int | None = None
    texto: str = Field(default="", max_length=20_000)
    tier: Tier = "pequeno"
    esfuerzo: Esfuerzo = "medio"


class LabConfigIn(BaseModel):
    backend: Literal["wsl", "attackbox", "virtualbox"]
    confirmado: bool = False
    distro: str | None = Field(default=None, max_length=64)
    url: str | None = Field(default=None, max_length=500)


class LabAbrirIn(BaseModel):
    seccion_id: int
    backend: Literal["wsl", "attackbox", "virtualbox"] | None = None


class IdIn(BaseModel):
    seccion_id: int | None = None
    path_id: int | None = None


class AliasIn(BaseModel):
    alias: str


class ConversacionIn(BaseModel):
    modo: Modo
    project_id: int | None = None
    engagement_id: int | None = None


class ConversacionPatch(BaseModel):
    titulo: str | None = Field(default=None, max_length=200)
    archivada: bool | None = None
    project_id: int | None = None


def create_app(db_path: Path | None = None, ollama_transport: httpx.AsyncBaseTransport | None = None,
               precargar: bool = True, token: str | None = None, nube: ClienteNube | None = None,
               lab_detector: dict[str, Any] | None = None, abrir_carpeta=None) -> FastAPI:
    db = DB(db_path or data_dir() / "forja.db")
    ollama = OllamaClient(OLLAMA_URL, transport=ollama_transport)
    nube = nube or ClienteNube()
    motor = MotorChat(db, ollama, nube)
    cloud_client.configurar_bin(db.get_setting("nube.claude_bin", ""))
    token = token or secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tarea = asyncio.create_task(_precarga()) if precargar and db.get_setting("modelos.precargar") == "1" else None
        yield
        if tarea:
            tarea.cancel()

    async def _precarga():
        """Precarga el modelo del último modo/tier para que el primer mensaje sea rápido."""
        try:
            modo, tier = db.get_setting("estado.modo", "scripts"), db.get_setting("estado.tier", "pequeno")
            if modo != "scripts" or tier == "nube":
                modo, tier = "scripts", "pequeno"
            fila = db.one("SELECT etiqueta FROM models WHERE alias = ?", (FAMILIA[(modo, tier)],))
            if fila and normalizar(fila["etiqueta"]) in await ollama.instalados():
                await ollama.cargar(fila["etiqueta"])
        except Exception as e:  # nunca romper el arranque por la precarga
            log.info("Precarga omitida: %s", e)

    app = FastAPI(title="FORJA", version="0.1", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.db, app.state.ollama, app.state.token = db, ollama, token
    app.state.elegir_carpeta = None    # main() lo conecta al diálogo nativo de pywebview si hay ventana

    def _abrir(ruta: str) -> None:
        """Abre una carpeta en el Explorador (inyectable en las pruebas)."""
        if abrir_carpeta is not None:
            abrir_carpeta(ruta)
        elif hasattr(os, "startfile"):
            os.startfile(ruta)  # noqa: S606 — solo carpetas que FORJA conoce (proyecto, export, plantillas)
    app.add_middleware(TokenMiddleware, token=token)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError):
        return _err(e.status, e.codigo, e.mensaje)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, e: RequestValidationError):
        detalle = "; ".join(f"{'.'.join(str(x) for x in err['loc'][1:])}: {err['msg']}" for err in e.errors())
        return _err(422, "PETICION_INVALIDA", detalle)

    # --- UI -------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index():
        html = (UI_DIR / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(html.replace("__FORJA_TOKEN__", token), headers={"Cache-Control": "no-store"})

    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

    # --- API-001 salud ----------------------------------------------------------
    def _registro() -> list[dict[str, Any]]:
        return db.query("SELECT * FROM models ORDER BY CASE tier WHEN 'pequeno' THEN 0 WHEN 'grande' THEN 1 ELSE 2 END, alias")

    @app.get("/salud")
    async def salud():
        version = await ollama.version()
        instalados: list[str] = []
        cargados: list[str] = []
        if version:
            try:
                instalados, cargados = await ollama.instalados(), await ollama.cargados()
            except OllamaCaido:
                version = None
        modelos = []
        for m in _registro():
            if m["tier"] == "nube":
                continue
            inst = normalizar(m["etiqueta"]) in instalados
            if version:
                db.execute("UPDATE models SET instalado = ? WHERE alias = ?", (int(inst), m["alias"]))
            modelos.append({**m, "instalado": inst, "necesario": m["alias"] in NECESARIOS})
        return {
            "ollama": "ok" if version else "caido",
            "ollama_version": version,
            "ollama_instalado": ejecutable_ollama() is not None,
            "modelos_instalados": instalados,
            "modelo_cargado": cargados[0] if cargados else None,
            "modelos": modelos,
            "faltan_necesarios": bool(version) and any(m["necesario"] and not m["instalado"] for m in modelos),
            "ram_libre_mb": ram_libre_mb(),
            "disco_libre_mb": disco_libre_mb(db.path.parent),
            **(await _estado_nube()),
        }

    async def _estado_nube() -> dict[str, Any]:
        """ADR-0006: si Claude Code falta o no tiene sesión, el tier Nube se deshabilita y se guía."""
        backend = cloud_client.backend_nube(db)
        estado = None
        if backend == "claude_code" and db.get_setting("nube.activada") == "1":
            estado = await asyncio.to_thread(cloud_client.comprobar_sesion)
        return {"nube_activada": cloud_client.activada(db), "nube_backend": backend, "nube_estado": estado}

    @app.post("/ollama/arrancar")
    async def ollama_arrancar():
        if await ollama.version():
            return {"lanzado": False, "ya_estaba": True, "instalado": True}
        if not arrancar_ollama():
            return {"lanzado": False, "ya_estaba": False, "instalado": False,
                    "instrucciones": "Instala Ollama desde https://ollama.com/download o con: winget install Ollama.Ollama"}
        for _ in range(20):  # hasta ~10 s
            await asyncio.sleep(0.5)
            if await ollama.version():
                break
        return {"lanzado": True, "ya_estaba": False, "instalado": True, "ok": bool(await ollama.version())}

    # --- API-002/003 chat ---------------------------------------------------------
    @app.post("/chat")
    async def chat(cuerpo: ChatIn):
        gen = motor.generar(cuerpo.sesion_id, cuerpo.modo, cuerpo.tier, cuerpo.esfuerzo, cuerpo.texto, cuerpo.forzar,
                            engagement_id=cuerpo.engagement_id)
        return StreamingResponse(gen, media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # --- API-032 verificador de código (MOD-110, doc 23) ------------------------------
    @app.exception_handler(verificador.VerificadorError)
    async def _verif_error(_: Request, e: verificador.VerificadorError):
        return _err(e.status, e.codigo, e.mensaje)

    @app.post("/scripts/verificar")
    async def scripts_verificar(cuerpo: VerificarIn):
        """Análisis ESTÁTICO del bloque (nunca lo ejecuta). ok:false + aviso si falta la herramienta."""
        return await verificador.verificar(cuerpo.lenguaje, cuerpo.codigo)

    @app.get("/scripts/verificar/herramientas")
    async def scripts_verificar_herramientas():
        return await asyncio.to_thread(verificador.herramientas)

    @app.post("/scripts/verificar/instalar")
    async def scripts_verificar_instalar(cuerpo: InstalarVerifIn):
        """ST-040: sin confirmado devuelve la propuesta; con él, abre winget en una ventana aparte (auditado)."""
        r = verificador.instalar(cuerpo.id, cuerpo.confirmado)
        if cuerpo.confirmado:
            audit.registrar(db, "verificador_instalar", {"id": cuerpo.id, "comando": r["comando"], "confirmado": True})
        return r

    @app.post("/scripts/corregir")
    async def scripts_corregir(cuerpo: CorregirIn):
        """BTN-102 «Corregir con la IA»: código + errores → Motor de Chat (mismo hilo, mismo streaming que /chat)."""
        texto = verificador.prompt_correccion(cuerpo.lenguaje, cuerpo.codigo, [e.model_dump() for e in cuerpo.errores])
        gen = motor.generar(cuerpo.sesion_id, "scripts", cuerpo.tier, cuerpo.esfuerzo, texto, True)
        return StreamingResponse(gen, media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # --- API-010/011/012 modelos ----------------------------------------------------
    def _fila_modelo(alias: str) -> dict[str, Any]:
        fila = db.one("SELECT * FROM models WHERE alias = ?", (alias,))
        if fila is None:
            raise ApiError(404, "MODELO_DESCONOCIDO", f"No existe el alias '{alias}'.")
        if fila["tier"] == "nube" or not fila["etiqueta"]:
            raise ApiError(400, "MODELO_NO_LOCAL", "Ese alias no es un modelo local de Ollama.")
        return fila

    @app.get("/modelos")
    async def modelos():
        familia: dict[str, dict[str, str]] = {}
        for (modo, tier), alias in FAMILIA.items():
            familia.setdefault(modo, {})[tier] = alias
        override = {f"{m}:{e}": o["familia"] for (m, e), o in OVERRIDE_ESFUERZO.items() if "familia" in o}   # "seguridad:bajo"
        return {"modelos": _registro(), "familia": familia, "override": override}

    @app.post("/modelos/descargar")
    async def modelos_descargar(cuerpo: AliasIn):
        fila = _fila_modelo(cuerpo.alias)

        async def progreso():
            inicio = time.monotonic()
            try:
                async for d in ollama.pull_stream(fila["etiqueta"]):
                    total, hecho = d.get("total"), d.get("completed")
                    yield sse("progreso", {
                        "estado": d.get("status", ""), "total": total, "completado": hecho,
                        "porcentaje": round(hecho * 100 / total, 1) if total and hecho else None,
                    })
                db.execute("UPDATE models SET instalado = 1 WHERE alias = ?", (fila["alias"],))
                audit.registrar(db, "descarga_modelo", {"alias": fila["alias"], "etiqueta": fila["etiqueta"],
                                                        "segundos": round(time.monotonic() - inicio)})
                yield sse("fin", {"alias": fila["alias"], "etiqueta": fila["etiqueta"]})
            except OllamaCaido:
                yield sse("error", {"codigo": "OLLAMA_CAIDO", "mensaje": "Ollama no responde."})
            except OllamaError as e:
                yield sse("error", {"codigo": "OLLAMA_ERROR", "mensaje": str(e)})

        return StreamingResponse(progreso(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.post("/modelos/cargar")
    async def modelos_cargar(cuerpo: AliasIn):
        fila = _fila_modelo(cuerpo.alias)
        try:
            await ollama.cargar(fila["etiqueta"])
        except OllamaCaido:
            raise ApiError(503, "OLLAMA_CAIDO", "Ollama no responde en localhost:11434.")
        except ModeloFaltante:
            raise ApiError(404, "MODELO_FALTANTE", f"El modelo {fila['etiqueta']} no está descargado.")
        except OllamaError as e:
            raise ApiError(502, "OLLAMA_ERROR", str(e))
        return {"cargado": normalizar(fila["etiqueta"]), "alias": fila["alias"]}

    # --- API-020..023 conversaciones -------------------------------------------------
    def _conv(cid: int) -> dict[str, Any]:
        c = db.one("SELECT * FROM conversations WHERE id = ?", (cid,))
        if c is None:
            raise ApiError(404, "CONVERSACION_NO_EXISTE", "La conversación no existe.")
        return c

    @app.get("/conversaciones")
    async def conversaciones(modo: Modo | None = None, archivadas: bool = False, engagement: int | None = None,
                             proyecto: int | None = None):
        sql = ("SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS n_mensajes "
               "FROM conversations c WHERE c.archivada = ?")
        params: list[Any] = [int(archivadas)]
        if modo:
            sql += " AND c.modo = ?"
            params.append(modo)
        if engagement is not None:
            sql += " AND c.engagement_id = ?"
            params.append(engagement)
        if proyecto is not None:
            sql += " AND c.project_id = ?"
            params.append(proyecto)
        return {"conversaciones": db.query(sql + " ORDER BY c.updated_at DESC, c.id DESC", tuple(params))}

    @app.post("/conversaciones", status_code=201)
    async def conversacion_crear(cuerpo: ConversacionIn):
        if cuerpo.project_id is not None:
            motor.proyectos.ver(cuerpo.project_id)
        cid = db.execute("INSERT INTO conversations(modo, project_id, engagement_id) VALUES (?, ?, ?)",
                         (cuerpo.modo, cuerpo.project_id, cuerpo.engagement_id))
        return _conv(cid)

    @app.get("/conversaciones/{cid}/mensajes")
    async def conversacion_mensajes(cid: int):
        _conv(cid)
        return {"mensajes": db.query("SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (cid,))}

    @app.patch("/conversaciones/{cid}")
    async def conversacion_editar(cid: int, cuerpo: ConversacionPatch):
        _conv(cid)
        cambios = cuerpo.model_dump(exclude_unset=True)
        if cambios.get("project_id") is not None:
            motor.proyectos.ver(cambios["project_id"])   # BTN-036: solo proyectos que existen
        if "archivada" in cambios:
            cambios["archivada"] = int(cambios["archivada"])
        if cambios:
            sets = ", ".join(f"{k} = ?" for k in cambios)
            db.execute(f"UPDATE conversations SET {sets}, updated_at = ? WHERE id = ?",
                       (*cambios.values(), ahora(), cid))
        return _conv(cid)

    @app.delete("/conversaciones/{cid}", status_code=204)
    async def conversacion_borrar(cid: int):
        _conv(cid)
        db.execute("DELETE FROM conversations WHERE id = ?", (cid,))

    # --- API-060/061 ajustes y auditoría ----------------------------------------------
    @app.get("/ajustes")
    async def ajustes():
        return {"ajustes": {
            **db.settings(),
            "nube.backend": cloud_client.backend_nube(db),
            "nube.tiene_clave": "1" if cloud_client.tiene_clave() else "0",
            "nube.tiene_cli": "1" if cloud_client.ejecutable_claude() else "0",
            "nube.claude_bin_detectado": cloud_client.detectar_claude() or "",
        }}

    @app.get("/seguridad/plantillas-informe")
    async def plantillas_informe():
        """API-055 (SG3): plantillas de informe — HackerOne, Bugcrowd, breve y la propia del usuario — para que
        Ajustes y el redactor (SCR-022) las ofrezcan. La propia va vacía si aún no se ha escrito (el redactor
        usaría entonces HackerOne)."""
        from .modes.seguridad import PLANTILLAS_INFORME, plantilla_informe
        nombre, estructura = plantilla_informe(db)
        plantillas = {k: {"nombre": n, "estructura": e} for k, (n, e) in PLANTILLAS_INFORME.items()}
        plantillas["personalizada"] = {"nombre": "propia",
                                       "estructura": (db.get_setting("ui.informe_estructura", "") or "").strip()}
        return {"plantillas": plantillas,
                "activa": {"id": db.get_setting("ui.informe_plantilla", "hackerone"), "nombre": nombre,
                           "estructura": estructura}}

    # --- Rama 8: Estudio de Apariencia (MOD-100, SCR-040) --------------------------------
    @app.get("/apariencia")
    async def apariencia_catalogo():
        """Presets (BTN-095), acentos, fuentes y mínimos de contraste para el Estudio."""
        return {"presets": apariencia.PRESETS,
                "acentos": {k: v for k, v in apariencia.ACENTOS.items()},
                "bases": apariencia.BASES, "fuentes": list(apariencia.FUENTES), "temas": list(apariencia.TEMAS),
                "minimos": {"texto": apariencia.MIN_TEXTO, "secundario": apariencia.MIN_SECUNDARIO,
                            "acento": apariencia.MIN_ACENTO},
                "opacidad": {"min": apariencia.OPACIDAD_MIN, "max": apariencia.OPACIDAD_MAX}}

    @app.post("/apariencia/previa")
    async def apariencia_previa(cuerpo: PreviaIn):
        """Paleta resultante + problemas de contraste de un estado ui.* sin guardarlo (vista previa en vivo)."""
        estado = {**db.settings(), **cuerpo.estado}
        try:
            for k in list(estado):
                if k in apariencia.CLAVES and k in cuerpo.estado:
                    v = estado[k]
                    estado[k] = apariencia.normalizar(k, v if isinstance(v, str) else json.dumps(v))
        except apariencia.AparienciaError as e:
            raise ApiError(400, e.codigo, e.mensaje)
        return apariencia.paleta(estado, cuerpo.tema_efectivo)

    def _dir_fondos() -> Path:
        d = data_dir() / "fondos"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @app.post("/apariencia/fondo")
    async def apariencia_fondo_subir(request: Request):
        """BTN-098: guarda una imagen local de fondo (png/jpg/webp/gif ≤ 8 MB) en %APPDATA%\\FORJA\\fondos."""
        import hashlib
        datos = await request.body()
        if len(datos) > apariencia.MAX_IMAGEN:
            raise ApiError(400, "IMAGEN_GRANDE", "La imagen supera 8 MB.")
        ext = apariencia.tipo_imagen(datos)
        if not ext:
            raise ApiError(400, "IMAGEN_INVALIDA", "Solo imágenes PNG, JPG, WebP o GIF.")
        nombre = f"{hashlib.sha256(datos).hexdigest()[:16]}.{ext}"
        (_dir_fondos() / nombre).write_bytes(datos)
        return {"archivo": nombre, "bytes": len(datos)}

    @app.get("/apariencia/fondo/{archivo}")
    async def apariencia_fondo(archivo: str):
        from fastapi.responses import FileResponse
        import re as _re
        if not _re.fullmatch(r"[0-9a-f]{16}\.(png|jpg|webp|gif)", archivo):
            raise ApiError(404, "NO_ENCONTRADO", "No existe ese fondo.")
        ruta = _dir_fondos() / archivo
        if not ruta.is_file():
            raise ApiError(404, "NO_ENCONTRADO", "No existe ese fondo.")
        return FileResponse(ruta, headers={"Cache-Control": "no-store"})

    @app.put("/ajustes")
    async def ajustes_guardar(cuerpo: dict[str, str]):
        # Rama 8: formato de las claves de apariencia y contraste del resultado (TST-073).
        try:
            for clave in [k for k in cuerpo if k in apariencia.CLAVES]:
                cuerpo[clave] = apariencia.normalizar(clave, cuerpo[clave])
            if any(k in cuerpo for k in ("ui.tema", "ui.acento", "ui.base", "ui.acento_por_modo")):
                apariencia.validar_contraste({**db.settings(), **cuerpo})
            if "ui.fondo" in cuerpo:
                f = json.loads(cuerpo["ui.fondo"])
                if f["tipo"] == "imagen" and not (_dir_fondos() / f["archivo"]).is_file():
                    raise apariencia.AparienciaError("AJUSTE_INVALIDO", "Esa imagen de fondo ya no existe.")
        except apariencia.AparienciaError as e:
            r = _err(400, e.codigo, e.mensaje)
            if e.problemas:
                cuerpo_r = json.loads(r.body)
                cuerpo_r["error"]["problemas"] = e.problemas
                return JSONResponse(cuerpo_r, status_code=400)
            return r
        for clave, valor in cuerpo.items():
            if clave in apariencia.CLAVES:
                continue
            if clave in CLAVES_ACADEMIA:
                permitidos = CLAVES_ACADEMIA[clave]
                if permitidos and valor not in permitidos:
                    raise ApiError(400, "AJUSTE_INVALIDO", f"'{clave}' admite: {', '.join(permitidos)}.")
                if clave == "academia.xp_por_dificultad":
                    try:
                        tabla = json.loads(valor)
                        assert isinstance(tabla, dict) and all(isinstance(v, int) and 0 <= v <= 10_000 for v in tabla.values())
                    except (ValueError, AssertionError):
                        raise ApiError(400, "AJUSTE_INVALIDO", "XP por dificultad: JSON como {\"facil\": 20}.")
                if clave == "lab.attackbox_url" and valor:
                    try:
                        Laboratorio._validar_url(valor)
                    except LabError as e:
                        raise ApiError(400, e.codigo, e.mensaje)
                continue
            if clave in CLAVES_RUTA:
                ruta = str(valor).strip().strip('"')
                if ruta and not Path(os.path.expandvars(ruta)).is_absolute():
                    raise ApiError(400, "RUTA_INVALIDA", f"'{clave}' debe ser una ruta completa (o vacía).")
                if ruta and clave == "proyectos.dir":
                    try:
                        proy_mod.Proyectos.validar_carpeta(ruta)
                    except ProyectoError as e:
                        raise ApiError(400, e.codigo, e.mensaje)
                cuerpo[clave] = ruta
                continue
            if clave in CLAVES_CERRADAS and valor not in CLAVES_CERRADAS[clave]:
                raise ApiError(400, "AJUSTE_INVALIDO", f"'{clave}' admite: {', '.join(CLAVES_CERRADAS[clave])}.")
            if clave in CLAVES_CERRADAS:
                continue
            if clave == "ui.informe_estructura" and len(valor) > MAX_INFORME_ESTRUCTURA:
                raise ApiError(400, "AJUSTE_INVALIDO", f"La estructura del informe admite {MAX_INFORME_ESTRUCTURA} caracteres.")
            if clave not in CLAVES_NUBE and not clave.startswith(PREFIJOS_AJUSTES_EDITABLES):
                raise ApiError(400, "AJUSTE_NO_EDITABLE", f"'{clave}' no se puede cambiar desde aquí.")
            if clave.startswith("umbral."):
                try:
                    float(valor)
                except ValueError:
                    raise ApiError(400, "UMBRAL_INVALIDO", f"'{clave}' debe ser un número.")
        if "nube.modelo" in cuerpo and cuerpo["nube.modelo"] not in MODELOS_NUBE:
            raise ApiError(400, "NUBE_MODELO", f"Modelos admitidos: {', '.join(MODELOS_NUBE)}.")
        # La clave va al Administrador de credenciales de Windows, NUNCA a la BBDD (NFR-010).
        if "nube.api_key" in cuerpo:
            clave_api = cuerpo["nube.api_key"].strip()
            if clave_api:
                cloud_client.guardar_clave(clave_api)
            else:
                cloud_client.borrar_clave()
                db.set_setting("nube.activada", "0")
        if "nube.claude_bin" in cuerpo:
            ruta = cuerpo["nube.claude_bin"].strip().strip('"')
            if ruta and not Path(ruta).is_file():
                raise ApiError(400, "NUBE_SIN_CLI", f"No existe el ejecutable: {ruta}")
            cuerpo["nube.claude_bin"] = ruta
            cloud_client.configurar_bin(ruta)
        if "nube.backend" in cuerpo and cuerpo["nube.backend"] not in cloud_client.BACKENDS:
            raise ApiError(400, "NUBE_BACKEND", "nube.backend admite: claude_code o api.")
        prov = cuerpo.get("nube.backend") or cloud_client.backend_nube(db)
        activar = cuerpo.get("nube.activada", db.get_setting("nube.activada")) == "1"
        if activar and not cloud_client.listo(db, prov):
            if prov == "claude_code":
                raise ApiError(400, "NUBE_SIN_CLI", "No encuentro Claude Code (claude.exe) en este equipo.")
            raise ApiError(400, "NUBE_SIN_CLAVE", "Guarda primero una clave de Anthropic.")
        if "seguridad.enfoque" in cuerpo and cuerpo["seguridad.enfoque"] != db.get_setting("seguridad.enfoque"):
            audit.registrar(db, "academia_enfoque", {"enfoque": cuerpo["seguridad.enfoque"]})   # L-A4
        for clave, valor in cuerpo.items():
            if clave == "nube.api_key":
                continue
            db.set_setting(clave, str(valor))
            if clave == "nube.modelo":
                db.execute("UPDATE models SET etiqueta = ? WHERE alias = 'nube-frontera'", (valor,))
        return await ajustes()

    @app.post("/nube/probar")
    async def nube_probar():
        try:
            return await nube.probar(db.get_setting("nube.modelo", "claude-opus-5-5"),
                                     backend=cloud_client.backend_nube(db))
        except NubeError as e:
            raise ApiError(400, e.codigo, e.mensaje)

    # --- API-004 estimador y troceo -----------------------------------------------------
    @app.post("/estimar")
    async def estimar(cuerpo: EstimarIn):
        try:
            return motor.estimar(cuerpo.modo, cuerpo.tier, cuerpo.esfuerzo, cuerpo.texto, cuerpo.sesion_id)
        except LookupError as e:
            raise ApiError(404, "SESION_INVALIDA", str(e))

    @app.post("/trocear")
    async def trocear(cuerpo: TrocearIn):
        return await motor.trocear(cuerpo.modo, cuerpo.texto)

    # --- API-050..053 Modo Seguridad (MOD-030) — guardarraíles en modes/seguridad.py ------------------
    seg = motor.seguridad

    @app.exception_handler(SeguridadError)
    async def _seguridad_error(_: Request, e: SeguridadError):
        r = _err(e.status, e.codigo, e.mensaje)
        if e.extra:
            cuerpo = json.loads(r.body)
            cuerpo["error"].update(e.extra)
            r = JSONResponse(cuerpo, status_code=e.status)
        return r

    @app.get("/engagements")
    async def engagements(archivados: bool = False):
        return {"engagements": seg.engagements(archivados)}

    @app.post("/engagements", status_code=201)
    async def engagements_crear(cuerpo: EngagementIn):
        return seg.crear(cuerpo.nombre, cuerpo.alcance, cuerpo.notas)

    @app.get("/engagements/{eid}")
    async def engagements_ver(eid: int):
        return seg.engagement(eid)

    @app.patch("/engagements/{eid}")
    async def engagements_editar(eid: int, cuerpo: dict[str, Any]):
        return seg.editar(eid, cuerpo)

    @app.post("/engagements/{eid}/entrar")
    async def engagements_entrar(eid: int):
        return seg.entrar(eid)

    @app.delete("/engagements/{eid}", status_code=204)
    async def engagements_borrar(eid: int):
        seg.borrar(eid)

    @app.post("/engagements/{eid}/analizar")
    async def engagements_analizar(eid: int, cuerpo: AnalizarIn):
        return await seg.analizar(eid, cuerpo.datos_recon, cuerpo.tier, cuerpo.esfuerzo)

    @app.get("/engagements/{eid}/findings")
    async def findings(eid: int):
        return {"findings": seg.findings(eid)}

    @app.post("/engagements/{eid}/findings", status_code=201)
    async def findings_crear(eid: int, cuerpo: dict[str, Any]):
        return seg.crear_finding(eid, cuerpo)

    @app.post("/findings/{fid}")   # API-052 (la spec usa POST)
    @app.patch("/findings/{fid}")
    async def findings_editar(fid: int, cuerpo: dict[str, Any]):
        return seg.editar_finding(fid, cuerpo)

    @app.delete("/findings/{fid}", status_code=204)
    async def findings_borrar(fid: int):
        seg.borrar_finding(fid)

    @app.post("/findings/{fid}/informe")
    async def findings_informe(fid: int, cuerpo: InformeIn):
        return StreamingResponse(seg.informe(fid, cuerpo.enfoques, cuerpo.tier, cuerpo.esfuerzo),
                                 media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/export")
    async def exportar(cuerpo: ExportIn):
        if cuerpo.tipo == "informe":
            return seg.exportar_informe(cuerpo.id)
        return proy_mod.exportar_conversacion(db, cuerpo.id, cuerpo.incluir_razonamiento)   # API-062 / BTN-060

    @app.post("/export/abrir-carpeta")
    async def exportar_abrir(tipo: Literal["informes", "conversaciones"] = "informes"):
        """Abre en el Explorador la carpeta de exportación (solo esa; nunca una ruta arbitraria)."""
        from .modes.seguridad import dir_export
        carpeta = dir_export(db) / tipo
        carpeta.mkdir(parents=True, exist_ok=True)
        _abrir(str(carpeta))
        return {"carpeta": str(carpeta)}

    # --- API-030/031 proyectos (SCR-011) y BTN-032 plantillas — Rama 5 --------------------------------
    proyectos = motor.proyectos
    plantillas = Plantillas(db)

    @app.exception_handler(ProyectoError)
    async def _proyecto_error(_: Request, e: ProyectoError):
        return JSONResponse({"error": {"codigo": e.codigo, "mensaje": e.mensaje, **e.extra}}, status_code=e.status)

    @app.get("/proyectos")
    async def proyectos_lista():
        return {"proyectos": proyectos.listar(), "dir_base": str(proyectos.dir_base()),
                "selector_nativo": app.state.elegir_carpeta is not None}

    @app.get("/proyectos/sugerencia")
    async def proyectos_sugerencia(nombre: str = ""):
        return {"carpeta": proyectos.carpeta_sugerida(nombre[:120])}

    @app.post("/proyectos", status_code=201)
    async def proyectos_crear(cuerpo: ProyectoIn):          # BTN-034
        return proyectos.crear(cuerpo.nombre, cuerpo.carpeta, cuerpo.descripcion)

    @app.get("/proyectos/{pid}")
    async def proyectos_ver(pid: int):
        return {**proyectos.ver(pid), "archivos": proyectos.archivos(pid)}

    @app.patch("/proyectos/{pid}")
    async def proyectos_editar(pid: int, cuerpo: dict[str, Any]):
        return proyectos.editar(pid, cuerpo)

    @app.delete("/proyectos/{pid}", status_code=204)
    async def proyectos_borrar(pid: int):
        proyectos.borrar(pid)

    @app.post("/proyectos/{pid}/abrir")
    async def proyectos_abrir(pid: int):                    # BTN-035
        p = proyectos.ver(pid)
        Path(p["carpeta"]).mkdir(parents=True, exist_ok=True)
        _abrir(p["carpeta"])
        return {"carpeta": p["carpeta"]}

    @app.post("/proyectos/{pid}/guardar-archivo")
    async def proyectos_guardar(pid: int, cuerpo: GuardarArchivoIn):   # API-031 / BTN-031 (ST-040)
        return proyectos.guardar_archivo(pid, cuerpo.nombre, cuerpo.contenido, cuerpo.confirmado, cuerpo.sobrescribir)

    @app.post("/sistema/elegir-carpeta")
    async def elegir_carpeta(cuerpo: ElegirCarpetaIn):
        """Selector de carpetas del SO (solo con la ventana nativa). Sin ventana, la UI pide la ruta escrita."""
        if app.state.elegir_carpeta is None:
            raise ApiError(501, "SIN_SELECTOR", "El selector de carpetas solo está en la ventana de FORJA; escribe la ruta.")
        ruta = await asyncio.to_thread(app.state.elegir_carpeta, cuerpo.inicial or str(proyectos.dir_base()))
        return {"carpeta": ruta}

    @app.get("/plantillas")
    async def plantillas_lista():
        return {"plantillas": plantillas.listar(), "dir_usuario": str(plantillas.dir_usuario())}

    @app.get("/plantillas/{plid}")
    async def plantillas_ver(plid: str):
        return plantillas.ver(plid)

    @app.post("/plantillas/abrir-carpeta")
    async def plantillas_abrir():
        """Crea (si falta) y abre tu carpeta de plantillas: un .md ahí con el mismo nombre sustituye al de serie."""
        carpeta = plantillas.dir_usuario()
        carpeta.mkdir(parents=True, exist_ok=True)
        leeme = carpeta / "LEEME.txt"
        if not leeme.exists():
            leeme.write_text(
                "Plantillas de FORJA (BTN-032).\n"
                "Cada archivo .md es una plantilla. Cabecera (opcional) y luego una línea con ---:\n\n"
                "nombre: Mi plantilla\ndescripcion: para qué sirve\nlenguaje: python\norden: 60\n---\n"
                "Texto que se inserta en el compositor (puede llevar bloques ```código```).\n\n"
                "Si se llama igual que una de serie (python.md, bash.md, powershell.md, firmware.md), la sustituye.\n",
                encoding="utf-8")
        _abrir(str(carpeta))
        return {"carpeta": str(carpeta)}

    # --- Academia de Seguridad (MOD-090) + Laboratorio Linux y Copiloto (MOD-091) — Rama 4b ---------------
    lab = Laboratorio(db, detector=lab_detector)
    aca = Academia(db, ollama, nube, lab)
    app.state.academia = aca

    @app.exception_handler(AcademiaError)
    async def _academia_error(_: Request, e: AcademiaError):
        return JSONResponse({"error": {"codigo": e.codigo, "mensaje": e.mensaje, **e.extra}}, status_code=e.status)

    @app.exception_handler(LabError)
    async def _lab_error(_: Request, e: LabError):
        return _err(e.status, e.codigo, e.mensaje)

    def _sse_resp(gen):
        return StreamingResponse(gen, media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    def _id(cuerpo: IdIn, campo: str) -> int:
        v = getattr(cuerpo, campo)
        if v is None:
            raise ApiError(422, "PETICION_INVALIDA", f"Falta {campo}.")
        return v

    @app.get("/academia/rutas")
    async def academia_rutas(enfoque: str | None = None):
        return {"rutas": aca.rutas(enfoque), "enfoque": enfoque if enfoque in ("ofensivo", "defensivo") else aca.enfoque(),
                "laboratorio": aca.laboratorio()}

    @app.get("/academia/rutas/{pid}")
    async def academia_ruta(pid: int):
        return aca.ruta(pid)

    @app.post("/academia/enrolar")
    async def academia_enrolar(cuerpo: IdIn):
        return aca.enrolar(_id(cuerpo, "path_id"))

    @app.get("/academia/laboratorio")
    async def academia_lab_ver():
        return {"laboratorio": aca.laboratorio()}

    @app.post("/academia/laboratorio")
    async def academia_lab_declarar(cuerpo: LabDeclaraIn):
        return {"laboratorio": aca.declarar_laboratorio(cuerpo.entorno, cuerpo.descripcion, cuerpo.declaracion)}

    @app.delete("/academia/laboratorio", status_code=204)
    async def academia_lab_revocar():
        aca.revocar_laboratorio()

    @app.get("/academia/leccion/{sid}")
    async def academia_leccion(sid: int):
        return aca.seccion(sid)

    @app.post("/academia/leccion/{sid}/generar")
    async def academia_leccion_generar(sid: int, cuerpo: GenerarIn):
        return _sse_resp(aca.generar_leccion(sid, cuerpo.tier, cuerpo.esfuerzo))

    @app.post("/academia/pista")
    async def academia_pista(cuerpo: PistaIn):
        return await aca.pista(cuerpo.seccion_id, cuerpo.tier, cuerpo.esfuerzo, cuerpo.duda)

    @app.post("/academia/comprobar")
    async def academia_comprobar(cuerpo: ComprobarIn):
        return await aca.comprobar(cuerpo.seccion_id, cuerpo.respuesta, cuerpo.tier, cuerpo.esfuerzo)

    @app.post("/academia/progreso")
    async def academia_progreso(cuerpo: IdIn):
        return aca.completar(_id(cuerpo, "seccion_id"))

    @app.get("/academia/perfil")
    async def academia_perfil():
        return aca.perfil()

    @app.get("/academia/herramientas")
    async def academia_herramientas(enfoque: str | None = None):
        return {"herramientas": aca.herramientas(enfoque)}

    @app.get("/academia/mensajes")
    async def academia_mensajes(seccion: int | None = None):
        return {"mensajes": aca.mensajes(seccion)}

    @app.get("/academia/lab/detectar")
    async def lab_detectar():
        return await asyncio.to_thread(lab.detectar)

    @app.post("/academia/lab/configurar")
    async def lab_configurar(cuerpo: LabConfigIn):
        return await asyncio.to_thread(lab.configurar, cuerpo.backend, cuerpo.confirmado, cuerpo.distro, cuerpo.url)

    @app.post("/academia/lab/contexto")
    async def lab_contexto(cuerpo: IdIn):
        return aca.contexto_lab(_id(cuerpo, "seccion_id"))

    @app.post("/academia/lab/abrir")
    async def lab_abrir(cuerpo: LabAbrirIn):
        return await asyncio.to_thread(aca.abrir_lab, cuerpo.seccion_id, cuerpo.backend)

    @app.post("/academia/lab/carpeta")
    async def lab_carpeta(cuerpo: IdIn):
        """Abre en el Explorador la carpeta del ejercicio (solo carpetas de FORJA-lab)."""
        ctx = aca.contexto_lab(_id(cuerpo, "seccion_id"))
        if hasattr(os, "startfile"):
            os.startfile(ctx["carpeta"])  # noqa: S606 — carpeta propia de FORJA
        return ctx

    @app.post("/academia/copiloto/{accion}")
    async def academia_copiloto(accion: Literal["siguiente", "explicar", "chat"], cuerpo: CopilotoIn):
        return _sse_resp(aca.copiloto(cuerpo.seccion_id, accion, cuerpo.texto, cuerpo.tier, cuerpo.esfuerzo))

    # --- API-040..043 Modo Tareas (MOD-040) ---------------------------------------------------
    org = Organizador(db, ollama, nube)
    app.state.organizador = org

    @app.exception_handler(TareasError)
    async def _tareas_error(_: Request, e: TareasError):
        return _err(e.status, e.codigo, e.mensaje)

    @app.get("/listas")
    async def listas():
        return {"listas": org.listas()}

    @app.post("/listas", status_code=201)
    async def listas_crear(cuerpo: ListaIn):
        return org.crear_lista(cuerpo.nombre)

    @app.patch("/listas/{lid}")
    async def listas_renombrar(lid: int, cuerpo: ListaIn):
        return org.renombrar_lista(lid, cuerpo.nombre)

    @app.delete("/listas/{lid}", status_code=204)
    async def listas_borrar(lid: int):
        org.borrar_lista(lid)

    @app.get("/tareas")
    async def tareas(lista: int):
        db.set_setting("tareas.lista", str(lista))
        return org.vista(lista)

    @app.post("/tareas", status_code=201)
    async def tareas_crear(cuerpo: TareasIn):
        return {"creadas": await org.anadir(cuerpo.lista_id, cuerpo.texto, cuerpo.parent_id)}

    @app.post("/tareas/interpretar")
    async def tareas_interpretar(cuerpo: InterpretarIn):
        """Vista previa de P1 (solo reglas, instantánea) mientras escribes."""
        h = tareas_mod.hoy()
        return {"lineas": [lenguaje.interpretar(l, h) for l in cuerpo.texto.splitlines() if l.strip()][:50]}

    @app.patch("/tareas/{tid}")
    async def tareas_editar(tid: int, cuerpo: dict[str, Any]):
        return org.editar(tid, cuerpo)

    @app.delete("/tareas/{tid}", status_code=204)
    async def tareas_borrar(tid: int):
        org.borrar(tid)

    @app.post("/tareas/organizar")
    async def tareas_organizar(cuerpo: OrganizarIn):
        return await org.organizar(cuerpo.lista_id, cuerpo.esfuerzo, cuerpo.tier)

    @app.get("/auditoria")
    async def auditoria(limite: int = 200):
        filas = db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (max(1, min(limite, 1000)),))
        for f in filas:
            try:
                f["detalle"] = json.loads(f["detalle"]) if f["detalle"] else None
            except ValueError:
                pass
        return {"auditoria": filas}

    return app


# --- arranque de escritorio -------------------------------------------------------
def _puerto_libre(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) != 0


def _puerto_disponible(preferido: int, explicito: bool) -> int:
    """El puerto de siempre si está libre; si lo ocupa otra app (FORJA ya se descartó con el mutex), uno libre."""
    if _puerto_libre(HOST, preferido):
        return preferido
    if explicito:
        raise SystemExit(f"El puerto {preferido} ya está en uso. Elige otro con --puerto.")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        libre = s.getsockname()[1]
    log.info("El puerto %s está ocupado por otra aplicación; uso el %s.", preferido, libre)
    return libre


def _arrancar(args: argparse.Namespace) -> None:
    import uvicorn

    from . import escritorio

    # ST-060 (1/3): una sola FORJA por sesión de Windows.
    if not escritorio.instancia_unica():
        escritorio.mensaje("FORJA ya está abierta. Búscala en la barra de tareas.")
        return
    puerto = _puerto_disponible(args.puerto if args.puerto is not None else PORT, args.puerto is not None)

    # ST-060 (2/3): backend arriba — crea %APPDATA%\FORJA y aplica las migraciones de la BBDD (DB.migrate).
    app = create_app()
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=puerto, log_level="warning"))
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()
    while not server.started:
        if not hilo.is_alive():
            raise RuntimeError("El backend no pudo arrancar (¿otro programa en el puerto?).")
        time.sleep(0.05)

    # ST-060 (3/3): la interfaz comprueba Ollama (/salud) y, si falta Ollama o un modelo necesario, abre
    # SCR-008 con la guía (arrancar Ollama / descargar el modelo); si todo está bien, el shell (SCR-001).
    url = f"http://{HOST}:{puerto}/"
    log.info("FORJA escuchando en %s (datos en %s)", url, app.state.db.path)
    if not args.sin_ventana:
        try:
            import webview
        except ImportError:
            log.warning("pywebview no disponible; abro el navegador.")
        else:
            oscuro = app.state.db.get_setting("ui.tema", "oscuro") == "oscuro"
            ventana = webview.create_window("FORJA", url, width=1200, height=820, min_size=(760, 540),
                                            background_color="#0d0d0e" if oscuro else "#e6e6e3")

            def elegir(inicial: str) -> str | None:
                tipo = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
                r = ventana.create_file_dialog(tipo, directory=inicial if Path(inicial).is_dir() else "")
                return (r[0] if isinstance(r, (list, tuple)) else r) or None

            app.state.elegir_carpeta = elegir
            webview.start()
            server.should_exit = True
            hilo.join(timeout=5)
            return
    webbrowser.open(url)
    try:
        hilo.join()
    except KeyboardInterrupt:
        server.should_exit = True


def main() -> None:
    from . import escritorio
    from .config import CONGELADO

    p = argparse.ArgumentParser(prog="FORJA", description="FORJA — IA local")
    p.add_argument("--sin-ventana", action="store_true", help="abrir en el navegador en vez de en ventana propia")
    p.add_argument("--puerto", type=int, default=None, help=f"puerto local del backend (por defecto {PORT})")
    p.add_argument("--instalar", action="store_true",
                   help="copia FORJA.exe a %%LOCALAPPDATA%%\\Programs\\FORJA y crea los accesos directos con icono")
    args = p.parse_args()
    registro = escritorio.configurar_registro()
    try:
        if args.instalar:
            r = escritorio.instalar()
            escritorio.mensaje(f"FORJA instalada en:\n{r['exe']}\n\nAccesos directos creados en el Escritorio y en el "
                               "menú Inicio. Ábrela con doble clic.")
            return
        _arrancar(args)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — sin consola, el usuario debe ver por qué no arrancó
        log.exception("FORJA no pudo arrancar")
        if CONGELADO or registro:
            escritorio.mensaje(f"FORJA no pudo arrancar:\n\n{e}\n\nDetalles en:\n{registro or escritorio.ruta_log()}",
                               error=True)
            raise SystemExit(1) from e
        raise


if __name__ == "__main__":
    main()
