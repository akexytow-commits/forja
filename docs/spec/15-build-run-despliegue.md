# 15 — Build, Ejecución y Despliegue (Windows)

Pensado para tu máquina (Windows, 8 GB RAM, ~29 GB libres). Objetivo: algo que arranque con doble clic y
que no te obligue a montar un entorno de desarrollo pesado.

## Stack final recomendado
- **Motor IA:** Ollama (instalador oficial de Windows).
- **Backend:** Python 3.11+, FastAPI + uvicorn. (Entorno virtual `.venv`.)
- **BBDD:** SQLite (incluido). Acceso con SQLAlchemy o `sqlite3`.
- **Credenciales:** `keyring` (usa Windows Credential Manager) para la clave de Nube.
- **Shell/UI:** `pywebview` (ventana nativa con WebView2, ya presente en Windows 10/11) sirviendo una SPA
  estática (HTML/CSS/JS; opcional Preact/Alpine ligero por CDN o empaquetado). (ADR-0002)
- **Empaquetado:** PyInstaller para generar un `.exe` que arranca backend + ventana. (Opcional en v1; en
  desarrollo puedes lanzar con un `.bat`.)

## Preparación (una vez)
1. **Instala Ollama** desde ollama.com (instalador Windows). Verifica: `ollama --version`.
2. **Descarga modelos** (confirma etiquetas vigentes en ollama.com; valores sugeridos en `04-...md`):
   ```
   ollama pull qwen3:4b
   ollama pull qwen2.5-coder:3b
   ollama pull qwen3:8b            REM opcional, va justo de RAM
   ollama pull qwen2.5-coder:7b    REM opcional
   ```
   > Con ~29 GB libres caben varios, pero descarga primero los Pequeños y prueba antes de bajar los Grandes.
3. **Libera disco si hace falta** (el Modo Tareas puede ayudarte a listar candidatos; tú decides).
4. **Para el tier Nube:** ten **Claude Code** instalado y con sesión iniciada (tu suscripción de Claude).
   FORJA lo detecta solo; si falta, el tier Nube queda deshabilitado y el núcleo local sigue funcionando.

## Estructura de carpetas del proyecto (a crear por Claude Code)
```
forja/
  backend/
    main.py            # FastAPI, monta API-0xx
    router.py          # MOD-010
    ollama_client.py   # MOD-011
    cloud_client.py    # MOD-012
    chat.py            # MOD-013 (streaming SSE)
    estimator.py       # MOD-050
    db.py              # MOD-060 (SQLite, migraciones)
    audit.py           # MOD-080
    modes/
      scripts.py       # MOD-020
      security.py      # MOD-030 (guardarraíles como código)
      tasks.py         # MOD-040
    prompts/
      scripts.txt  security.txt  tasks.txt
    plantillas/        # andamiajes de código
    migrations/        # 001_init.sql, ...
  ui/
    index.html  app.js  styles.css  strings.es.json
  data/
    forja.db           # se crea al primer arranque
  run.bat              # arranca backend + ventana
  requirements.txt
```

## Cómo se abre FORJA (FR-074)
FORJA es una **app de escritorio**: `pywebview` abre su **propia ventana** (usa WebView2, ya en Windows).
**No** se abre "desde una página web" ni necesita un navegador aparte: aunque la interfaz esté hecha con
tecnología web, corre dentro de la ventana de la app. En desarrollo se lanza con `run.bat`; empaquetada con
PyInstaller, se abre con **doble clic** en el `.exe` (o su acceso directo). El backend en localhost es
interno; el usuario nunca teclea una URL.

## Carpeta de datos
- `forja.db` y logs en la carpeta de datos del usuario (p. ej. `%APPDATA%\FORJA\`). No en Archivos de
  Programa (permisos). Configurable en Ajustes.

## Arranque (desarrollo)
`run.bat`:
```
@echo off
cd /d %~dp0
call .venv\Scripts\activate
python -m backend.main   REM arranca FastAPI en 127.0.0.1:8756 y abre la ventana pywebview
```
Secuencia interna (ST-060): backend arriba → comprueba Ollama (API-001) → si falta algo, SCR-008 →
si todo ok, abre el shell (SCR-001).

## Empaquetado a .exe (cuando quieras distribuirlo)
- PyInstaller con `--onefile` para el backend+pywebview, incluyendo `ui/` como datos.
- Ollama queda como dependencia externa (se instala aparte); la app detecta si falta y guía (SCR-008).

## Requisitos de red
- Núcleo: **ninguno**. Todo en loopback.
- Nube (opcional): usa **Claude Code** (tu suscripción de Claude), que ya corre en esta máquina. FORJA lo
  invoca en local (`claude -p ...`); la red la gestiona el propio Claude Code. Requiere tenerlo instalado y
  con sesión iniciada. Solo se usa cuando tú escalas. (ADR-0006)

## Notas de rendimiento para el build
- Forzar CPU en Ollama (no hay GPU utilizable).
- `num_ctx` conservador por tier (`04-...md`) para no agotar RAM.
- Cargar un solo modelo; precargar el Pequeño al arrancar para que el primer mensaje sea rápido.
- Cerrar otras apps pesadas al usar el tier Grande.
