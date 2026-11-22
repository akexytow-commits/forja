"""MOD-040 Modo Organizador de Tareas (11-modo-tareas-organizador.md, 17-patrones-planificador.md).

- P1 (Todoist): captura en lenguaje natural → fecha/hora/prioridad/duración (lenguaje.py; capa 2 = modelo).
- P2 (Motion/Sunsama): Reorganizar recoloca solo lo libre; lo fijado (fijada=1, o movido a mano) no se toca.
- P3 (Sunsama): capacidad diaria (plan.capacidad_dia_min); el reparto no supera la capacidad.
- P4 (Logseq): subtareas (parent_id); una tarea con hijas es un contenedor y lo que se planifica son las hojas.
Esfuerzo: bajo = reglas sin IA (por prioridad); medio = IA reparte; extra = IA razona dependencias (thinking).
"""
from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import date, timedelta
from typing import Any

from .. import audit, cloud_client
from ..cloud_client import ClienteNube, NubeError
from ..db import DB, ahora
from ..ollama_client import ModeloFaltante, OllamaCaido, OllamaClient, OllamaError
from ..router import FAMILIA, cargar_prompt
from . import lenguaje

MODO = "tareas"
DISPONIBLE = True
HORIZONTE_DIAS = 7          # la IA reparte en los próximos 7 días; lo que no cabe, sigue después
MIN_DEFECTO = 30
MAX_PROFUNDIDAD = 3

# Salidas estructuradas de Ollama: obliga al modelo a devolver exactamente este contrato
# (un modelo de 4B, con solo format=json, a veces devuelve el JSON de entrada en lugar del plan).
ESQUEMA_PLAN = {
    "type": "object",
    "properties": {
        "plan": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "dia_asignado": {"type": "string"},
                           "orden": {"type": "integer"}, "prioridad": {"type": "integer"},
                           "estimacion_min": {"type": "integer"}},
            "required": ["id", "dia_asignado", "orden", "prioridad", "estimacion_min"]}},
        "resumen": {"type": "string"},
    },
    "required": ["plan", "resumen"],
}

CAMPOS = ("id, list_id, parent_id, texto, prioridad, estimacion_min, dia_asignado, hora, orden, estado, "
          "origen, fijada, created_at, updated_at")


class TareasError(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje = status, codigo, mensaje


def hoy() -> date:
    return date.today()


# --- JSON tolerante (TST-043) ---------------------------------------------------------------
def parsear_json_tolerante(texto: str) -> Any:
    """Nunca rompe por JSON mal formado: quita ``` , recorta al objeto, comas finales, comillas raras."""
    if not isinstance(texto, str):
        return texto
    t = texto.strip()
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S)
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t.strip(), flags=re.I | re.M)
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        t = t[i:j + 1]
    intentos = [t]
    limpio = re.sub(r",\s*([}\]])", r"\1", t)
    limpio = limpio.replace("“", '"').replace("”", '"').replace("’", "'")
    intentos.append(limpio)
    intentos.append(re.sub(r"(?<![\w\\])'([^'\n]*?)'(?=\s*[:,}\]])", r'"\1"', limpio))  # 'x' → "x"
    intentos.append(re.sub(r"([{,]\s*)([A-Za-z_]\w*)\s*:", r'\1"\2":', intentos[-1]))  # claves sin comillas
    for cand in intentos:
        try:
            return json.loads(cand)
        except ValueError:
            continue
    return None


def _entero(v: Any, defecto: int | None, lo: int, hi: int) -> int | None:
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return defecto
    return max(lo, min(hi, n))


