"""MOD-030 Modo Seguridad / Bug Bounty (10-...md, ADR-0005).

La IA orienta y documenta; el usuario ejecuta y valida. Guardarraíles como código:
- G-1 / ST-030: sin engagement autorizado (alcance declarado + autorización confirmada) no hay chat ni análisis.
  Cambiar el alcance devuelve el engagement a `autorizacion_pendiente` y se audita.
- G-2: este modo no tiene herramientas activas; FORJA no ejecuta nada contra ningún objetivo.
- G-3: guardarrailes.evaluar() bloquea antes de llamar al modelo (lista «nunca» y objetivos fuera de alcance).
- G-5: auditoría de alcance, autorizaciones, entradas, bloqueos, escalados y exportaciones.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from .. import audit, cloud_client
from ..cloud_client import ClienteNube, NubeError
from ..db import DB, ahora
from ..ollama_client import ModeloFaltante, OllamaCaido, OllamaClient, OllamaError
from ..router import FAMILIA, alias_para, cargar_prompt
from . import guardarrailes
from .tareas import parsear_json_tolerante

MODO = "seguridad"
DISPONIBLE = True
OPERABLES = ("autorizado", "operando")
SEVERIDADES = ("info", "baja", "media", "alta", "critica")
ESTADOS_FINDING = ("idea", "validado_por_usuario", "en_informe", "reportado")
MAX_RECON_CHARS = {"pequeno": 14_000, "grande": 8_000, "nube": 120_000}

ESQUEMA_ANALISIS = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string"},
        "hallazgos": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"}, "clase": {"type": "string"},
                "severidad_estim": {"type": "string", "enum": list(SEVERIDADES)},
                "donde_enfocar": {"type": "string"}, "como_verificar": {"type": "string"},
            },
            "required": ["titulo", "clase", "severidad_estim", "donde_enfocar", "como_verificar"]}},
    },
    "required": ["resumen", "hallazgos"],
}

PLANTILLA_HACKERONE = """## Resumen
## Impacto
## Pasos para reproducir
1. …
## Evidencia
## Mitigación recomendada"""


class SeguridadError(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str, **extra: Any):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje, self.extra = status, codigo, mensaje, extra


def _sse(evento: str, datos: dict[str, Any]) -> str:
    return f"event: {evento}\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"


def _texto(v: Any, maximo: int) -> str:
    return str(v or "").strip()[:maximo]


def dir_export(db: DB) -> Path:
    elegido = (db.get_setting("export.dir", "") or "").strip()
    # Ojo: en Windows "Documents\FORJA" sería la misma carpeta que el proyecto "Documents\forja".
    base = Path(elegido) if elegido else Path(os.environ.get("USERPROFILE", Path.home())) / "Documents" / "FORJA exportados"
    return base


