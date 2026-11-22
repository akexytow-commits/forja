"""Fixtures: un Ollama falso (httpx.MockTransport) y la app con una BBDD temporal."""
from __future__ import annotations

import hashlib
import json
import re

import httpx
import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError
from fastapi.testclient import TestClient

from backend.main import create_app

TOKEN = "token-de-prueba"
# Registro por defecto (doc 04 rev. 10): pequeno-general = instruct, pequeno-razonador = thinking-2507.
INSTRUCT = "qwen3:4b-instruct-2507-q4_K_M"
RAZONADOR = "qwen3:4b-thinking-2507-q4_K_M"
EMBED = "nomic-embed-text:latest"
DIM_EMBED = 768


def vector_falso(texto: str) -> list[float]:
    """Embedding determinista de bolsa de palabras (sin el prefijo de nomic): el coseno sí mide parecido."""
    for pref in ("search_document: ", "search_query: "):
        if texto.startswith(pref):
            texto = texto[len(pref):]
    v = [0.0] * DIM_EMBED
    for w in re.findall(r"\w+", texto.lower()):
        if len(w) > 2:
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM_EMBED] += 1.0
    v[0] += 0.01   # nunca el vector cero
    return v


class FakeOllama:
    def __init__(self):
        self.up = True
        self.instalados = {"qwen2.5-coder:3b", INSTRUCT, RAZONADOR, EMBED}
        self.embeds: list[dict] = []    # peticiones a /api/embed (doc 24)
        self.cargados: list[str] = []
        self.descargados_de_ram: list[str] = []
        self.chats: list[dict] = []
        self.respuesta = ["Hola", ", aquí ", "tienes:\n```python\nprint('hola')\n```"]
        self.pensamiento = ["Analizo ", "la petición."]
        self.json_respuestas: list[str] = []  # respuestas en bruto para peticiones sin streaming (cola)
        # Simula un modelo que razona aunque se pida think=false: el razonamiento sale en el contenido,
        # terminado en "</think>" (lo que hace qwen3:4b-thinking-2507 de verdad).
        self.fuga_think: list[str] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    @staticmethod
    def _ndjson(objs: list[dict]) -> httpx.Response:
        return httpx.Response(200, content="\n".join(json.dumps(o) for o in objs).encode() + b"\n")

    def handle(self, req: httpx.Request) -> httpx.Response:
        if not self.up:
            raise httpx.ConnectError("Ollama apagado", request=req)
        p = req.url.path
        body = json.loads(req.content) if req.content else {}
        if p == "/api/version":
            return httpx.Response(200, json={"version": "0.12.0"})
        if p == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": n} for n in sorted(self.instalados)]})
        if p == "/api/ps":
            return httpx.Response(200, json={"models": [{"name": n} for n in self.cargados]})
        if p == "/api/generate":
            modelo = body["model"]
            if body.get("keep_alive") == 0:
                if modelo in self.cargados:
                    self.cargados.remove(modelo)
                self.descargados_de_ram.append(modelo)
                return httpx.Response(200, json={"done": True})
            if modelo not in self.instalados:
                return httpx.Response(404, json={"error": f"model '{modelo}' not found"})
            self.cargados = [*self.cargados, modelo] if modelo not in self.cargados else self.cargados
            return httpx.Response(200, json={"done": True})
        if p == "/api/chat":
            modelo = body["model"]
            self.chats.append(body)
            if modelo not in self.instalados:
                return httpx.Response(404, json={"error": f"model '{modelo}' not found"})
            if modelo not in self.cargados:
                self.cargados.append(modelo)
            if body.get("stream") is False and self.json_respuestas:
                return httpx.Response(200, json={"message": {"role": "assistant", "content": self.json_respuestas.pop(0)},
                                                 "done": True})
            if body.get("stream") is False:
                pasos = {"pasos": [{"texto": "Crear el esqueleto de la app", "estimacion_min": 20},
                                   {"texto": "Implementar la pantalla principal", "estimacion_min": 45},
                                   {"texto": "Probar en el simulador", "estimacion_min": 15}]}
                return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps(pasos)},
                                                 "done": True})
            trozos = []
            if body.get("think"):
                trozos += [{"message": {"role": "assistant", "content": "", "thinking": t}, "done": False}
                           for t in self.pensamiento]
            elif self.fuga_think:
                trozos += [{"message": {"role": "assistant", "content": c}, "done": False} for c in self.fuga_think]
            trozos += [{"message": {"role": "assistant", "content": c}, "done": False} for c in self.respuesta]
            trozos.append({"message": {"role": "assistant", "content": ""}, "done": True,
                           "prompt_eval_count": 42, "eval_count": 17, "eval_duration": 2_000_000_000})
            return self._ndjson(trozos)
        if p == "/api/embed":
            self.embeds.append(body)
            if body["model"] not in self.instalados:
                return httpx.Response(404, json={"error": f"model '{body['model']}' not found"})
            if body["model"] not in self.cargados:
                self.cargados.append(body["model"])
            return httpx.Response(200, json={"model": body["model"],
                                             "embeddings": [vector_falso(t) for t in body["input"]]})
        if p == "/api/pull":
            modelo = body["model"]
            self.instalados.add(modelo)
            return self._ndjson([
                {"status": "pulling manifest"},
                {"status": "pulling abc", "digest": "sha256:abc", "total": 1000, "completed": 250},
                {"status": "pulling abc", "digest": "sha256:abc", "total": 1000, "completed": 1000},
                {"status": "success"},
            ])
        return httpx.Response(404, json={"error": "ruta desconocida"})


