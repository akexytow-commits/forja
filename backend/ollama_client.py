"""MOD-011 Gestor de Ollama: salud, listar/descargar, cargar/descargar (uno a la vez).

Usa la API nativa de Ollama (/api/*) y no la compatible con OpenAI (/v1), porque solo la nativa
permite fijar num_ctx/num_gpu por petición y devuelve el razonamiento ("thinking") separado del
contenido.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from .config import KEEP_ALIVE


class OllamaCaido(Exception):
    """Ollama no responde en localhost:11434 (NFR-020)."""


class ModeloFaltante(Exception):
    def __init__(self, etiqueta: str):
        super().__init__(etiqueta)
        self.etiqueta = etiqueta


class OllamaError(Exception):
    pass


def normalizar(etiqueta: str) -> str:
    return etiqueta if ":" in etiqueta else f"{etiqueta}:latest"


NO_THINK = "/no_think"
NUM_PREDICT_MIN_NO_THINK = 768   # = router.NUM_PREDICT_MIN_NO_THINK (doc 04 rev. 8)


def es_embeddings(etiqueta: str) -> bool:
    """Modelos de embeddings (nomic-embed-text, mxbai-embed…): no cuentan para «un solo modelo en RAM»."""
    return "embed" in normalizar(etiqueta).split(":")[0]


def es_qwen3(etiqueta: str) -> bool:
    """Modelos Qwen3 que razonan (híbridos o thinking). qwen2.5-coder y los qwen3 *instruct* no."""
    e = normalizar(etiqueta).lower()
    return e.startswith("qwen3") and "instruct" not in e


ABRE_THINK, CIERRA_THINK = "<think>", "</think>"


def _cola_parcial(texto: str, marca: str) -> int:
    """Longitud del final de `texto` que podría ser el principio de `marca` (para no partir la etiqueta)."""
    for n in range(min(len(marca) - 1, len(texto)), 0, -1):
        if marca.startswith(texto[-n:]):
            return n
    return 0


class FiltroThink:
    """Red de seguridad (doc 04 §Tope de razonamiento, B): con el thinking apagado, un modelo que razona
    igualmente lo mete en el contenido, terminado en `</think>`. Ese texto es razonamiento, no respuesta.

    trozo(texto) → lista de ("thinking" | "content" | "reclasificar", texto). "reclasificar" significa: todo
    el contenido ya emitido era razonamiento (el `</think>` llegó cuando ya se mostraba como respuesta).
    """

    def __init__(self, pensando: bool = False):
        self.pensando = pensando      # True: lo que llegue es razonamiento hasta el </think>
        self.inicio = True            # aún no ha llegado texto visible
        self.cola = ""
        self.emitido = False          # se emitió contenido (visible) desde el último </think>

    def trozo(self, texto: str) -> list[tuple[str, str]]:
        buf, self.cola, salida = self.cola + texto, "", []
        if self.inicio:
            limpio = buf.lstrip()
            if not limpio or (len(limpio) < len(ABRE_THINK) and ABRE_THINK.startswith(limpio)):
                self.cola = buf       # todavía no se sabe si empieza por <think>
                return salida
            self.inicio = False
            if limpio.startswith(ABRE_THINK):
                self.pensando, buf = True, limpio[len(ABRE_THINK):]
        while CIERRA_THINK in buf:
            antes, buf = buf.split(CIERRA_THINK, 1)
            if self.pensando:
                if antes:
                    salida.append(("thinking", antes))
            else:
                if antes:
                    salida.append(("content", antes))
                salida.append(("reclasificar", ""))
            self.pensando, self.emitido, buf = False, False, buf.lstrip("\r\n")
        n = _cola_parcial(buf, CIERRA_THINK)
        if n:
            buf, self.cola = buf[:-n], buf[-n:]
        if buf:
            salida.append(("thinking" if self.pensando else "content", buf))
            self.emitido = self.emitido or not self.pensando
        return salida

    def fin(self) -> list[tuple[str, str]]:
        resto, self.cola = self.cola, ""
        if self.inicio:
            resto = resto.strip()
        return [("thinking" if self.pensando else "content", resto)] if resto else []


def quitar_razonamiento(texto: str) -> str:
    """Respuesta completa (sin streaming): lo que va antes del último </think> es razonamiento."""
    return texto.rsplit(CIERRA_THINK, 1)[-1].lstrip() if CIERRA_THINK in texto else texto


def sin_thinking(etiqueta: str, mensajes: list[dict[str, str]], opciones: dict[str, Any],
                 think: bool | None) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Doc 04 rev. 8: qwen3 a veces razona aunque se pida think=false (y agota num_predict sin responder).
    Siempre que se use qwen3 con thinking apagado, en cualquier modo: se añade /no_think al último mensaje
    del usuario (más fiable que solo enable_thinking=false) y num_predict nunca baja de 768.
    Trabaja sobre copias: lo que se guarda en la BBDD no lleva la marca."""
    if think is not False or not es_qwen3(etiqueta):
        return mensajes, opciones
    mensajes = [dict(m) for m in mensajes]
    for m in reversed(mensajes):
        if m.get("role") == "user":
            if NO_THINK not in m.get("content", ""):
                m["content"] = f"{m.get('content', '').rstrip()}\n\n{NO_THINK}"
            break
    else:
        mensajes.append({"role": "user", "content": NO_THINK})
    opciones = dict(opciones)
    opciones["num_predict"] = max(int(opciones.get("num_predict") or 0), NUM_PREDICT_MIN_NO_THINK)
    return mensajes, opciones