def _dia(v: Any, hoy_: date, dias: list[str]) -> str | None:
    """Acepta ISO, índice de día (0=hoy), 'hoy'/'mañana'/'pasado'. Devuelve ISO o None."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        k = int(v)
        return (hoy_ + timedelta(days=k)).isoformat() if 0 <= k <= 60 else None
    s = lenguaje.sin_tildes(str(v)).strip().lower()
    if not s or s in ("null", "none", "sin asignar", "-"):
        return None
    if s.isdigit():
        return _dia(int(s), hoy_, dias)
    alias = {"hoy": 0, "manana": 1, "pasado": 2, "pasado manana": 2}
    if s in alias:
        return (hoy_ + timedelta(days=alias[s])).isoformat()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try:
            d = date.fromisoformat(m.group(1))
        except ValueError:
            return None
        return max(d, hoy_).isoformat()
    for k, iso in enumerate(dias):  # "lunes 23", "Día 2"...
        if iso in s:
            return iso
    return None


class Organizador:
    def __init__(self, db: DB, ollama: OllamaClient, nube: ClienteNube):
        self.db, self.ollama, self.nube = db, ollama, nube

    # --- listas (API-040) ------------------------------------------------------------------
    def listas(self) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT l.id, l.nombre, l.resumen, l.organizada_at, "
            "  (SELECT COUNT(*) FROM tasks t WHERE t.list_id = l.id) AS total, "
            "  (SELECT COUNT(*) FROM tasks t WHERE t.list_id = l.id AND t.estado != 'hecha') AS pendientes "
            "FROM task_lists l ORDER BY l.id")

    def lista(self, lista_id: int) -> dict[str, Any]:
        fila = self.db.one("SELECT id, nombre, resumen, organizada_at FROM task_lists WHERE id = ?", (lista_id,))
        if not fila:
            raise TareasError(404, "LISTA_INVALIDA", f"No existe la lista {lista_id}.")
        return fila

    def crear_lista(self, nombre: str) -> dict[str, Any]:
        nombre = (nombre or "").strip()[:80]
        if not nombre:
            raise TareasError(400, "NOMBRE_VACIO", "La lista necesita un nombre.")
        return self.lista(self.db.execute("INSERT INTO task_lists(nombre) VALUES (?)", (nombre,)))

    def renombrar_lista(self, lista_id: int, nombre: str) -> dict[str, Any]:
        self.lista(lista_id)
        nombre = (nombre or "").strip()[:80]
        if not nombre:
            raise TareasError(400, "NOMBRE_VACIO", "La lista necesita un nombre.")
        self.db.execute("UPDATE task_lists SET nombre = ? WHERE id = ?", (nombre, lista_id))
        return self.lista(lista_id)

    def borrar_lista(self, lista_id: int) -> None:
        self.lista(lista_id)
        if len(self.listas()) <= 1:
            raise TareasError(400, "ULTIMA_LISTA", "No puedes borrar la única lista.")
        self.db.execute("DELETE FROM task_lists WHERE id = ?", (lista_id,))

    # --- tareas (API-041/043) ---------------------------------------------------------------
    def tareas(self, lista_id: int) -> list[dict[str, Any]]:
        self.lista(lista_id)
        return self.db.query(f"SELECT {CAMPOS} FROM tasks WHERE list_id = ? "
                             "ORDER BY COALESCE(dia_asignado, '9999'), orden, id", (lista_id,))

    def tarea(self, tid: int) -> dict[str, Any]:
        fila = self.db.one(f"SELECT {CAMPOS} FROM tasks WHERE id = ?", (tid,))
        if not fila:
            raise TareasError(404, "TAREA_INVALIDA", f"No existe la tarea {tid}.")
        return fila

    def capacidad(self) -> int:
        return _entero(self.db.get_setting("plan.capacidad_dia_min", "480"), 480, 30, 1440) or 480

    def vista(self, lista_id: int) -> dict[str, Any]:
        return {"lista": self.lista(lista_id), "tareas": self.tareas(lista_id), "hoy": hoy().isoformat(),
                "capacidad_dia_min": self.capacidad()}

    async def anadir(self, lista_id: int, texto: str, parent_id: int | None = None,
                     origen: str = "usuario") -> list[dict[str, Any]]:
        """BTN-050: una tarea por línea; P1 extrae fecha/hora/prioridad/duración; la sangría anida (P4)."""
        self.lista(lista_id)
        if parent_id is not None:
            padre = self.tarea(parent_id)
            if padre["list_id"] != lista_id:
                raise TareasError(400, "PADRE_INVALIDO", "La tarea padre es de otra lista.")
        crudas = [l for l in (texto or "").splitlines() if l.strip()]
        if len(crudas) == 1 and ";" in crudas[0]:
            crudas = [p for p in crudas[0].split(";") if p.strip()]
        if not crudas:
            raise TareasError(400, "TEXTO_VACIO", "Escribe al menos una tarea.")
        if len(crudas) > 200:
            raise TareasError(400, "DEMASIADAS", "Máximo 200 tareas de una vez.")
        h = hoy()
        datos = [lenguaje.interpretar(l, h) for l in crudas]
        await self._resolver_ambiguas(datos, h)

        creadas: list[dict[str, Any]] = []
        pila: list[tuple[int, int]] = []  # (nivel, id) para anidar por sangría
        base_orden = (self.db.one("SELECT COALESCE(MAX(orden), 0) AS m FROM tasks WHERE list_id = ?",
                                  (lista_id,)) or {"m": 0})["m"]
        for k, (cruda, d) in enumerate(zip(crudas, datos), 1):
            nivel = lenguaje.sangria(cruda)
            while pila and pila[-1][0] >= nivel:
                pila.pop()
            padre = pila[-1][1] if pila else parent_id
            tid = self.db.execute(
                "INSERT INTO tasks(list_id, parent_id, texto, prioridad, estimacion_min, dia_asignado, hora, "
                "orden, origen, fijada) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (lista_id, padre, d["texto"][:500], d["prioridad"], d["estimacion_min"], d["dia_asignado"],
                 d["hora"], base_orden + k, origen, 1 if d["dia_asignado"] else 0),
            )
            pila.append((nivel, tid))
            t = self.tarea(tid)
            t["detectado"] = d["detectado"]
            creadas.append(t)
        return creadas

    async def _resolver_ambiguas(self, datos: list[dict[str, Any]], h: date) -> None:
        """P1 capa 2: lo que las reglas no entienden se lo pregunta al modelo Pequeño (si está)."""
        ambiguas = [d for d in datos if d.get("ambigua") and not d["dia_asignado"]]
        if not ambiguas:
            return
        try:
            etiqueta = self._etiqueta("pequeno")
        except TareasError:
            return
        for d in ambiguas[:10]:
            prompt = (f"Hoy es {h.isoformat()} ({_NOMBRE_DIA[h.weekday()]}). Extrae de esta tarea la fecha "
                      "y limpia el texto. Responde SOLO JSON: "
                      '{"texto_limpio": "...", "dia_asignado": "AAAA-MM-DD" o null, "prioridad": 1-5}.\n'
                      f"Tarea: {d['texto']}")
            try:
                bruto = await self.ollama.chat_completo(
                    etiqueta, [{"role": "user", "content": prompt}],
                    {"temperature": 0.1, "num_ctx": 2048, "num_predict": 200, "num_gpu": 0}, think=False)
            except (OllamaCaido, ModeloFaltante, OllamaError):
                return
            r = parsear_json_tolerante(bruto)
            if not isinstance(r, dict):
                continue
            dia = _dia(r.get("dia_asignado"), h, [])
            if dia:
                d["dia_asignado"] = dia
                d["detectado"].append("fecha_ia")
                limpio = str(r.get("texto_limpio") or "").strip()
                if limpio:
                    d["texto"] = limpio
            if r.get("prioridad") is not None and d["prioridad"] == lenguaje.PRIORIDAD_DEFECTO:
                d["prioridad"] = _entero(r.get("prioridad"), d["prioridad"], 1, 5)

    def editar(self, tid: int, cambios: dict[str, Any]) -> dict[str, Any]:
        """BTN-051/052/053/054/058/059 (PATCH /tareas/{id})."""
        t = self.tarea(tid)
        sets: dict[str, Any] = {}
        if "texto" in cambios:
            texto = str(cambios["texto"] or "").strip()
            if not texto:
                raise TareasError(400, "TEXTO_VACIO", "La tarea no puede quedar vacía.")
            sets["texto"] = texto[:500]
        if "prioridad" in cambios:
            sets["prioridad"] = _entero(cambios["prioridad"], t["prioridad"], 1, 5)
        if "estimacion_min" in cambios:
            v = cambios["estimacion_min"]
            sets["estimacion_min"] = None if v in (None, "") else _entero(v, t["estimacion_min"], 1, 1440)
        if "hora" in cambios:
            v = (cambios["hora"] or "").strip()
            if v and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
                raise TareasError(400, "HORA_INVALIDA", "La hora va como HH:MM.")
            sets["hora"] = v or None
        if "estado" in cambios:
            if cambios["estado"] not in ("pendiente", "en_curso", "hecha"):
                raise TareasError(400, "ESTADO_INVALIDO", "Estado: pendiente, en_curso o hecha.")
            sets["estado"] = cambios["estado"]
        if "fijada" in cambios:
            sets["fijada"] = 1 if cambios["fijada"] in (1, True, "1", "true") else 0
        if "parent_id" in cambios:
            sets["parent_id"] = self._validar_padre(t, cambios["parent_id"])
        movida = False
        if "dia_asignado" in cambios:
            v = cambios["dia_asignado"]
            if v in (None, ""):
                sets["dia_asignado"] = None
            else:
                try:
                    sets["dia_asignado"] = date.fromisoformat(str(v)).isoformat()
                except ValueError:
                    raise TareasError(400, "DIA_INVALIDO", "El día va como AAAA-MM-DD.")
            movida = True
            # P2: lo que mueves a mano queda fijado (salvo que digas lo contrario).
            if "fijada" not in cambios:
                sets["fijada"] = 1 if sets["dia_asignado"] else 0
        if sets:
            sets["updated_at"] = ahora()
            cols = ", ".join(f"{k} = ?" for k in sets)
            self.db.execute(f"UPDATE tasks SET {cols} WHERE id = ?", (*sets.values(), tid))
        if "orden" in cambios or movida:
            self._colocar(tid, _entero(cambios.get("orden"), None, 0, 10_000))
        if "estado" in sets:
            self._propagar_estado(self.tarea(tid))
        return self.tarea(tid)

    def _validar_padre(self, t: dict[str, Any], nuevo: Any) -> int | None:
        if nuevo in (None, "", 0):
            return None
        pid = _entero(nuevo, None, 1, 10**9)
        padre = self.tarea(pid)
        if padre["list_id"] != t["list_id"]:
            raise TareasError(400, "PADRE_INVALIDO", "La tarea padre es de otra lista.")
        # Sin ciclos y con profundidad limitada.
        nivel, actual = 1, padre
        while actual:
            if actual["id"] == t["id"]:
                raise TareasError(400, "PADRE_INVALIDO", "Una tarea no puede ir dentro de sí misma.")
            if actual["parent_id"] is None:
                break
            actual = self.tarea(actual["parent_id"])
            nivel += 1
        if nivel + self._altura(t["id"]) > MAX_PROFUNDIDAD:
            raise TareasError(400, "DEMASIADO_PROFUNDO", f"Máximo {MAX_PROFUNDIDAD} niveles de subtareas.")
        return pid

    def _altura(self, tid: int) -> int:
        hijas = self.db.query("SELECT id FROM tasks WHERE parent_id = ?", (tid,))
        return 1 + max((self._altura(h["id"]) for h in hijas), default=0)

    def _propagar_estado(self, t: dict[str, Any]) -> None:
        """Marcar un padre marca toda su rama; si todas las hijas están hechas, el padre también (hacia arriba)."""
        if t["estado"] == "hecha":
            pendientes = [t["id"]]
            while pendientes:
                hijas = self.db.query("SELECT id FROM tasks WHERE parent_id = ?", (pendientes.pop(),))
                for h in hijas:
                    self.db.execute("UPDATE tasks SET estado = 'hecha', updated_at = ? WHERE id = ?", (ahora(), h["id"]))
                    pendientes.append(h["id"])
        pid = t["parent_id"]
        while pid is not None:
            padre = self.tarea(pid)
            pend = self.db.one("SELECT COUNT(*) AS n FROM tasks WHERE parent_id = ? AND estado != 'hecha'",
                               (pid,))["n"]
            nuevo = "hecha" if not pend else ("en_curso" if padre["estado"] == "en_curso" else "pendiente")
            if nuevo == padre["estado"]:
                break
            self.db.execute("UPDATE tasks SET estado = ?, updated_at = ? WHERE id = ?", (nuevo, ahora(), pid))
            pid = padre["parent_id"]

    def _colocar(self, tid: int, indice: int | None) -> None:
        """Reordena el día de la tarea: la pone en la posición `indice` (0-based) y renumera."""
        t = self.tarea(tid)
        if t["dia_asignado"] is None:
            otros = self.db.query("SELECT id FROM tasks WHERE list_id = ? AND dia_asignado IS NULL AND id != ? "
                                  "ORDER BY orden, id", (t["list_id"], tid))
        else:
            otros = self.db.query("SELECT id FROM tasks WHERE list_id = ? AND dia_asignado = ? AND id != ? "
                                  "ORDER BY orden, id", (t["list_id"], t["dia_asignado"], tid))
        ids = [o["id"] for o in otros]
        ids.insert(len(ids) if indice is None else min(indice, len(ids)), tid)
        with closing(self.db.conn()) as c, c:
            c.executemany("UPDATE tasks SET orden = ? WHERE id = ?", [(k, i) for k, i in enumerate(ids, 1)])

    def borrar(self, tid: int) -> None:
        self.tarea(tid)
        self.db.execute("DELETE FROM tasks WHERE id = ?", (tid,))

    # --- organizar (API-042, BTN-055/056) ---------------------------------------------------
    def _etiqueta(self, tier: str) -> str:
        fila = self.db.one("SELECT etiqueta FROM models WHERE alias = ?", (FAMILIA[(MODO, tier)],))
        if not fila or not fila["etiqueta"]:
            raise TareasError(400, "MODELO_FALTA", "No hay modelo configurado para ese tier.")
        return fila["etiqueta"]

    async def organizar(self, lista_id: int, esfuerzo: str, tier: str) -> dict[str, Any]:
        self.lista(lista_id)
        h = hoy()
        dias = [(h + timedelta(days=k)).isoformat() for k in range(HORIZONTE_DIAS)]
        cap = self.capacidad()
        todas = self.tareas(lista_id)
        con_hijas = {t["parent_id"] for t in todas if t["parent_id"] is not None}
        hojas = [t for t in todas if t["id"] not in con_hijas and t["estado"] != "hecha"]
        fijas = [t for t in hojas if t["fijada"] and t["dia_asignado"]]
        libres = [t for t in hojas if not (t["fijada"] and t["dia_asignado"])]
        carga: dict[str, int] = {}
        for t in fijas:
            carga[t["dia_asignado"]] = carga.get(t["dia_asignado"], 0) + (t["estimacion_min"] or MIN_DEFECTO)

        nombres = {t["id"]: t["texto"] for t in todas}
        avisos: list[str] = []
        origen, modelo, resumen = "reglas", None, None
        propuesta: dict[int, dict[str, Any]] = {}
        if libres and esfuerzo != "bajo":
            try:
                propuesta, resumen, modelo = await self._pedir_plan(libres, nombres, fijas, carga, dias, cap,
                                                                    esfuerzo, tier)
                origen = "ia" if propuesta else "reglas"
                if not propuesta:
                    avisos.append("La IA no devolvió un plan utilizable; he repartido por prioridad.")
            except (OllamaCaido, OllamaError) as e:
                avisos.append(f"Sin IA ({e}); he repartido por prioridad.")
            except ModeloFaltante as e:
                raise TareasError(400, "MODELO_FALTA", f"Falta el modelo {e}. Descárgalo en Estado del sistema.")
            except NubeError as e:
                raise TareasError(400, e.codigo, e.mensaje)

        # Orden de colocación: el de la IA (día sugerido, orden); si no, prioridad y orden actual.
        def clave(t: dict[str, Any]):
            p = propuesta.get(t["id"])
            if p:
                return (0, dias.index(p["dia"]) if p["dia"] in dias else HORIZONTE_DIAS, p["orden"], t["id"])
            return (1, t["prioridad"], t["orden"], t["id"])

        for t in libres:
            p = propuesta.get(t["id"])
            if p:
                t["prioridad"] = p["prioridad"] or t["prioridad"]
                if p["estimacion_min"] and not t["estimacion_min"]:
                    t["estimacion_min"] = p["estimacion_min"]
        libres.sort(key=clave)

        # P3: reparto sin pasar de la capacidad; lo que no cabe en el horizonte sigue en días posteriores.
        asignacion: dict[int, str] = {}
        for t in libres:
            mins = t["estimacion_min"] or MIN_DEFECTO
            p = propuesta.get(t["id"])
            k = dias.index(p["dia"]) if p and p["dia"] in dias else 0
            while True:
                iso = (h + timedelta(days=k)).isoformat()
                usado = carga.get(iso, 0)
                if usado + mins <= cap or (usado == 0):
                    break
                k += 1
            carga[iso] = carga.get(iso, 0) + mins
            asignacion[t["id"]] = iso

        orden_dia: dict[str, int] = {}
        for t in fijas:
            orden_dia[t["dia_asignado"]] = max(orden_dia.get(t["dia_asignado"], 0), t["orden"])
        ts = ahora()
        with closing(self.db.conn()) as c, c:
            for t in libres:
                iso = asignacion[t["id"]]
                orden_dia[iso] = orden_dia.get(iso, 0) + 1
                c.execute("UPDATE tasks SET dia_asignado = ?, orden = ?, prioridad = ?, estimacion_min = ?, "
                          "updated_at = ? WHERE id = ?",
                          (iso, orden_dia[iso], t["prioridad"], t["estimacion_min"] or MIN_DEFECTO, ts, t["id"]))
        # Los contenedores (con hijas) toman el primer día de sus hijas.
        self._fechar_contenedores(lista_id)

        if not resumen:
            resumen = self._resumen_reglas(lista_id, h, cap)
        self.db.execute("UPDATE task_lists SET resumen = ?, organizada_at = ? WHERE id = ?",
                        (resumen[:1000], ahora(), lista_id))
        return {**self.vista(lista_id), "origen": origen, "modelo": modelo, "avisos": avisos,
                "resumen": resumen, "movidas": len(libres), "respetadas": len(fijas)}

    def _fechar_contenedores(self, lista_id: int) -> None:
        for _ in range(MAX_PROFUNDIDAD):
            self.db.execute(
                "UPDATE tasks SET dia_asignado = (SELECT MIN(h.dia_asignado) FROM tasks h WHERE h.parent_id = tasks.id) "
                "WHERE list_id = ? AND fijada = 0 AND id IN (SELECT parent_id FROM tasks WHERE parent_id IS NOT NULL)",
                (lista_id,))

    def _resumen_reglas(self, lista_id: int, h: date, cap: int) -> str:
        filas = self.db.query("SELECT dia_asignado AS d, COUNT(*) AS n, SUM(COALESCE(estimacion_min, 30)) AS m "
                              "FROM tasks WHERE list_id = ? AND estado != 'hecha' AND dia_asignado IS NOT NULL "
                              "AND id NOT IN (SELECT parent_id FROM tasks WHERE parent_id IS NOT NULL) "
                              "GROUP BY dia_asignado ORDER BY dia_asignado", (lista_id,))
        partes = []
        for f in filas[:3]:
            d = date.fromisoformat(f["d"])
            nombre = "Hoy" if d == h else "Mañana" if d == h + timedelta(days=1) else _NOMBRE_DIA[d.weekday()].capitalize()
            partes.append(f"{nombre}: {f['n']} tarea(s), {f['m']} min de {cap}")
        return "; ".join(partes) + "." if partes else "No hay tareas pendientes."

    async def _pedir_plan(self, libres, nombres, fijas, carga, dias, cap, esfuerzo, tier):
        h = date.fromisoformat(dias[0])
        entrada = {
            "hoy": dias[0],
            "capacidad_minutos_por_dia": cap,
            "dias": [{"fecha": d, "nombre": _etiqueta_dia(date.fromisoformat(d), h),
                      "minutos_ya_ocupados": carga.get(d, 0)} for d in dias],
            "tareas": [{"id": t["id"], "texto": t["texto"], "prioridad": t["prioridad"],
                        **({"minutos": t["estimacion_min"]} if t["estimacion_min"] else {}),
                        **({"dentro_de": nombres.get(t["parent_id"])} if t["parent_id"] else {})}
                       for t in libres],
        }
        system = cargar_prompt(MODO).format(lugar="en local" if tier != "nube" else "en la Nube",
                                            modelo=tier, tier=tier, esfuerzo=esfuerzo)
        extra = ("Razona antes las dependencias (qué debe ir antes de qué) y equilibra la carga entre días."
                 if esfuerzo == "extra" else "Reparte de forma sensata y equilibrada.")
        usuario = f"{extra}\nDatos:\n{json.dumps(entrada, ensure_ascii=False)}"
        mensajes = [{"role": "system", "content": system}, {"role": "user", "content": usuario}]

        if tier == "nube":
            if not cloud_client.activada(self.db):
                raise NubeError("NUBE_NO_ACTIVADA", "La Nube no está activada. Actívala en Ajustes.")
            modelo = self.db.get_setting("nube.modelo", "claude-opus-5-5")
            backend = cloud_client.backend_nube(self.db)
            audit.registrar(self.db, "escalado_nube", {"modo": MODO, "modelo": modelo, "esfuerzo": esfuerzo,
                                                       "backend": backend, "tareas": len(libres)})
            texto = ""
            async for ev in self.nube.stream(modelo, system, mensajes[1:], esfuerzo, backend=backend):
                if ev["tipo"] == "token":
                    texto += ev["texto"]
            intentos = [texto]
        else:
            modelo = self._etiqueta(tier)
            await self.ollama.asegurar_unico(modelo)
            opciones = {"temperature": 0.2, "num_ctx": 8192, "num_gpu": 0,
                        "num_predict": 6000 if esfuerzo == "extra" else 2500}
            texto = await self.ollama.chat_completo(modelo, mensajes, opciones, formato=ESQUEMA_PLAN,
                                                    think=(esfuerzo == "extra"))
            intentos = [texto]
        datos = parsear_json_tolerante(intentos[0])
        if not self._sanear_plan(datos, libres, dias)[0] and tier != "nube":
            # Robustez (11-...md): pedir al modelo que reformatee su propia salida una vez.
            try:
                texto2 = await self.ollama.chat_completo(
                    modelo, [{"role": "system", "content": "Devuelve SOLO el JSON válido equivalente, sin texto."},
                             {"role": "user", "content": texto[:6000]}],
                    {"temperature": 0.0, "num_ctx": 8192, "num_predict": 2500, "num_gpu": 0},
                    formato=ESQUEMA_PLAN, think=False)
                datos = parsear_json_tolerante(texto2)
            except OllamaError:
                datos = None
        return (*self._sanear_plan(datos, libres, dias), modelo)

    def _sanear_plan(self, datos: Any, libres, dias) -> tuple[dict[int, dict[str, Any]], str | None]:
        if not isinstance(datos, dict):
            return {}, None
        items = datos.get("plan") or []
        if not isinstance(items, list):
            return {}, None
        h = date.fromisoformat(dias[0])
        por_id = {t["id"]: t for t in libres}
        por_texto = {lenguaje.sin_tildes(t["texto"]).lower(): t["id"] for t in libres}
        plan: dict[int, dict[str, Any]] = {}
        for n, it in enumerate(items, 1):
            if not isinstance(it, dict):
                continue
            tid = _entero(it.get("id"), None, 1, 10**9)
            if tid not in por_id:
                tid = por_texto.get(lenguaje.sin_tildes(str(it.get("texto", ""))).lower().strip())
            if tid is None or tid in plan:
                continue
            dia = _dia(it.get("dia_asignado", it.get("dia")), h, dias)
            if dia is None and it.get("dia_asignado", it.get("dia")) is None:
                continue  # sin día no es un plan (p. ej. el modelo devolvió la entrada tal cual)
            plan[tid] = {
                "dia": dia if dia in dias else (dias[-1] if dia else None),
                "orden": _entero(it.get("orden"), n, 0, 10_000) + n / 1000,
                "prioridad": _entero(it.get("prioridad"), por_id[tid]["prioridad"], 1, 5),
                "estimacion_min": _entero(it.get("estimacion_min", it.get("minutos")), None, 5, 1440),
            }
        resumen = datos.get("resumen")
        return plan, (str(resumen).strip()[:1000] if resumen else None)


_NOMBRE_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _etiqueta_dia(d: date, h: date) -> str:
    k = (d - h).days
    base = {0: "hoy", 1: "mañana", 2: "pasado mañana"}.get(k)
    return f"{base} ({_NOMBRE_DIA[d.weekday()]})" if base else _NOMBRE_DIA[d.weekday()]
