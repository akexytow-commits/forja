"""MOD-012 Cliente Nube: Claude (Anthropic) — ADR-0006.

settings.nube.backend:
- "claude_code" (por defecto): Claude Code en modo headless (`claude -p --output-format stream-json`)
  como subproceso local. Usa la sesión de la suscripción Claude del usuario: sin clave ni facturación
  aparte, pero consume del límite de uso del plan. Ruta en settings.nube.claude_bin ('' = autodetectar).
- "api": SDK oficial con clave propia (pago por uso). La clave vive en el Administrador de
  credenciales de Windows (keyring), nunca en la BBDD (NFR-010). Pensamiento adaptativo con resumen
  visible y fallback del servidor ante rechazos.
Solo se usa si el usuario activó la Nube (FR-006).
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import threading
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import anthropic
import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from .db import DB

SERVICIO_KEYRING = "FORJA"
USUARIO_KEYRING = "anthropic_api_key"
MODELOS_NUBE = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")
SIN_FALLBACK_SERVIDOR = {"claude-haiku-5-5"}  # Haiku 5.5 no tiene fallback del lado del servidor
BETA_FALLBACK = "server-side-fallback-2026-07-01"
EFFORT = {"bajo": "low", "medio": "medium", "extra": "high"}
MAX_TOKENS = 64000  # streaming: sin riesgo de timeout HTTP


class NubeError(Exception):
    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


# --- credenciales -------------------------------------------------------------------
def _clave() -> str | None:
    try:
        return keyring.get_password(SERVICIO_KEYRING, USUARIO_KEYRING)
    except KeyringError:
        return None


def tiene_clave() -> bool:
    return bool(_clave())


def guardar_clave(clave: str) -> None:
    keyring.set_password(SERVICIO_KEYRING, USUARIO_KEYRING, clave.strip())


def borrar_clave() -> None:
    try:
        keyring.delete_password(SERVICIO_KEYRING, USUARIO_KEYRING)
    except PasswordDeleteError:
        pass


BACKENDS = ("claude_code", "api")


def backend_nube(db: DB) -> str:
    p = db.get_setting("nube.backend", "claude_code")
    return p if p in BACKENDS else "claude_code"


_RUTA_CONFIGURADA = {"ruta": ""}


def configurar_bin(ruta: str | None) -> None:
    """settings.nube.claude_bin: ruta elegida por el usuario ('' = autodetectar)."""
    _RUTA_CONFIGURADA["ruta"] = (ruta or "").strip().strip('"')
    _SESION["t"] = 0.0


def detectar_claude() -> str | None:
    hallado = shutil.which("claude")
    if hallado:
        return hallado
    local = Path.home() / ".local" / "bin" / "claude.exe"
    return str(local) if local.exists() else None


def ejecutable_claude() -> str | None:
    """Ruta del CLI: FORJA_CLAUDE_BIN (pruebas) > nube.claude_bin > autodetección."""
    forzado = os.environ.get("FORJA_CLAUDE_BIN") or _RUTA_CONFIGURADA["ruta"]
    if forzado:
        return forzado if Path(forzado).is_file() else None
    return detectar_claude()


# Estado de la sesión de Claude Code (se comprueba con `claude auth status`, cacheado).
_SESION: dict[str, Any] = {"t": 0.0, "estado": None, "plan": None}
TTL_SESION_S = 300


def comprobar_sesion(forzar: bool = False) -> str:
    """'ok' | 'sin_cli' | 'sin_sesion' | 'desconocido'. Bloqueante: llamar con asyncio.to_thread."""
    if not forzar and _SESION["estado"] and time.monotonic() - _SESION["t"] < TTL_SESION_S:
        return _SESION["estado"]
    b = ejecutable_claude()
    plan = None
    if not b:
        estado = "sin_cli"
    else:
        try:
            r = subprocess.run([b, "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60, env=_entorno(), cwd=_cwd_aislado(),
                               creationflags=_SIN_VENTANA, check=False)
            info = json.loads(r.stdout)
            estado = "ok" if info.get("loggedIn") else "sin_sesion"
            plan = info.get("subscriptionType") or info.get("authMethod")
        except (OSError, ValueError, subprocess.SubprocessError):
            estado = "desconocido"
    _SESION.update(t=time.monotonic(), estado=estado, plan=plan)
    return estado


def sesion_cacheada() -> str | None:
    return _SESION["estado"]


def listo(db: DB, prov: str | None = None) -> bool:
    """El proveedor tiene lo que necesita: CLI instalado o clave guardada."""
    prov = prov or backend_nube(db)
    if prov == "claude_code":
        # Sin CLI o con la sesión cerrada, el tier Nube se deshabilita (ADR-0006).
        return ejecutable_claude() is not None and _SESION["estado"] != "sin_sesion"
    return tiene_clave()


def activada(db: DB) -> bool:
    return db.get_setting("nube.activada") == "1" and listo(db)


# --- cliente --------------------------------------------------------------------------
def _traducir(e: Exception) -> NubeError:
    if isinstance(e, anthropic.AuthenticationError):
        return NubeError("NUBE_CLAVE", "Anthropic rechazó la clave API. Revísala en Ajustes.")
    if isinstance(e, anthropic.PermissionDeniedError):
        return NubeError("NUBE_PERMISO", "La clave no tiene permiso para ese modelo.")
    if isinstance(e, anthropic.NotFoundError):
        return NubeError("NUBE_MODELO", "Anthropic no reconoce ese modelo.")
    if isinstance(e, anthropic.RateLimitError):
        return NubeError("NUBE_LIMITE", "Límite de uso de Anthropic alcanzado. Espera un poco y reintenta.")
    if isinstance(e, anthropic.APIStatusError):
        return NubeError("NUBE_ERROR", f"Error de Anthropic ({e.status_code}): {e.message}")
    if isinstance(e, anthropic.APIConnectionError):
        return NubeError("NUBE_SIN_RED", "No hay conexión con Anthropic (¿sin internet?).")
    return NubeError("NUBE_ERROR", str(e))


class ClienteNube:
    """Despacha al proveedor elegido; misma interfaz para los dos."""

    def __init__(self):
        self.api = ClienteApi()
        self.claude_code = ClienteClaudeCode()

    def _de(self, prov: str):
        return self.claude_code if prov == "claude_code" else self.api

    async def probar(self, modelo: str, backend: str = "api") -> dict[str, Any]:
        return await self._de(backend).probar(modelo)

    def stream(self, modelo: str, system: str, mensajes: list[dict[str, str]], esfuerzo: str,
               backend: str = "api") -> AsyncIterator[dict[str, Any]]:
        return self._de(backend).stream(modelo, system, mensajes, esfuerzo)


class ClienteApi:
    def _cliente(self) -> anthropic.AsyncAnthropic:
        clave = _clave()
        if not clave:
            raise NubeError("NUBE_SIN_CLAVE", "No hay clave de Anthropic guardada.")
        return anthropic.AsyncAnthropic(api_key=clave, max_retries=2)

    async def probar(self, modelo: str) -> dict[str, Any]:
        try:
            m = await self._cliente().models.retrieve(modelo)
        except NubeError:
            raise
        except Exception as e:  # noqa: BLE001 — se traduce a un error legible
            raise _traducir(e) from e
        return {"modelo": m.id, "nombre": m.display_name}

    async def stream(self, modelo: str, system: str, mensajes: list[dict[str, str]],
                     esfuerzo: str) -> AsyncIterator[dict[str, Any]]:
        """Produce {"tipo": "thinking"|"token", "texto"} y al final {"tipo": "fin", ...}."""
        cliente = self._cliente()
        extra: dict[str, Any] = {}
        if modelo not in SIN_FALLBACK_SERVIDOR:
            extra = {"betas": [BETA_FALLBACK], "fallbacks": "default"}
        try:
            async with cliente.beta.messages.stream(
                model=modelo,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=mensajes,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": EFFORT[esfuerzo]},
                **extra,
            ) as s:
                async for ev in s:
                    if ev.type == "content_block_delta":
                        if ev.delta.type == "thinking_delta" and ev.delta.thinking:
                            yield {"tipo": "thinking", "texto": ev.delta.thinking}
                        elif ev.delta.type == "text_delta" and ev.delta.text:
                            yield {"tipo": "token", "texto": ev.delta.text}
                final = await s.get_final_message()
        except NubeError:
            raise
        except anthropic.AnthropicError as e:
            raise _traducir(e) from e
        detalle = getattr(final, "stop_details", None)
        yield {
            "tipo": "fin",
            "stop_reason": final.stop_reason,
            "categoria": getattr(detalle, "category", None) if detalle else None,
            "modelo": final.model,
            "tokens_in": final.usage.input_tokens,
            "tokens_out": final.usage.output_tokens,
        }


# --- suscripción: CLI de Claude Code ----------------------------------------------------
def _cwd_aislado() -> str:
    """Carpeta vacía para el CLI: así no recoge CLAUDE.md ni ajustes de proyecto ajenos."""
    from .config import data_dir
    d = data_dir() / "claude-code"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def _entorno() -> dict[str, str]:
    env = dict(os.environ)
    # Sin clave API en el entorno: el CLI usa la sesión de la suscripción y no factura por API.
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"):
        env.pop(k, None)
    return env


def componer_prompt(mensajes: list[dict[str, str]]) -> str:
    """El CLI recibe un solo prompt: el historial va delante, etiquetado, y el último mensaje al final."""
    *previos, actual = mensajes
    if not previos:
        return actual["content"]
    partes = ["<historial>"]
    for m in previos:
        quien = "usuario" if m["role"] == "user" else "asistente"
        partes.append(f"<{quien}>\n{m['content']}\n</{quien}>")
    partes.append("</historial>\n\nResponde al siguiente mensaje del usuario, teniendo en cuenta el historial:\n")
    partes.append(actual["content"])
    return "\n".join(partes)


def _error_cli(texto: str) -> NubeError:
    t = (texto or "").lower()
    if "login" in t or "log in" in t or "not logged" in t or "authenticat" in t:
        return NubeError("NUBE_SIN_SESION",
                         "Claude Code no tiene sesión iniciada. Abre una terminal y ejecuta: claude auth login")
    if "limit" in t or "rate" in t or "usage" in t:
        return NubeError("NUBE_LIMITE", "Has llegado al límite de uso de tu suscripción. Espera a que se renueve.")
    return NubeError("NUBE_ERROR", f"Claude Code: {texto.strip()[:300] or 'error desconocido'}")


_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ClienteClaudeCode:
    TIMEOUT_S = 1800

    def _bin(self) -> str:
        b = ejecutable_claude()
        if not b:
            raise NubeError("NUBE_SIN_CLI", "No encuentro Claude Code (claude.exe). Instálalo e inicia sesión.")
        return b

    async def probar(self, modelo: str) -> dict[str, Any]:
        self._bin()
        estado = await asyncio.to_thread(comprobar_sesion, True)
        if estado == "sin_sesion":
            raise _error_cli("not logged in")
        if estado != "ok":
            raise NubeError("NUBE_ERROR", "No pude consultar el estado de Claude Code (`claude auth status`).")
        plan = (_SESION["plan"] or "").capitalize()
        # No se devuelve el email ni la organización: solo lo necesario para la UI.
        return {"modelo": modelo, "nombre": f"Suscripción Claude {plan}".strip()}

    def _comando(self, modelo: str, system: str, esfuerzo: str) -> list[str]:
        return [self._bin(), "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                "--model", modelo, "--effort", EFFORT[esfuerzo], "--tools", "", "--system-prompt", system,
                "--no-session-persistence", "--safe-mode", "--strict-mcp-config", "--disable-slash-commands"]

    async def stream(self, modelo: str, system: str, mensajes: list[dict[str, str]],
                     esfuerzo: str) -> AsyncIterator[dict[str, Any]]:
        cmd = self._comando(modelo, system, esfuerzo)
        prompt = componer_prompt(mensajes)
        bucle = asyncio.get_running_loop()
        cola: asyncio.Queue = asyncio.Queue()
        fin = object()
        # Hilo + Popen: funciona con cualquier event loop de Windows (uvicorn usa Selector).
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=_entorno(), cwd=_cwd_aislado(), creationflags=_SIN_VENTANA)
        errores: list[str] = []

        def _leer():
            try:
                proc.stdin.write(prompt.encode("utf-8"))
                proc.stdin.close()
                for linea in proc.stdout:
                    bucle.call_soon_threadsafe(cola.put_nowait, linea)
            except (OSError, ValueError):
                pass
            finally:
                bucle.call_soon_threadsafe(cola.put_nowait, fin)

        def _leer_err():
            for linea in proc.stderr:
                errores.append(linea.decode("utf-8", "replace"))

        threading.Thread(target=_leer, daemon=True).start()
        threading.Thread(target=_leer_err, daemon=True).start()
        modelo_real, resultado = modelo, None
        try:
            while True:
                linea = await asyncio.wait_for(cola.get(), timeout=self.TIMEOUT_S)
                if linea is fin:
                    break
                try:
                    d = json.loads(linea)
                except ValueError:
                    continue
                if d.get("type") == "stream_event":
                    ev = d.get("event") or {}
                    if ev.get("type") == "message_start":
                        modelo_real = (ev.get("message") or {}).get("model") or modelo_real
                    elif ev.get("type") == "content_block_delta":
                        delta = ev.get("delta") or {}
                        if delta.get("type") == "thinking_delta" and delta.get("thinking"):
                            yield {"tipo": "thinking", "texto": delta["thinking"]}
                        elif delta.get("type") == "text_delta" and delta.get("text"):
                            yield {"tipo": "token", "texto": delta["text"]}
                elif d.get("type") == "result":
                    resultado = d
        except TimeoutError:
            raise NubeError("NUBE_ERROR", "Claude Code no respondió a tiempo.") from None
        finally:
            if proc.poll() is None:
                proc.kill()
        if resultado is None:
            raise _error_cli("".join(errores) or "el CLI terminó sin resultado")
        if resultado.get("is_error"):
            raise _error_cli(str(resultado.get("result") or resultado.get("subtype") or ""))
        uso = resultado.get("usage") or {}
        yield {
            "tipo": "fin",
            "stop_reason": resultado.get("stop_reason") or "end_turn",
            "categoria": None,
            "modelo": modelo_real,
            "tokens_in": (uso.get("input_tokens") or 0) + (uso.get("cache_read_input_tokens") or 0)
                         + (uso.get("cache_creation_input_tokens") or 0),
            "tokens_out": uso.get("output_tokens"),
        }
