"""MOD-010 Router de Modelos — tabla determinista (ADR-0004, 04-modelo-de-modelos.md).

resolver(modo, tier, esfuerzo, longitud_entrada_tokens) -> PlanDeModelo
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from .config import PROMPTS_DIR

MODOS = ("scripts", "seguridad", "tareas")
TIERS = ("pequeno", "grande", "nube")
ESFUERZOS = ("bajo", "medio", "extra")

# Paso 1 — familia de modelo por (modo, tier)
FAMILIA: dict[tuple[str, str], str] = {
    ("scripts", "pequeno"): "pequeno-codigo",
    ("scripts", "grande"): "grande-codigo",
    ("scripts", "nube"): "nube-frontera",
    ("seguridad", "pequeno"): "pequeno-general",
    ("seguridad", "grande"): "grande-general",
    ("seguridad", "nube"): "nube-frontera",
    ("tareas", "pequeno"): "pequeno-general",
    ("tareas", "grande"): "grande-general",
    ("tareas", "nube"): "nube-frontera",
}

# Paso 2a — modelos CON thinking nativo (Qwen3)
PARAMS_THINKING: dict[str, dict[str, Any]] = {
    "bajo": {"enable_thinking": False, "reasoning_effort": None, "temperatura": 0.3, "num_predict": 512},
    "medio": {"enable_thinking": True, "reasoning_effort": "medium", "temperatura": 0.5, "num_predict": 1024},
    "extra": {"enable_thinking": True, "reasoning_effort": "high", "temperatura": 0.7, "num_predict": 2048},
}

# Paso 2b — modelos SIN thinking: el esfuerzo se emula con prompt + parámetros
PARAMS_EMULADO: dict[str, dict[str, Any]] = {
    "bajo": {"estrategia": "directa", "temperatura": 0.2, "num_predict": 512, "instruccion": ""},
    "medio": {
        "estrategia": "paso_a_paso_breve",
        "temperatura": 0.4,
        "num_predict": 1024,
        "instruccion": "Piensa paso a paso brevemente antes de responder.",
    },
    "extra": {
        "estrategia": "bloque_plan",
        "temperatura": 0.6,
        "num_predict": 2048,
        "instruccion": (
            "Antes del código, razona dentro de un bloque <plan>...</plan> (pasos, supuestos, casos "
            "límite). Después del </plan>, da la respuesta final con el código."
        ),
    },
}

# Paso 3 — contexto por tier (presupuesto de RAM, 01-restricciones-hardware.md)
CONTEXTO: dict[str, tuple[int, int | None]] = {
    "pequeno": (8192, 16384),
    "grande": (4096, 8192),
    "nube": (32768, None),
}

EFFORT_NUBE = {"bajo": "low", "medio": "medium", "extra": "high"}

HERRAMIENTAS: dict[str, list[str]] = {
    "scripts": ["guardar_archivo"],  # siempre con confirmación (ST-040); se activa en Rama 5
    "seguridad": [],  # G-2: ninguna herramienta activa
    "tareas": [],
}


class RouterError(ValueError):
    pass


@dataclass
class PlanDeModelo:
    alias: str
    tier: str
    modo: str
    esfuerzo: str
    etiqueta_ollama: str | None
    proveedor_nube: str | None
    thinking_nativo: bool
    system_prompt: str
    params: dict[str, Any] = field(default_factory=dict)
    herramientas: list[str] = field(default_factory=list)
    requiere_carga: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def tokens_aprox(texto: str) -> int:
    """Estimación barata de tokens (≈3.5 caracteres/token en español con código)."""
    return math.ceil(len(texto) / 3.5) if texto else 0


def num_ctx_para(tier: str, longitud_entrada_tokens: int, num_predict: int) -> int:
    defecto, tope = CONTEXTO[tier]
    necesario = longitud_entrada_tokens + num_predict + 256
    if necesario <= defecto:
        return defecto
    ampliado = math.ceil(necesario / 1024) * 1024
    return min(ampliado, tope) if tope else ampliado


def cargar_prompt(modo: str) -> str:
    path = PROMPTS_DIR / f"{modo}.txt"
    if not path.exists():
        raise RouterError(f"No hay prompt de sistema para el modo '{modo}'.")
    return path.read_text(encoding="utf-8")


def resolver(
    modo: str,
    tier: str,
    esfuerzo: str,
    longitud_entrada_tokens: int = 0,
    registro: dict[str, dict[str, Any]] | None = None,
    modelos_cargados: list[str] | None = None,
) -> PlanDeModelo:
    if modo not in MODOS:
        raise RouterError(f"Modo desconocido: {modo}")
    if tier not in TIERS:
        raise RouterError(f"Tier desconocido: {tier}")
    if esfuerzo not in ESFUERZOS:
        raise RouterError(f"Esfuerzo desconocido: {esfuerzo}")

    alias = FAMILIA[(modo, tier)]
    fila = (registro or {}).get(alias)
    if fila is None:
        raise RouterError(f"El alias '{alias}' no está en el registro de modelos.")

    thinking = bool(fila.get("thinking"))
    if tier == "nube":
        # Claude: pensamiento adaptativo siempre activo; el esfuerzo va en output_config.effort.
        base = {"temperatura": None, "num_predict": 64000, "effort": EFFORT_NUBE[esfuerzo]}
        instruccion = ""
    elif thinking:
        base = dict(PARAMS_THINKING[esfuerzo])
        instruccion = ""
    else:
        base = dict(PARAMS_EMULADO[esfuerzo])
        instruccion = base.pop("instruccion")

    params: dict[str, Any] = {
        "temperatura": base.pop("temperatura"),
        "num_predict": base.pop("num_predict"),
        **base,
    }
    params["num_ctx"] = num_ctx_para(tier, longitud_entrada_tokens, params["num_predict"])

    es_nube = tier == "nube"
    etiqueta = None if es_nube else fila["etiqueta"]
    plantilla = cargar_prompt(modo)
    system_prompt = plantilla.format(
        modelo=etiqueta or "proveedor de nube",
        tier=tier,
        esfuerzo=esfuerzo,
        lugar="en la nube (el usuario lo ha pedido)" if es_nube else "en local, solo CPU y 8 GB de RAM",
    )
    if instruccion:
        system_prompt += "\n\n" + instruccion

    cargados = modelos_cargados or []
    return PlanDeModelo(
        alias=alias,
        tier=tier,
        modo=modo,
        esfuerzo=esfuerzo,
        etiqueta_ollama=etiqueta,
        proveedor_nube=fila["etiqueta"] if es_nube else None,
        thinking_nativo=thinking or es_nube,
        system_prompt=system_prompt,
        params=params,
        herramientas=list(HERRAMIENTAS[modo]),
        requiere_carga=(not es_nube) and (etiqueta not in cargados),
    )