class OllamaClient:
    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    def _client(self, timeout: float | None = 10.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, transport=self._transport, timeout=timeout)

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            async with self._client(timeout=5.0) as c:
                r = await c.get(path)
                r.raise_for_status()
                return r.json()
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            raise OllamaCaido(str(e)) from e

    # --- salud / inventario ----------------------------------------------
    async def version(self) -> str | None:
        try:
            return (await self._get("/api/version")).get("version")
        except (OllamaCaido, httpx.HTTPError):
            return None

    async def instalados(self) -> list[str]:
        data = await self._get("/api/tags")
        return [normalizar(m["name"]) for m in data.get("models", [])]

    async def cargados(self) -> list[str]:
        data = await self._get("/api/ps")
        return [normalizar(m["name"]) for m in data.get("models", [])]

    # --- carga / descarga (FR-005, ST-020) --------------------------------
    async def descargar_de_ram(self, etiqueta: str) -> None:
        try:
            async with self._client(timeout=30.0) as c:
                await c.post("/api/generate", json={"model": etiqueta, "keep_alive": 0})
        except httpx.ConnectError as e:
            raise OllamaCaido(str(e)) from e

    async def asegurar_unico(self, etiqueta: str) -> bool:
        """Deja en RAM como mucho `etiqueta` (más el modelo de embeddings, doc 24: es pequeño y convive con el
        chat). Devuelve True si habrá que cargarla."""
        etiqueta = normalizar(etiqueta)
        cargados = await self.cargados()
        for m in cargados:
            if m != etiqueta and not es_embeddings(m):
                await self.descargar_de_ram(m)
        return etiqueta not in cargados

    # --- embeddings (doc 24, API-072/073) ------------------------------------
    async def embed(self, etiqueta: str, textos: list[str], num_ctx: int = 8192) -> list[list[float]]:
        """POST /api/embed: un vector por texto. num_ctx 8192 (el defecto de Ollama, 2048, corta fragmentos largos)."""
        cuerpo = {"model": normalizar(etiqueta), "input": textos, "truncate": True, "keep_alive": KEEP_ALIVE,
                  "options": {"num_ctx": num_ctx, "num_gpu": 0}}
        try:
            async with self._client(timeout=httpx.Timeout(10.0, read=600.0)) as c:
                r = await c.post("/api/embed", json=cuerpo)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise OllamaCaido(str(e)) from e
        if r.status_code == 404:
            raise ModeloFaltante(normalizar(etiqueta))
        if r.status_code >= 400:
            raise OllamaError(_mensaje_error(r.text))
        vectores = r.json().get("embeddings") or []
        if len(vectores) != len(textos):
            raise OllamaError(f"/api/embed devolvió {len(vectores)} vectores para {len(textos)} textos.")
        return vectores

    async def cargar(self, etiqueta: str) -> None:
        etiqueta = normalizar(etiqueta)
        await self.asegurar_unico(etiqueta)
        try:
            async with self._client(timeout=600.0) as c:
                r = await c.post(
                    "/api/generate",
                    json={"model": etiqueta, "keep_alive": KEEP_ALIVE, "options": {"num_gpu": 0}},
                )
        except httpx.ConnectError as e:
            raise OllamaCaido(str(e)) from e
        if r.status_code == 404:
            raise ModeloFaltante(etiqueta)
        if r.status_code >= 400:
            raise OllamaError(r.text)

    # --- generación --------------------------------------------------------
    async def chat_stream(
        self,
        etiqueta: str,
        mensajes: list[dict[str, str]],
        opciones: dict[str, Any],
        think: bool | None,
    ) -> AsyncIterator[dict[str, Any]]:
        mensajes, opciones = sin_thinking(etiqueta, mensajes, opciones, think)
        cuerpo: dict[str, Any] = {
            "model": normalizar(etiqueta),
            "messages": mensajes,
            "stream": True,
            "keep_alive": KEEP_ALIVE,
            "options": opciones,
        }
        if think is not None:
            cuerpo["think"] = think
        try:
            async with self._client(timeout=httpx.Timeout(10.0, read=600.0)) as c:
                async with c.stream("POST", "/api/chat", json=cuerpo) as r:
                    if r.status_code == 404:
                        raise ModeloFaltante(normalizar(etiqueta))
                    if r.status_code >= 400:
                        await r.aread()
                        raise OllamaError(_mensaje_error(r.text))
                    # Con el thinking apagado (o sin pedirlo), un `…</think>` en el contenido es razonamiento.
                    # (No se da por razonamiento de entrada aunque el modelo sea "thinking": si nunca llegara el
                    # </think>, se ocultaría la respuesta entera. Se muestra y, si llega, se reclasifica.)
                    filtro = FiltroThink() if think is not True else None
                    async for linea in r.aiter_lines():
                        if not linea.strip():
                            continue
                        dato = json.loads(linea)
                        if "error" in dato:
                            raise OllamaError(dato["error"])
                        if filtro is None:
                            yield dato
                            continue
                        m = dato.get("message") or {}
                        piezas = filtro.trozo(m.get("content") or "")
                        if dato.get("done"):
                            piezas += filtro.fin()
                        if m.get("thinking"):
                            piezas.insert(0, ("thinking", m["thinking"]))
                        if not piezas and not dato.get("done"):
                            continue
                        for i, (tipo, texto) in enumerate(piezas):
                            final = dato.get("done") and i == len(piezas) - 1
                            base = {k: v for k, v in dato.items() if k != "message"} if final else {"done": False}
                            if tipo == "reclasificar":
                                yield {**base, "reclasificar": True, "message": {"role": "assistant", "content": ""}}
                            else:
                                yield {**base, "message": {"role": "assistant", tipo: texto}}
                        if dato.get("done") and not piezas:
                            yield {**dato, "message": {"role": "assistant", "content": ""}}
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise OllamaCaido(str(e)) from e

    async def chat_completo(self, etiqueta: str, mensajes: list[dict[str, str]], opciones: dict[str, Any],
                            formato: str | dict | None = "json", think: bool | None = None) -> str:
        """Una respuesta completa (sin streaming); devuelve el contenido en bruto.

        formato: "json", un esquema JSON (salidas estructuradas de Ollama) o None.
        """
        mensajes, opciones = sin_thinking(etiqueta, mensajes, opciones, think)
        cuerpo: dict[str, Any] = {"model": normalizar(etiqueta), "messages": mensajes, "stream": False,
                                  "keep_alive": KEEP_ALIVE, "options": opciones}
        if formato:
            cuerpo["format"] = formato
        if think is not None:
            cuerpo["think"] = think
        try:
            async with self._client(timeout=httpx.Timeout(10.0, read=900.0)) as c:
                r = await c.post("/api/chat", json=cuerpo)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise OllamaCaido(str(e)) from e
        if r.status_code == 404:
            raise ModeloFaltante(normalizar(etiqueta))
        if r.status_code >= 400:
            raise OllamaError(_mensaje_error(r.text))
        try:
            contenido = r.json()["message"]["content"]
            return quitar_razonamiento(contenido) if think is not True else contenido
        except (ValueError, KeyError, TypeError) as e:
            raise OllamaError("Respuesta de Ollama sin contenido.") from e

    async def chat_json(self, etiqueta: str, mensajes: list[dict[str, str]], opciones: dict[str, Any]) -> Any:
        """Una respuesta completa forzada a JSON (format=json). Lanza OllamaError si no es JSON."""
        contenido = await self.chat_completo(etiqueta, mensajes, opciones)
        try:
            return json.loads(contenido)
        except (ValueError, TypeError) as e:
            raise OllamaError("El modelo no devolvió JSON válido.") from e

    async def pull_stream(self, etiqueta: str) -> AsyncIterator[dict[str, Any]]:
        try:
            async with self._client(timeout=httpx.Timeout(10.0, read=None)) as c:
                async with c.stream("POST", "/api/pull", json={"model": etiqueta, "stream": True}) as r:
                    if r.status_code >= 400:
                        await r.aread()
                        raise OllamaError(_mensaje_error(r.text))
                    async for linea in r.aiter_lines():
                        if not linea.strip():
                            continue
                        dato = json.loads(linea)
                        if "error" in dato:
                            raise OllamaError(dato["error"])
                        yield dato
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise OllamaCaido(str(e)) from e


def _mensaje_error(texto: str) -> str:
    try:
        return json.loads(texto).get("error", texto)
    except (ValueError, AttributeError):
        return texto


def ejecutable_ollama() -> str | None:
    """Busca ollama.exe (PATH o instalación por defecto en Windows)."""
    encontrado = shutil.which("ollama")
    if encontrado:
        return encontrado
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidato = Path(local) / "Programs" / "Ollama" / "ollama.exe"
        if candidato.exists():
            return str(candidato)
    return None


def arrancar_ollama() -> bool:
    """BTN-070: lanza `ollama serve` en segundo plano. False si no está instalado."""
    exe = ejecutable_ollama()
    if not exe:
        return False
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    subprocess.Popen(
        [exe, "serve"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    return True
