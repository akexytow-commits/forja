"""Configuración global de FORJA (rutas, puertos, constantes)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "FORJA"
HOST = "127.0.0.1"
PORT = int(os.environ.get("FORJA_PORT", "8756"))
OLLAMA_URL = os.environ.get("FORJA_OLLAMA_URL", "http://127.0.0.1:11434")

# Cuánto mantiene Ollama el modelo en RAM tras usarlo. Un solo modelo a la vez (FR-005).
KEEP_ALIVE = os.environ.get("FORJA_KEEP_ALIVE", "30m")
# El modelo de embeddings (nomic-embed-text, ~0,3 GB) se queda más: la primera búsqueda en frío paga su carga.
KEEP_ALIVE_EMBED = os.environ.get("FORJA_KEEP_ALIVE_EMBED", "4h")
# num_ctx por defecto del chat local (= router.CONTEXTO["pequeno"][0]). Ollama RECARGA el modelo si una petición
# pide otro num_ctx que el de la carga: la precarga y los modos usan este para no pagar ~6 s por recarga.
NUM_CTX_DEFECTO = 8192
# Hilos de CPU para Ollama. Por defecto Ollama usa los núcleos FÍSICOS (4 en el Ryzen 3 5425U); medido en este
# portátil, con los 8 LÓGICOS la evaluación del prompt va +30–50 % (38→50 tok/s con 500 tokens, 28→42 con ~3000)
# y la generación queda igual (~8,5 tok/s). Debe ser el mismo en todas las peticiones: si cambia, Ollama recarga.
NUM_THREAD = int(os.environ.get("FORJA_NUM_THREAD", "0") or 0) or (os.cpu_count() or 4)

# Rama 7: empaquetado con PyInstaller (--onefile), los recursos (ui/, prompts, migraciones, plantillas) van
# dentro del .exe y se extraen en sys._MEIPASS al arrancar; los datos del usuario siguen en %APPDATA%\FORJA.
CONGELADO = bool(getattr(sys, "frozen", False))
ROOT_DIR = Path(getattr(sys, "_MEIPASS", "")) if CONGELADO else Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
ASSETS_DIR = ROOT_DIR / "assets"
UI_DIR = ROOT_DIR / "ui"
PROMPTS_DIR = BACKEND_DIR / "prompts"
MIGRATIONS_DIR = BACKEND_DIR / "migrations"

TOKEN_HEADER = "X-Forja-Token"


def data_dir() -> Path:
    """Carpeta de datos del usuario: %APPDATA%\\FORJA (o FORJA_DATA_DIR)."""
    override = os.environ.get("FORJA_DATA_DIR")
    base = Path(override) if override else Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base