class Seguridad:
    def __init__(self, db: DB, ollama: OllamaClient, nube: ClienteNube):
        self.db, self.ollama, self.nube = db, ollama, nube

    # --- engagements (API-050, ST-030) ------------------------------------------------------
    def engagements(self, archivados: bool = False) -> list[dict[str, Any]]:
        return [self._con_resumen(e) for e in self.db.query(
            "SELECT * FROM engagements WHERE archivado = ? ORDER BY COALESCE(updated_at, created_at) DESC, id DESC",
            (int(archivados),))]

    def _con_resumen(self, e: dict[str, Any]) -> dict[str, Any]:
        cuenta = self.db.one(
            "SELECT COUNT(*) AS total, SUM(estado != 'idea') AS validados FROM findings WHERE engagement_id = ?",
            (e["id"],))
        al = guardarrailes.parsear_alcance(e["alcance"])
        return {**e, "hallazgos": cuenta["total"] or 0, "validados": cuenta["validados"] or 0,
                "alcance_items": [*al.dominios, *("*." + c for c in al.comodines), *(str(r) for r in al.redes)],
                "operable": e["estado"] in OPERABLES and e["autorizacion_confirmada"] == 1}

    def engagement(self, eid: int | None) -> dict[str, Any]:
        fila = self.db.one("SELECT * FROM engagements WHERE id = ?", (eid,)) if eid is not None else None
        if not fila:
            raise SeguridadError(404, "ENGAGEMENT_INVALIDO", "No existe ese engagement.")
        return self._con_resumen(fila)

    def _validar_alcance(self, alcance: str) -> str:
        alcance = _texto(alcance, 5000)
        if guardarrailes.parsear_alcance(alcance).vacio:
            raise SeguridadError(400, "ALCANCE_VACIO",
                                 "Declara al menos un activo en alcance (dominio, *.dominio, IP o rango CIDR).")
        return alcance

    def crear(self, nombre: str, alcance: str, notas: str = "") -> dict[str, Any]:
        nombre = _texto(nombre, 120)
        if not nombre:
            raise SeguridadError(400, "NOMBRE_VACIO", "Pon un nombre al engagement (p. ej. «Acme – HackerOne»).")
        alcance = self._validar_alcance(alcance)
        eid = self.db.execute(
            "INSERT INTO engagements(nombre, alcance, notas, estado, updated_at) VALUES (?, ?, ?, 'declarando_alcance', ?)",
            (nombre, alcance, _texto(notas, 5000) or None, ahora()))
        audit.registrar(self.db, "cambio_alcance", {"engagement_id": eid, "accion": "declarado", "nombre": nombre,
                                                    "alcance": alcance})
        return self.engagement(eid)

    def editar(self, eid: int, cambios: dict[str, Any]) -> dict[str, Any]:
        e = self.engagement(eid)
        sets: dict[str, Any] = {}
        if "nombre" in cambios:
            nombre = _texto(cambios["nombre"], 120)
            if not nombre:
                raise SeguridadError(400, "NOMBRE_VACIO", "El engagement necesita un nombre.")
            sets["nombre"] = nombre
        if "notas" in cambios:
            sets["notas"] = _texto(cambios["notas"], 5000) or None
        if "alcance" in cambios:
            nuevo = self._validar_alcance(cambios["alcance"])
            if nuevo != e["alcance"]:
                # ST-030: operando —[editar alcance]→ autorizacion_pendiente (hay que re-confirmar). Auditado.
                sets.update(alcance=nuevo, autorizacion_confirmada=0, estado="autorizacion_pendiente",
                            autorizado_at=None)
                audit.registrar(self.db, "cambio_alcance", {"engagement_id": eid, "accion": "editado",
                                                            "antes": e["alcance"], "despues": nuevo})
        if "archivado" in cambios:
            sets["archivado"] = 1 if cambios["archivado"] in (1, True, "1") else 0
        if cambios.get("autorizacion_confirmada") in (1, True, "1"):
            alcance_final = sets.get("alcance", e["alcance"])
            if guardarrailes.parsear_alcance(alcance_final).vacio:
                raise SeguridadError(400, "ALCANCE_VACIO", "No se puede autorizar un alcance vacío.")
            if cambios.get("declaracion") is not True:
                raise SeguridadError(400, "DECLARACION_REQUERIDA",
                                     "Marca la declaración de que tienes autorización para probar estos activos.")
            sets.update(autorizacion_confirmada=1, estado="autorizado", autorizado_at=ahora())
            audit.registrar(self.db, "cambio_alcance", {"engagement_id": eid, "accion": "autorizacion_confirmada",
                                                        "alcance": alcance_final})
        elif cambios.get("autorizacion_confirmada") in (0, False, "0") and e["autorizacion_confirmada"]:
            sets.update(autorizacion_confirmada=0, estado="revocado", autorizado_at=None)
            audit.registrar(self.db, "cambio_alcance", {"engagement_id": eid, "accion": "revocado"})
        if sets:
            sets["updated_at"] = ahora()
            cols = ", ".join(f"{k} = ?" for k in sets)
            self.db.execute(f"UPDATE engagements SET {cols} WHERE id = ?", (*sets.values(), eid))
        return self.engagement(eid)

    def entrar(self, eid: int) -> dict[str, Any]:
        """BTN-039: autorizado → operando. Registrado en auditoría."""
        e = self.engagement(eid)
        if e["estado"] not in OPERABLES or not e["autorizacion_confirmada"]:
            raise SeguridadError(403, "MODO_BLOQUEADO",
                                 "Este engagement no tiene la autorización confirmada. Revisa el alcance y confírmala.")
        self.db.execute("UPDATE engagements SET estado = 'operando', updated_at = ? WHERE id = ?", (ahora(), eid))
        self.db.set_setting("seguridad.engagement", str(eid))
        audit.registrar(self.db, "engagement", {"engagement_id": eid, "accion": "entrar", "nombre": e["nombre"]})
        return self.engagement(eid)

    def borrar(self, eid: int) -> None:
        e = self.engagement(eid)
        self.db.execute("DELETE FROM engagements WHERE id = ?", (eid,))
        audit.registrar(self.db, "engagement", {"engagement_id": eid, "accion": "borrado", "nombre": e["nombre"]})

    def exigir_operable(self, eid: int | None) -> dict[str, Any]:
        """Invariante ST-030: sin `autorizado` no hay análisis ni chat de seguridad (a nivel de backend)."""
        if eid is None:
            raise SeguridadError(403, "MODO_BLOQUEADO",
                                 "El Modo Seguridad necesita un engagement con alcance y autorización confirmados.")
        e = self.engagement(eid)
        if not e["operable"]:
            raise SeguridadError(403, "MODO_BLOQUEADO",
                                 "Este engagement no tiene la autorización confirmada (¿cambió el alcance?).")
        return e

    def contexto_prompt(self, e: dict[str, Any]) -> str:
        items = "\n".join(f"- {x}" for x in e["alcance_items"]) or e["alcance"]
        return (f"Engagement activo: {e['nombre']}\nAlcance autorizado (solo esto):\n{items}"
                + (f"\nNotas del programa: {e['notas']}" if e.get("notas") else ""))

    def comprobar_peticion(self, e: dict[str, Any], texto: str, origen: str) -> None:
        bloqueo = guardarrailes.evaluar(texto, e["alcance"])
        if bloqueo:
            audit.registrar(self.db, "guardarrail", {
                "engagement_id": e["id"], "origen": origen, "categoria": bloqueo.categoria,
                "extracto": texto[:200], "hosts": bloqueo.hosts})
            raise SeguridadError(400, "FUERA_DE_LIMITES", bloqueo.motivo, categoria=bloqueo.categoria,
                                 reconduccion=bloqueo.reconduccion)

    # --- modelo ----------------------------------------------------------------------------------
    def _etiqueta(self, tier: str, esfuerzo: str | None = None) -> str:
        """Modelo general del tier; con esfuerzo "extra", el que razona (pequeno-razonador, doc 04 rev. 10)."""
        alias = FAMILIA[(MODO, tier)]
        if esfuerzo == "extra":
            registro = {f["alias"]: f for f in self.db.query("SELECT alias FROM models")}
            alias = alias_para(MODO, tier, esfuerzo, registro)
        fila = self.db.one("SELECT etiqueta FROM models WHERE alias = ?", (alias,))
        if not fila or not fila["etiqueta"]:
            raise SeguridadError(400, "MODELO_FALTA", "No hay modelo configurado para ese tier.")
        return fila["etiqueta"]

    def _system(self, e: dict[str, Any], tier: str, esfuerzo: str, etiqueta: str | None) -> str:
        base = cargar_prompt(MODO).format(
            lugar="en la nube (el usuario lo ha pedido)" if tier == "nube" else "en local, solo CPU y 8 GB de RAM",
            modelo=etiqueta or "Claude", tier=tier, esfuerzo=esfuerzo)
        return base + "\n\n" + self.contexto_prompt(e)

    def _nube_activa(self, e: dict[str, Any], uso: str, esfuerzo: str, caracteres: int) -> tuple[str, str]:
        if not cloud_client.activada(self.db):
            raise SeguridadError(400, "NUBE_NO_ACTIVADA", "La Nube no está activada. Actívala en Ajustes.")
        modelo = self.db.get_setting("nube.modelo", "claude-opus-5-5")
        backend = cloud_client.backend_nube(self.db)
        audit.registrar(self.db, "escalado_nube", {"modo": MODO, "uso": uso, "engagement_id": e["id"],
                                                   "modelo": modelo, "backend": backend, "esfuerzo": esfuerzo,
                                                   "caracteres": caracteres})
        return modelo, backend

    # --- análisis de recon (API-051, BTN-042) --------------------------------------------------
    async def analizar(self, eid: int, datos: str, tier: str, esfuerzo: str) -> dict[str, Any]:
        e = self.exigir_operable(eid)
        datos = (datos or "").strip()
        if not datos:
            raise SeguridadError(400, "TEXTO_VACIO", "Pega o importa los datos de reconocimiento que quieres analizar.")
        maximo = MAX_RECON_CHARS[tier]
        recortado = len(datos) > maximo
        datos_envio = datos[:maximo]
        pedido = ("Analiza estos datos de reconocimiento que el investigador obtuvo con sus propias herramientas. "
                  "Devuelve posibles hallazgos (clases de problema plausibles) SOLO sobre activos del alcance, "
                  "priorizados, con dónde enfocar y cómo verificarlo de forma segura y de bajo impacto. "
                  "No propongas acciones fuera de alcance, ni DoS, ni exploits destructivos. Si no hay nada "
                  "relevante, devuelve una lista vacía y explícalo en el resumen. No inventes CVE ni versiones que "
                  "no estén en los datos. Responde en español.\n\n"
                  f"<datos_recon>\n{datos_envio}\n</datos_recon>")
        etiqueta = None if tier == "nube" else self._etiqueta(tier, esfuerzo)
        system = self._system(e, tier, esfuerzo, etiqueta)
        try:
            if tier == "nube":
                modelo, backend = self._nube_activa(e, "analisis", esfuerzo, len(datos_envio))
                texto = ""
                async for ev in self.nube.stream(modelo, system, [{"role": "user", "content": pedido + (
                        "\n\nResponde SOLO con JSON: " + json.dumps(ESQUEMA_ANALISIS["properties"], ensure_ascii=False))}],
                        esfuerzo, backend=backend):
                    if ev["tipo"] == "token":
                        texto += ev["texto"]
            else:
                modelo = etiqueta
                await self.ollama.asegurar_unico(modelo)
                texto = await self.ollama.chat_completo(
                    modelo, [{"role": "system", "content": system}, {"role": "user", "content": pedido}],
                    {"temperature": 0.2, "num_ctx": 8192, "num_gpu": 0,
                     "num_predict": 4000 if esfuerzo == "extra" else 2000},
                    formato=ESQUEMA_ANALISIS, think=(esfuerzo == "extra"))
        except ModeloFaltante as ex:
            raise SeguridadError(400, "MODELO_FALTA", f"Falta el modelo {ex}. Descárgalo en Estado del sistema.")
        except OllamaCaido:
            raise SeguridadError(503, "OLLAMA_CAIDO", "Ollama no responde en localhost:11434.")
        except OllamaError as ex:
            raise SeguridadError(502, "OLLAMA_ERROR", str(ex))
        except NubeError as ex:
            raise SeguridadError(400, ex.codigo, ex.mensaje)

        datos_ia = parsear_json_tolerante(texto)
        if not isinstance(datos_ia, dict):
            raise SeguridadError(502, "ANALISIS_INVALIDO", "El modelo no devolvió un análisis utilizable. Reinténtalo "
                                 "o sube el esfuerzo/tier.")
        # Los CVE que el modelo cite sin que aparezcan en los datos aportados son inventados: fuera.
        cves_reales = {c.upper() for c in re.findall(r"CVE-\d{4}-\d{4,7}", datos, flags=re.I)}

        def sin_cve_inventado(v: Any) -> Any:
            if not isinstance(v, str):
                return v
            return re.sub(r"\s*\(?\b(CVE-\d{4}-\d{4,7})\b\)?",
                          lambda m: m.group(0) if m.group(1).upper() in cves_reales else "", v, flags=re.I).strip()

        creados = []
        for h in (datos_ia.get("hallazgos") or [])[:30]:
            if isinstance(h, dict):
                h = {k: sin_cve_inventado(v) for k, v in h.items()}
            if not isinstance(h, dict) or not _texto(h.get("titulo"), 200):
                continue
            sev = str(h.get("severidad_estim") or "").lower().replace("í", "i")
            fid = self.db.execute(
                "INSERT INTO findings(engagement_id, titulo, clase, severidad_estim, donde_enfocar, como_verificar, "
                "origen, estado) VALUES (?, ?, ?, ?, ?, ?, 'ia', 'idea')",
                (eid, _texto(h.get("titulo"), 200), _texto(h.get("clase"), 80) or None,
                 sev if sev in SEVERIDADES else None, _texto(h.get("donde_enfocar"), 4000) or None,
                 _texto(h.get("como_verificar"), 4000) or None))
            creados.append(self.finding(fid))
        self.db.execute("UPDATE engagements SET updated_at = ? WHERE id = ?", (ahora(), eid))
        return {"resumen": _texto(datos_ia.get("resumen"), 3000), "hallazgos": creados, "modelo": modelo,
                "recortado": recortado, "caracteres_analizados": len(datos_envio)}

    # --- hallazgos (API-052, BTN-043/044) ------------------------------------------------------
    def findings(self, eid: int) -> list[dict[str, Any]]:
        self.engagement(eid)
        orden = "CASE severidad_estim WHEN 'critica' THEN 0 WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baja' THEN 3 " \
                "WHEN 'info' THEN 4 ELSE 5 END"
        return self.db.query(f"SELECT * FROM findings WHERE engagement_id = ? ORDER BY {orden}, id", (eid,))

    def finding(self, fid: int) -> dict[str, Any]:
        f = self.db.one("SELECT * FROM findings WHERE id = ?", (fid,))
        if not f:
            raise SeguridadError(404, "HALLAZGO_INVALIDO", "No existe ese hallazgo.")
        return f

    def crear_finding(self, eid: int, datos: dict[str, Any]) -> dict[str, Any]:
        e = self.exigir_operable(eid)
        titulo = _texto(datos.get("titulo"), 200)
        if not titulo:
            raise SeguridadError(400, "TITULO_VACIO", "El hallazgo necesita un título.")
        self.comprobar_peticion(e, " ".join(str(datos.get(k) or "") for k in ("titulo", "donde_enfocar")), "hallazgo")
        sev = datos.get("severidad_estim")
        fid = self.db.execute(
            "INSERT INTO findings(engagement_id, titulo, clase, severidad_estim, donde_enfocar, como_verificar, "
            "evidencia_usuario, origen) VALUES (?, ?, ?, ?, ?, ?, ?, 'manual')",
            (eid, titulo, _texto(datos.get("clase"), 80) or None, sev if sev in SEVERIDADES else None,
             _texto(datos.get("donde_enfocar"), 4000) or None, _texto(datos.get("como_verificar"), 4000) or None,
             _texto(datos.get("evidencia_usuario"), 20_000) or None))
        return self.finding(fid)

    def editar_finding(self, fid: int, cambios: dict[str, Any]) -> dict[str, Any]:
        f = self.finding(fid)
        self.exigir_operable(f["engagement_id"])
        sets: dict[str, Any] = {}
        for k, maximo in (("titulo", 200), ("clase", 80), ("donde_enfocar", 4000), ("como_verificar", 4000),
                          ("evidencia_usuario", 20_000), ("informe_md", 100_000)):
            if k in cambios:
                sets[k] = _texto(cambios[k], maximo) or None
        if sets.get("titulo", "x") is None:
            raise SeguridadError(400, "TITULO_VACIO", "El hallazgo necesita un título.")
        if "severidad_estim" in cambios:
            v = cambios["severidad_estim"]
            if v not in (*SEVERIDADES, None, ""):
                raise SeguridadError(400, "SEVERIDAD_INVALIDA", f"Severidad: {', '.join(SEVERIDADES)}.")
            sets["severidad_estim"] = v or None
        if "estado" in cambios:
            est = cambios["estado"]
            if est not in ESTADOS_FINDING:
                raise SeguridadError(400, "ESTADO_INVALIDO", f"Estado: {', '.join(ESTADOS_FINDING)}.")
            evidencia = sets.get("evidencia_usuario", f["evidencia_usuario"])
            if est != "idea" and not evidencia:
                # BTN-043: validar = lo comprobaste tú y adjuntas evidencia.
                raise SeguridadError(400, "EVIDENCIA_REQUERIDA",
                                     "Para marcarlo como validado, adjunta la evidencia de tu comprobación.")
            sets["estado"] = est
        if sets:
            sets["updated_at"] = ahora()
            cols = ", ".join(f"{k} = ?" for k in sets)
            self.db.execute(f"UPDATE findings SET {cols} WHERE id = ?", (*sets.values(), fid))
        return self.finding(fid)

    def borrar_finding(self, fid: int) -> None:
        f = self.finding(fid)
        self.exigir_operable(f["engagement_id"])
        self.db.execute("DELETE FROM findings WHERE id = ?", (fid,))

    # --- informe (API-053, BTN-040) — streaming ---------------------------------------------------
    async def informe(self, fid: int, enfoques: list[str], tier: str, esfuerzo: str) -> AsyncIterator[str]:
        try:
            f = self.finding(fid)
            e = self.exigir_operable(f["engagement_id"])
            if f["estado"] == "idea":
                raise SeguridadError(400, "NO_VALIDADO", "Solo se redactan informes de hallazgos que has validado tú "
                                     "(con evidencia).")
            enfoques = [x.strip()[:20_000] for x in enfoques if x and x.strip()][:4]
            etiqueta = None if tier == "nube" else self._etiqueta(tier)
            system = self._system(e, tier, esfuerzo, etiqueta)
        except SeguridadError as ex:
            yield _sse("error", {"codigo": ex.codigo, "mensaje": ex.mensaje})
            return
        partes = [f"Hallazgo: {f['titulo']}", f"Clase: {f['clase'] or '—'}",
                  f"Severidad estimada: {f['severidad_estim'] or '—'}",
                  f"Dónde se enfocó: {f['donde_enfocar'] or '—'}",
                  f"Evidencia validada por el investigador:\n{f['evidencia_usuario']}"]
        for i, enf in enumerate(enfoques, 1):
            partes.append(f"Enfoque/evidencia adicional {i}:\n{enf}")
        pedido = ("Redacta en español un informe de bug bounty presentable, uniendo TODAS las evidencias y enfoques "
                  "en un solo relato coherente (si hay varios caminos para llegar al mismo fallo, preséntalos como "
                  "variantes de reproducción). Usa exactamente esta estructura de Markdown (estilo HackerOne):\n"
                  f"{PLANTILLA_HACKERONE}\n"
                  "Empieza con una línea '# <título claro>'. No inventes datos que no estén en la evidencia: si falta "
                  "algo, deja un marcador [COMPLETAR: …]. Nada de payloads destructivos. Responde solo con el informe."
                  "\n\n" + "\n\n".join(partes))
        texto = ""
        yield _sse("inicio", {"modelo": etiqueta or "nube", "finding_id": fid})
        try:
            if tier == "nube":
                modelo, backend = self._nube_activa(e, "informe", esfuerzo, len(pedido))
                async for ev in self.nube.stream(modelo, system, [{"role": "user", "content": pedido}], esfuerzo,
                                                 backend=backend):
                    if ev["tipo"] == "token":
                        texto += ev["texto"]
                        yield _sse("token", {"texto": ev["texto"]})
            else:
                await self.ollama.asegurar_unico(etiqueta)
                opciones = {"temperature": 0.3, "num_ctx": 8192, "num_gpu": 0, "num_predict": 2500}
                # qwen3 a veces razona en texto plano antes del informe aunque think=False:
                # se retiene (como "thinking") hasta la primera línea que empieza por "# ".
                previo, empezado = "", False
                async for trozo in self.ollama.chat_stream(
                        etiqueta, [{"role": "system", "content": system}, {"role": "user", "content": pedido}],
                        opciones, False):
                    t = (trozo.get("message") or {}).get("content") or ""
                    if not t:
                        continue
                    if not empezado:
                        previo += t
                        m = re.search(r"(?m)^#\s", previo)
                        if not m:
                            yield _sse("thinking", {"texto_parcial": t})
                            continue
                        empezado, t = True, previo[m.start():]
                    texto += t
                    yield _sse("token", {"texto": t})
                if not empezado:
                    texto = previo
        except (OllamaCaido, ModeloFaltante, OllamaError, NubeError, SeguridadError) as ex:
            yield _sse("error", {"codigo": getattr(ex, "codigo", "OLLAMA_ERROR"), "mensaje": getattr(ex, "mensaje", str(ex))})
            return
        texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()
        if not texto:
            yield _sse("error", {"codigo": "INFORME_VACIO", "mensaje": "El modelo no devolvió texto."})
            return
        self.db.execute("UPDATE findings SET informe_md = ?, estado = CASE WHEN estado = 'reportado' THEN estado "
                        "ELSE 'en_informe' END, updated_at = ? WHERE id = ?", (texto, ahora(), fid))
        yield _sse("fin", {"finding": self.finding(fid)})

    # --- export (API-062, BTN-045) --------------------------------------------------------------
    def exportar_informe(self, fid: int) -> dict[str, Any]:
        f = self.finding(fid)
        e = self.engagement(f["engagement_id"])
        if not f["informe_md"]:
            raise SeguridadError(400, "SIN_INFORME", "Ese hallazgo todavía no tiene informe.")
        carpeta = dir_export(self.db) / "informes"
        carpeta.mkdir(parents=True, exist_ok=True)
        base = re.sub(r"[^\w\-]+", "_", f"{e['nombre']}_{f['titulo']}", flags=re.U).strip("_")[:90]
        ruta = carpeta / f"{base}_{datetime.now():%Y%m%d-%H%M}.md"
        ruta.write_text(f["informe_md"] + "\n", encoding="utf-8")
        audit.registrar(self.db, "export", {"tipo": "informe", "finding_id": fid, "engagement_id": e["id"],
                                            "ruta": str(ruta)})
        return {"ruta": str(ruta), "carpeta": str(carpeta), "nombre": ruta.name, "markdown": f["informe_md"]}
