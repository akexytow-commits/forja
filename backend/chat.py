"""MOD-013 Motor de Chat: bucle de conversación y streaming SSE (API-002/API-003, ST-010, ST-050)."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from . import audit, cloud_client, estimator
from .cloud_client import ClienteNube, NubeError
from .db import DB, ahora
from .ollama_client import ModeloFaltante, OllamaCaido, OllamaClient, OllamaError
from .modes.seguridad import Seguridad, SeguridadError
from .modes.proyectos import Proyectos
from .telemetria import Telemetria, con_ticks, objetivo_tokens
from .router import FAMILIA, RouterError, resolver, tokens_aprox
from dataclasses import replace

MODOS_DISPONIBLES = {"scripts", "seguridad"}  # Tareas tiene vista propia (Rama 3). Seguridad, tras el gate (ST-030).
MARCA_INTERRUMPIDA = "\n\n_[respuesta interrumpida]_"

PROMPT_TROCEO = (
    "Divide el encargo del usuario en entre 3 y 8 pasos secuenciales, cada uno pequeño para hacerse en una "
    "sola petición a un modelo local. Responde SOLO con JSON de la forma "
    '{"pasos": [{"texto": "...", "estimacion_min": 30}]}. Español, verbos en infinitivo. '
    "Cada paso debe producir una parte concreta del código (un módulo, fichero o función) y pedirse por "
    "separado; no incluyas pasos de descargar, instalar ni compilar herramientas."
)


def sse(evento: str, datos: dict[str, Any]) -> str:
    return f"event: {evento}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"


def error(codigo: str, mensaje: str, **extra: Any) -> str:
    return sse("error", {"codigo": codigo, "mensaje": mensaje, **extra})


class MotorChat:
    def __init__(self, db: DB, ollama: OllamaClient, nube: ClienteNube | None = None):
        self.db = db
        self.ollama = ollama
        self.nube = nube or ClienteNube()
        self.seguridad = Seguridad(db, ollama, self.nube)
        self.proyectos = Proyectos(db)
        self._activas: set[int] = set()  # invariante ST-010: una generación por sesión

    def registro(self) -> dict[str, dict[str, Any]]:
        return {r["alias"]: r for r in self.db.query("SELECT * FROM models")}

    def umbrales(self) -> dict[str, float]:
        u = {}
        for k in estimator.UMBRALES_DEFECTO:
            try:
                u[k] = float(self.db.get_setting(f"umbral.{k}", ""))
            except ValueError:
                pass
        return u

    # --- conversaciones ----------------------------------------------------
    def _conversacion(self, sesion_id: int | None, modo: str, engagement_id: int | None = None) -> dict[str, Any]:
        if sesion_id is not None:
            conv = self.db.one("SELECT * FROM conversations WHERE id = ?", (sesion_id,))
            if conv is None:
                raise LookupError("La conversación no existe.")
            if conv["modo"] != modo:
                raise LookupError("La conversación pertenece a otro modo.")
            if modo == "seguridad" and conv["engagement_id"] != engagement_id:
                raise LookupError("La conversación pertenece a otro engagement.")
            return conv
        nuevo = self.db.execute("INSERT INTO conversations(modo, engagement_id) VALUES (?, ?)",
                                (modo, engagement_id if modo == "seguridad" else None))
        return self.db.one("SELECT * FROM conversations WHERE id = ?", (nuevo,))

    def _historial(self, conv_id: int) -> list[dict[str, str]]:
        filas = self.db.query(
            "SELECT rol, contenido FROM messages WHERE conversation_id = ? "
            "AND rol IN ('user','assistant') ORDER BY id",
            (conv_id,),
        )
        return [{"role": f["rol"], "content": f["contenido"]} for f in filas]

    @staticmethod
    def _recortar(historial: list[dict[str, str]], presupuesto: int) -> list[dict[str, str]]:
        """Conserva los mensajes más recientes que quepan; el primero conservado es siempre del usuario."""
        elegidos: list[dict[str, str]] = []
        usado = 0
        for m in reversed(historial):
            t = tokens_aprox(m["content"]) + 4
            if usado + t > presupuesto:
                break
            elegidos.append(m)
            usado += t
        elegidos.reverse()
        while elegidos and elegidos[0]["role"] != "user":
            elegidos.pop(0)
        return elegidos

    def _guardar(self, conv: dict[str, Any], texto: str, respuesta: str, plan, modelo: str | None,
                 thinking: str, tokens_in: int | None, tokens_out: int | None,
                 gen_ms: int | None = None, thinking_ms: int | None = None) -> int:
        self.db.execute(
            "INSERT INTO messages(conversation_id, rol, contenido, tier, esfuerzo, created_at) "
            "VALUES (?, 'user', ?, ?, ?, ?)",
            (conv["id"], texto, plan.tier, plan.esfuerzo, ahora()),
        )
        mid = self.db.execute(
            "INSERT INTO messages(conversation_id, rol, contenido, tier, esfuerzo, modelo, thinking, "
            "tokens_in, tokens_out, gen_ms, thinking_ms, created_at) "
            "VALUES (?, 'assistant', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (conv["id"], respuesta, plan.tier, plan.esfuerzo, modelo or plan.alias,
             thinking or None, tokens_in, tokens_out, gen_ms, thinking_ms, ahora()),
        )
        titulo = conv["titulo"] or (texto.strip().splitlines()[0][:60] if texto.strip() else "Sin título")
        self.db.execute(
            "UPDATE conversations SET titulo = ?, updated_at = ? WHERE id = ?", (titulo, ahora(), conv["id"])
        )
        conv["titulo"] = titulo
        return mid

    # --- estimador (API-004) ---------------------------------------------------
    def estimar(self, modo: str, tier: str, esfuerzo: str, texto: str, sesion_id: int | None) -> dict[str, Any]:
        contexto: list[str] = []
        if sesion_id is not None:
            contexto = [m["content"] for m in self._historial(sesion_id)]
        est = estimator.estimar(modo, tier, esfuerzo, texto, contexto, self.umbrales())
        nube_on = cloud_client.activada(self.db)
        modelo_nube = self.db.get_setting("nube.modelo", "claude-opus-5-5")
        est["nube_activada"] = nube_on
        est["resumen_envio"] = {
            "modelo": modelo_nube,
            "mensajes": len(contexto) + 1,
            "tokens_aprox": est["tokens_entrada"],
            "backend": cloud_client.backend_nube(self.db),
            "texto": (f"Se enviarían a Anthropic ({modelo_nube}, "
                      f"{'vía tu suscripción' if cloud_client.backend_nube(self.db) == 'claude_code' else 'API de pago'}) "
                      f"{len(contexto) + 1} mensaje(s) de este hilo, "
                      f"~{est['tokens_entrada']} tokens, incluido tu mensaje actual."
                      + (" Consume de tu límite de uso de Claude, igual que si lo escribieras en Claude Code."
                         if cloud_client.backend_nube(self.db) == "claude_code" else "")),
        }
        return est

    # --- troceo (BTN-027 / BTN-029) ---------------------------------------------
    async def trocear(self, modo: str, texto: str) -> dict[str, Any]:
        pasos: list[dict[str, Any]] = []
        origen = "ia"
        try:
            alias = FAMILIA[(modo, "pequeno")]
            etiqueta = self.registro()[alias]["etiqueta"]
            for temperatura in (0.2, 0.0):  # un reintento: el JSON puede salir cortado o mal formado
                try:
                    datos = await self.ollama.chat_json(
                        etiqueta,
                        [{"role": "system", "content": PROMPT_TROCEO}, {"role": "user", "content": texto}],
                        {"temperature": temperatura, "num_ctx": 4096, "num_predict": 1500, "num_gpu": 0},
                    )
                except OllamaError:
                    continue
                pasos = estimator.sanear_pasos(datos)
                if pasos:
                    break
        except (OllamaCaido, ModeloFaltante, KeyError):
            pasos = []
        if not pasos:
            pasos, origen = estimator.troceo_heuristico(texto), "heuristica"

        # P4 (17-...md): el encargo entra en el Organizador como tarea padre con los pasos como subtareas,
        # en la última lista abierta del Modo Tareas (o la primera).
        titulo = "Troceo: " + (texto.strip().splitlines()[0][:60] if texto.strip() else "tarea")
        preferida = self.db.get_setting("tareas.lista", "")
        fila = (self.db.one("SELECT id FROM task_lists WHERE id = ?", (int(preferida),)) if preferida.isdigit()
                else None) or self.db.one("SELECT id FROM task_lists ORDER BY id LIMIT 1")
        lista_id = fila["id"] if fila else self.db.execute("INSERT INTO task_lists(nombre) VALUES ('General')")
        base = self.db.one("SELECT COALESCE(MAX(orden), 0) AS m FROM tasks WHERE list_id = ?", (lista_id,))["m"]
        padre_id = self.db.execute(
            "INSERT INTO tasks(list_id, texto, prioridad, estimacion_min, orden, origen) VALUES (?, ?, 2, ?, ?, 'troceo')",
            (lista_id, titulo, sum(p["estimacion_min"] for p in pasos), base + 1),
        )
        for i, p in enumerate(pasos, 1):
            p["id"] = self.db.execute(
                "INSERT INTO tasks(list_id, parent_id, texto, prioridad, estimacion_min, orden, origen) "
                "VALUES (?, ?, ?, 2, ?, ?, 'troceo')",
                (lista_id, padre_id, p["texto"], p["estimacion_min"], base + 1 + i),
            )
            p["orden"] = i
        return {"lista_id": lista_id, "padre_id": padre_id, "titulo": titulo, "pasos": pasos, "origen": origen}

    # --- telemetría (doc 22) --------------------------------------------------
    def _telemetria(self, texto: str, plan, modelo: str | None, tier: str, esfuerzo: str,
                    thinking_activo: bool, cargando: bool = False) -> Telemetria:
        previos = [f["tokens_out"] for f in self.db.query(
            "SELECT tokens_out FROM messages WHERE rol = 'assistant' AND modelo = ? AND esfuerzo = ? "
            "AND tokens_out IS NOT NULL ORDER BY id DESC LIMIT 15", (modelo, esfuerzo))]
        salida = estimator.salida_prevista(estimator._norm(texto))
        tel = Telemetria(objetivo_tokens(salida, esfuerzo, thinking_activo, previos),
                         plan.params.get("num_predict"), modelo or plan.alias, tier)
        if cargando:
            tel.fase = "cargando"
        return tel

    # --- generación ----------------------------------------------------------
    async def generar(self, sesion_id: int | None, modo: str, tier: str, esfuerzo: str,
                      texto: str, forzar: bool = False, engagement_id: int | None = None) -> AsyncIterator[str]:
        texto = (texto or "").strip()
        engagement = None
        if modo == "seguridad":
            # G-1 / ST-030 en el backend: sin engagement autorizado no hay chat. G-3 antes de llamar al modelo.
            try:
                engagement = self.seguridad.exigir_operable(engagement_id)
                if texto:
                    self.seguridad.comprobar_peticion(engagement, texto, "chat")
            except SeguridadError as e:
                yield error(e.codigo, e.mensaje, **e.extra)
                return
        if modo not in MODOS_DISPONIBLES:
            yield error("MODO_NO_DISPONIBLE", f"El modo '{modo}' todavía no está construido.")
            return
        es_nube = tier == "nube"
        if es_nube and not cloud_client.activada(self.db):
            yield error("NUBE_NO_ACTIVADA", "La Nube no está activada. Actívala en Ajustes.")
            return
        if not texto:
            yield error("TEXTO_VACIO", "Escribe algo antes de enviar.")
            return
        if sesion_id is not None and sesion_id in self._activas:
            yield error("SESION_OCUPADA", "Ya hay una generación en curso en esta conversación.")
            return

        # ST-010: estimando → (esperando_decision_escalado). No se crea ni guarda nada todavía.
        if not es_nube and not forzar:
            try:
                est = self.estimar(modo, tier, esfuerzo, texto, sesion_id)
            except LookupError as e:
                yield error("SESION_INVALIDA", str(e))
                return
            if est["veredicto"] != estimator.CABE_LOCAL:
                yield sse("sugerencia_escalado", {**est, "tier": tier, "texto": texto})
                return

        try:
            conv = self._conversacion(sesion_id, modo, engagement_id)
        except LookupError as e:
            yield error("SESION_INVALIDA", str(e))
            return
        if conv["id"] in self._activas:
            yield error("SESION_OCUPADA", "Ya hay una generación en curso en esta conversación.")
            return

        self._activas.add(conv["id"])
        plan = None
        modelo_real = None
        contenido = ""
        thinking = ""
        terminado = False
        tel: Telemetria | None = None
        try:
            historial = self._historial(conv["id"])
            cargados: list[str] = []
            if not es_nube:
                try:
                    cargados = await self.ollama.cargados()
                except OllamaCaido:
                    yield error("OLLAMA_CAIDO", "Ollama no responde en localhost:11434.")
                    return

            entrada = tokens_aprox(texto) + sum(tokens_aprox(m["content"]) for m in historial)
            plan = resolver(modo, tier, esfuerzo, entrada + 400, self.registro(), cargados)
            if engagement is not None:
                contexto = self.seguridad.contexto_prompt(engagement)
                plan = replace(plan, system_prompt=f"{plan.system_prompt}\n\n{contexto}")
            ctx_proyecto = self.proyectos.contexto_prompt(conv.get("project_id"))
            if ctx_proyecto:
                plan = replace(plan, system_prompt=f"{plan.system_prompt}\n\n{ctx_proyecto}")
            presupuesto = (plan.params["num_ctx"] - plan.params["num_predict"]
                           - tokens_aprox(plan.system_prompt) - tokens_aprox(texto) - 256)
            if es_nube:
                presupuesto = plan.params["num_ctx"] - tokens_aprox(plan.system_prompt) - tokens_aprox(texto)
            historial = self._recortar(historial, max(presupuesto, 0))
            mensajes = [*historial, {"role": "user", "content": texto}]

            tokens_in = tokens_out = None
            tps = None
            if es_nube:
                modelo_real = plan.proveedor_nube
                # ST-050 aceptado_nube: se audita QUÉ sale del equipo (resumen, no el contenido).
                audit.registrar(self.db, "escalado_nube", {
                    "sesion_id": conv["id"], "modelo": modelo_real, "esfuerzo": esfuerzo,
                    "mensajes": len(mensajes), "tokens_aprox": entrada, "extracto": texto[:200],
                    "backend": cloud_client.backend_nube(self.db),
                })
                yield sse("inicio", {
                    "sesion_id": conv["id"], "modelo": modelo_real, "alias": plan.alias, "tier": tier,
                    "esfuerzo": esfuerzo, "requiere_carga": False, "num_ctx": plan.params["num_ctx"],
                    "thinking_nativo": True,
                })
                tel = self._telemetria(texto, plan, modelo_real, tier, esfuerzo, True)
                yield sse("telemetria", tel.evento())
                async for ev in con_ticks(self.nube.stream(modelo_real, plan.system_prompt, mensajes, esfuerzo,
                                                               backend=cloud_client.backend_nube(self.db))):
                    if ev is None:
                        if tel.toca():
                            yield sse("telemetria", tel.evento())
                        continue
                    if ev["tipo"] == "thinking":
                        thinking += ev["texto"]
                        tel.thinking(tokens_aprox(ev["texto"]))
                        yield sse("thinking", {"texto_parcial": ev["texto"]})
                    elif ev["tipo"] == "token":
                        contenido += ev["texto"]
                        tel.token(tokens_aprox(ev["texto"]))
                        yield sse("token", {"texto": ev["texto"]})
                    elif ev["tipo"] == "fin":
                        tokens_in, tokens_out = ev["tokens_in"], ev["tokens_out"]
                        modelo_real = ev.get("modelo") or modelo_real
                        if ev["stop_reason"] == "refusal":
                            yield error("NUBE_RECHAZO", "Claude declinó la petición por sus políticas de seguridad.",
                                        categoria=ev.get("categoria"))
                            return
                    if tel.toca():
                        yield sse("telemetria", tel.evento())
            else:
                requiere_carga = await self.ollama.asegurar_unico(plan.etiqueta_ollama)
                modelo_real = plan.etiqueta_ollama
                yield sse("inicio", {
                    "sesion_id": conv["id"], "modelo": modelo_real, "alias": plan.alias,
                    "tier": tier, "esfuerzo": esfuerzo, "requiere_carga": requiere_carga,
                    "num_ctx": plan.params["num_ctx"], "thinking_nativo": plan.thinking_nativo,
                })
                opciones = {
                    "temperature": plan.params["temperatura"],
                    "num_ctx": plan.params["num_ctx"],
                    "num_predict": plan.params["num_predict"],
                    "num_gpu": 0,  # CPU-only (01-restricciones-hardware.md)
                }
                think = plan.params.get("enable_thinking") if plan.thinking_nativo else None
                eval_ns = None
                tel = self._telemetria(texto, plan, modelo_real, tier, esfuerzo, bool(think), requiere_carga)
                yield sse("telemetria", tel.evento())
                async for trozo in con_ticks(self.ollama.chat_stream(
                        plan.etiqueta_ollama, [{"role": "system", "content": plan.system_prompt}, *mensajes],
                        opciones, think)):
                    if trozo is None:              # sin datos en ~0,5 s: el contador sigue corriendo
                        if tel.toca():
                            yield sse("telemetria", tel.evento())
                        continue
                    msg = trozo.get("message") or {}
                    if msg.get("thinking"):
                        thinking += msg["thinking"]
                        tel.thinking(1)            # Ollama manda ~1 token por trozo
                        yield sse("thinking", {"texto_parcial": msg["thinking"]})
                    if msg.get("content"):
                        contenido += msg["content"]
                        tel.token(1)
                        yield sse("token", {"texto": msg["content"]})
                    if tel.toca():
                        yield sse("telemetria", tel.evento())
                    if trozo.get("done"):
                        tokens_in = trozo.get("prompt_eval_count")
                        tokens_out = trozo.get("eval_count")
                        eval_ns = trozo.get("eval_duration")
                tps = round(tokens_out / (eval_ns / 1e9), 1) if tokens_out and eval_ns else None

            gen_ms, thinking_ms = (tel.elapsed_ms(), tel.thinking_ms()) if tel else (None, None)
            if tokens_out is None and tel:
                tokens_out = tel.tokens_out
            mid = self._guardar(conv, texto, contenido, plan, modelo_real, thinking, tokens_in, tokens_out,
                                gen_ms, thinking_ms)
            terminado = True
            yield sse("fin", {
                "sesion_id": conv["id"], "mensaje_id": mid, "tokens_in": tokens_in,
                "tokens_out": tokens_out, "tokens_por_segundo": tps, "titulo": conv["titulo"],
                "modelo": modelo_real, "gen_ms": gen_ms, "thinking_ms": thinking_ms,
            })
        except ModeloFaltante as e:
            yield error("MODELO_FALTANTE", f"El modelo {e.etiqueta} no está descargado.",
                        etiqueta=e.etiqueta, alias=plan.alias if plan else None)
        except OllamaCaido:
            yield error("OLLAMA_CAIDO", "Se perdió la conexión con Ollama.")
        except OllamaError as e:
            yield error("OLLAMA_ERROR", f"Ollama devolvió un error: {e}")
        except NubeError as e:
            yield error(e.codigo, e.mensaje)
        except RouterError as e:
            yield error("ROUTER", str(e))
        finally:
            # Cancelado (botón detener / ventana cerrada) o error a medias: no perder lo generado.
            if not terminado and plan is not None and (contenido or thinking):
                self._guardar(conv, texto, contenido + MARCA_INTERRUMPIDA, plan, modelo_real, thinking, None,
                              tel.tokens_out if tel else None, tel.elapsed_ms() if tel else None,
                              tel.thinking_ms() if tel else None)
            self._activas.discard(conv["id"])