class KeyringMemoria(KeyringBackend):
    """Keyring en memoria: las pruebas nunca tocan el Administrador de credenciales real."""
    priority = 1

    def __init__(self):
        super().__init__()
        self.datos: dict[tuple[str, str], str] = {}

    def get_password(self, servicio, usuario):
        return self.datos.get((servicio, usuario))

    def set_password(self, servicio, usuario, clave):
        self.datos[(servicio, usuario)] = clave

    def delete_password(self, servicio, usuario):
        if self.datos.pop((servicio, usuario), None) is None:
            raise PasswordDeleteError("no existe")


@pytest.fixture(autouse=True)
def sin_claude_cli(monkeypatch, tmp_path):
    """Por defecto las pruebas no ven el Claude Code real del equipo."""
    monkeypatch.setenv("FORJA_CLAUDE_BIN", str(tmp_path / "no-existe" / "claude.exe"))
    monkeypatch.setenv("FORJA_DATA_DIR", str(tmp_path / "datos"))
    from backend import cloud_client
    cloud_client.configurar_bin("")
    cloud_client._SESION.update(t=0.0, estado=None, plan=None)


@pytest.fixture(autouse=True)
def keyring_memoria():
    anterior = keyring.get_keyring()
    kr = KeyringMemoria()
    keyring.set_keyring(kr)
    yield kr
    keyring.set_keyring(anterior)


class FakeNube:
    """Sustituye a ClienteNube: registra lo enviado y devuelve una respuesta fija."""

    def __init__(self):
        self.envios: list[dict] = []
        self.stop_reason = "end_turn"

    async def probar(self, modelo, backend="api"):
        return {"modelo": modelo, "nombre": "Claude de prueba"}

    async def stream(self, modelo, system, mensajes, esfuerzo, backend="api"):
        self.envios.append({"modelo": modelo, "system": system, "mensajes": mensajes, "esfuerzo": esfuerzo,
                            "backend": backend})
        yield {"tipo": "thinking", "texto": "Plan del firmware."}
        yield {"tipo": "token", "texto": "Aquí va el firmware completo."}
        yield {"tipo": "fin", "stop_reason": self.stop_reason, "categoria": None, "modelo": modelo,
               "tokens_in": 100, "tokens_out": 50}


@pytest.fixture
def nube() -> FakeNube:
    return FakeNube()


@pytest.fixture
def fake() -> FakeOllama:
    return FakeOllama()


@pytest.fixture
def make_client(tmp_path, fake, nube):
    abiertos = []

    def _make() -> TestClient:
        app = create_app(db_path=tmp_path / "forja.db", ollama_transport=fake.transport(),
                         precargar=False, token=TOKEN, nube=nube)
        c = TestClient(app)
        c.__enter__()
        c.headers.update({"X-Forja-Token": TOKEN})
        abiertos.append(c)
        return c

    yield _make
    for c in abiertos:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


def eventos(texto: str) -> list[tuple[str, dict]]:
    """Parsea un cuerpo text/event-stream en [(evento, datos)]."""
    out = []
    for bloque in texto.strip().split("\n\n"):
        ev, datos = "message", ""
        for linea in bloque.splitlines():
            if linea.startswith("event:"):
                ev = linea[6:].strip()
            elif linea.startswith("data:"):
                datos += linea[5:].strip()
        if datos:
            out.append((ev, json.loads(datos)))
    return out
