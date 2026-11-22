"""MOD-050 Estimador de Escalado (05-escalado-y-estimador.md).

Cálculo explícito y transparente, sin llamar a ningún modelo:
  1. tokens de entrada previstos  = (contexto + mensaje) en palabras × 1.3
  2. salida prevista (tokens)     = heurística por palabras clave e intención
  3. complejidad 0–100            = ficheros/módulos, dominios difíciles, "todo de una vez"
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

from .router import CONTEXTO

# Base de la "salida máxima razonable en local" (× umbral.factor_salida). Se queda en 2048 aunque el router
# suba num_predict (doc 04 rev. 8): ese aumento es presupuesto para el thinking, no más respuesta útil.
SALIDA_LOCAL_BASE = 2048

CABE_LOCAL, JUSTO, RECOMENDADO_NUBE = "CABE_LOCAL", "JUSTO", "RECOMENDADO_NUBE"

UMBRALES_DEFECTO = {"complejidad_nube": 70, "complejidad_justo": 45, "factor_salida": 2.0}

SALIDA_LARGA = (
    "firmware completo", "firmware entero", "proyecto entero", "proyecto completo", "todas las funciones",
    "codigo entero", "codigo completo", "todo el codigo", "aplicacion completa", "app completa",
    "programa completo", "sistema completo", "juego completo", "generame el codigo entero",
    "desde cero", "libreria completa", "api completa",
)
SALIDA_CORTA = (
    "explicame", "explica", "corrige esta linea", "que significa", "por que", "una linea", "resume",
    "que hace", "traduce", "renombra",
)
DOMINIOS_DIFICILES = (
    "firmware", "driver", "kernel", "criptograf", "cifrado", "parser binario", "formato binario",
    "bootloader", "rtos", "dma", "interrupci", "compilador", "emulador", "protocolo", "radio", "sub-ghz",
)
TODO_DE_UNA = ("todo de una vez", "de una vez", "completo", "completa", "entero", "entera", "todas las", "todos los")
RE_FICHERO = re.compile(r"\b[\w-]+\.(c|h|cpp|hpp|py|js|ts|rs|go|java|ps1|sh|ino|fap)\b", re.I)
RE_N_PIEZAS = re.compile(r"\b(\d+)\s+(ficheros|archivos|modulos|funciones|pantallas|clases|endpoints)\b")


def _norm(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes)


def tokens_por_palabras(texto: str) -> int:
    return math.ceil(len(texto.split()) * 1.3)


def salida_prevista(t: str) -> int:
    if any(k in t for k in SALIDA_LARGA):
        base = 6000
    elif any(t.startswith(k) or f" {k}" in t for k in SALIDA_CORTA):
        base = 300
    else:
        base = 800
    piezas = sum(int(n) for n, _ in RE_N_PIEZAS.findall(t))
    return base + piezas * 400


def complejidad(t: str, texto_original: str) -> int:
    puntos = 0
    piezas = len(RE_FICHERO.findall(texto_original)) + sum(int(n) for n, _ in RE_N_PIEZAS.findall(t))
    puntos += min(30, piezas * 6)
    puntos += min(45, 15 * sum(1 for d in DOMINIOS_DIFICILES if d in t))
    if any(k in t for k in TODO_DE_UNA):
        puntos += 20
    if any(k in t for k in SALIDA_LARGA):
        puntos += 20
    if len(texto_original) > 2000:
        puntos += 10
    return min(100, puntos)


def estimar(modo: str, tier: str, esfuerzo: str, texto: str, contexto: list[str] | None = None,
            umbrales: dict[str, float] | None = None) -> dict[str, Any]:
    u = {**UMBRALES_DEFECTO, **(umbrales or {})}
    t = _norm(texto)
    tokens_entrada = tokens_por_palabras(texto) + sum(tokens_por_palabras(c) for c in (contexto or []))
    salida = salida_prevista(t)
    comp = complejidad(t, texto)
    tope = CONTEXTO.get(tier, (0, None))[1]
    limite_salida = SALIDA_LOCAL_BASE * u["factor_salida"]

    if tope and tokens_entrada > tope:
        veredicto, codigo = RECOMENDADO_NUBE, "contexto"
        motivo = f"No cabe el contexto: ~{tokens_entrada} tokens de entrada y el tier {tier} admite {tope}."
    elif salida > limite_salida:
        veredicto, codigo = RECOMENDADO_NUBE, "salida"
        motivo = (f"La respuesta pedida es demasiado larga para la CPU: ~{salida} tokens previstos "
                  f"(el máximo razonable en local es {int(limite_salida)}).")
    elif comp >= u["complejidad_nube"]:
        veredicto, codigo = RECOMENDADO_NUBE, "complejidad"
        motivo = f"Tarea muy compleja para un modelo local (complejidad {comp}/100)."
    elif comp >= u["complejidad_justo"]:
        veredicto, codigo = JUSTO, "complejidad"
        motivo = f"Es grande para el tier {tier} (complejidad {comp}/100)."
    else:
        veredicto, codigo, motivo = CABE_LOCAL, None, "Cabe en local."

    return {"veredicto": veredicto, "motivo": motivo, "motivo_codigo": codigo,
            "tokens_entrada": tokens_entrada, "salida_prevista": salida, "complejidad": comp}


# --- Troceo (fallback local, FR-052) -----------------------------------------------
def troceo_heuristico(texto: str) -> list[dict[str, Any]]:
    """Si el usuario ya enumeró partes, se usan; si no, fases genéricas de un proyecto de código."""
    lineas = [re.sub(r"^\s*(\d+[.)]|[-*•])\s*", "", l).strip() for l in texto.splitlines()]
    enumeradas = [l for l, orig in zip(lineas, texto.splitlines()) if l and re.match(r"^\s*(\d+[.)]|[-*•])\s", orig)]
    if len(enumeradas) >= 2:
        return [{"texto": l[:300], "estimacion_min": 30} for l in enumeradas[:10]]
    tema = texto.strip().splitlines()[0][:120] if texto.strip() else "la tarea"
    fases = [
        f"Definir requisitos, entradas/salidas y estructura de ficheros de: {tema}",
        "Crear el esqueleto del proyecto y el punto de entrada",
        "Implementar el módulo principal (el núcleo de la funcionalidad)",
        "Implementar los módulos secundarios, uno por petición",
        "Integrar las partes, compilar y probar",
        "Documentar el uso y pulir detalles",
    ]
    return [{"texto": f, "estimacion_min": m} for f, m in zip(fases, (20, 30, 60, 60, 45, 20))]


def sanear_pasos(datos: Any) -> list[dict[str, Any]]:
    """Acepta {"pasos":[...]} o una lista; cada paso str o dict. Devuelve 2–10 pasos válidos o []."""
    if isinstance(datos, dict):
        datos = datos.get("pasos") or datos.get("plan") or datos.get("steps") or []
    if not isinstance(datos, list):
        return []
    pasos = []
    for p in datos:
        if isinstance(p, str):
            texto, mins = p, 30
        elif isinstance(p, dict):
            texto = p.get("texto") or p.get("titulo") or p.get("paso") or p.get("descripcion") or ""
            mins = p.get("estimacion_min", 30)
        else:
            continue
        texto = str(texto).strip()
        if not texto:
            continue
        try:
            mins = max(5, min(600, int(mins)))
        except (TypeError, ValueError):
            mins = 30
        pasos.append({"texto": texto[:300], "estimacion_min": mins})
    return pasos[:10] if len(pasos) >= 2 else []
