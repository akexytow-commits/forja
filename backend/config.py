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
