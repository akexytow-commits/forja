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
from pathlib import Path
from typing import Any, AsyncIterator

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
        """Deja en RAM como mucho `etiqueta`. Devuelve True si habrá que cargarla."""
        etiqueta = normalizar(etiqueta)
        cargados = await self.cargados()
        for m in cargados:
            if m != etiqueta:
                await self.descargar_de_ram(m)
        return etiqueta not in cargados

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
                    async for linea in r.aiter_lines():
                        if not linea.strip():
                            continue
                        dato = json.loads(linea)
                        if "error" in dato:
                            raise OllamaError(dato["error"])
                        yield dato
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise OllamaCaido(str(e)) from e

    async def chat_completo(self, etiqueta: str, mensajes: list[dict[str, str]], opciones: dict[str, Any],
                            formato: str | dict | None = "json", think: bool | None = None) -> str:
        """Una respuesta completa (sin streaming); devuelve el contenido en bruto.

        formato: "json", un esquema JSON (salidas estructuradas de Ollama) o None.
        """
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
            return r.json()["message"]["content"]
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
