# 03 — Arquitectura

## Vista de contexto (quién habla con quién)
```
┌─────────────────────────────────────────────────────────────┐
│  Tu portátil (Windows, offline por defecto)                   │
│                                                               │
│   ┌───────────────┐      HTTP/SSE      ┌──────────────────┐   │
│   │  UI (WebView) │◄──────────────────►│  Backend FastAPI │   │
│   │  pywebview    │  localhost:8756    │  (sidecar Python)│   │
│   └───────────────┘                    └───────┬──────────┘   │
│                                                 │             │
│                         ┌───────────────────────┼───────────┐ │
│                         │                        │           │ │
│                   ┌─────▼─────┐           ┌──────▼──────┐    │ │
│                   │  Ollama   │           │   SQLite    │    │ │
│                   │ :11434    │           │ forja.db    │    │ │
│                   │ (modelos) │           └─────────────┘    │ │
│                   └───────────┘                              │ │
│                         ▲ un modelo cargado a la vez         │ │
│                         │                                    │ │
│   ┌─────────────────────┴──────────────── (opcional) ──────┐ │ │
│   │  Nube: Claude Code (tu suscripción, solo si la activas) │ │ │
│   └─────────────────────────────────────────────────────── ┘ │ │
└─────────────────────────────────────────────────────────────┘
```

- La **UI** es HTML/CSS/JS servido por el backend y mostrado en una ventana nativa (pywebview). No hay
  navegador aparte.
- El **backend** es el cerebro de orquestación: router, estimador, persistencia, modos. Es el único que
  habla con Ollama, con SQLite y (opcional) con la Nube.
- **Ollama** sirve los modelos locales con API compatible OpenAI (`/v1/chat/completions`) y gestiona la
  carga/descarga de modelos.
- **SQLite** es un único fichero `forja.db` en la carpeta de datos de la app.

## Vista de contenedores
| Contenedor | Tecnología | Responsabilidad | Ref |
|---|---|---|---|
| Shell/UI | pywebview + HTML/CSS/JS (vanilla o Preact/Alpine ligero) | Render de pantallas, selectores, streaming visual | ADR-0002, `08-...md` |
| Backend | Python 3.11+ + FastAPI + uvicorn | Orquestación, API local, lógica de modos | `07-...md` |
| Motor de modelos | Ollama (local) | Inferencia local de modelos | ADR-0001 |
| Persistencia | SQLite (vía SQLAlchemy o sqlite3) | Guardar todo localmente | `06-...md` |
| Nube (opcional) | **Claude Code headless (tu suscripción de Claude)** | Tier "extra/grande" | ADR-0006, MOD-012 |

## Vista de componentes (los módulos — las "cajitas")
Fuente de verdad: `catalogo/modulos.yaml`. Resumen:

- **MOD-001 App Shell** — arranque, ventana, salud del sistema, enrutado de pantallas.
- **MOD-010 Router de Modelos** — (modo, tier, esfuerzo) → modelo+params. Núcleo.
- **MOD-011 Gestor de Ollama** — comprueba que Ollama vive, lista/descarga modelos, carga/descarga,
  controla `keep_alive` (un modelo a la vez).
- **MOD-012 Cliente Nube** — solo si está activada; envía al proveedor externo.
- **MOD-013 Motor de Chat** — bucle de conversación, streaming SSE, herramientas (tool-calling).
- **MOD-020 Modo Scripts/Firmware** — perfil + herramientas de código + proyectos.
- **MOD-030 Modo Seguridad** — perfil + alcance + análisis + informes + guardarraíles.
- **MOD-040 Modo Tareas** — captura + planificación + plan por días.
- **MOD-050 Estimador de Escalado** — tamaño de tarea y veredicto local/nube.
- **MOD-060 Persistencia** — acceso a SQLite, migraciones.
- **MOD-070 Ajustes** — configuración, activación de Nube, tema, rutas.
- **MOD-080 Auditoría** — registro de acciones sensibles.

Dependencias clave (flechas): el **mapa interactivo** las dibuja. En texto:
`MOD-001 → {MOD-013, MOD-070}`; `MOD-013 → {MOD-010, MOD-050, MOD-060}`;
`MOD-010 → {MOD-011, MOD-012}`; `MOD-020/030/040 → MOD-013`; `MOD-030 → MOD-080`.

## Flujo de una petición (camino feliz, local)
1. Usuario escribe en el compositor (SCR-001) en, p. ej., Modo Scripts, tier Pequeño, esfuerzo medio.
2. UI → `POST /chat` (API-002) con {modo, tier, esfuerzo, texto, sesion_id}.
3. **MOD-050** estima tamaño → "cabe en local".
4. **MOD-010** resuelve modelo+params (p. ej. `qwen3:4b`, num_ctx=8192, thinking=medio).
5. **MOD-011** asegura que ese modelo está cargado (descarga el anterior si hace falta).
6. **MOD-013** llama a Ollama `/v1/chat/completions` con `stream=true`.
7. Tokens vuelven por **SSE** (API-003) a la UI, que los pinta en vivo.
8. **MOD-060** guarda mensajes en SQLite (DB-002/003).

## Flujo de escalado a Nube
Ver `05-...md` y SCR-006. Resumen: si el estimador dice "recomendado Nube" y la Nube está activa, el
backend devuelve un `evento: sugerencia_escalado`; la UI muestra el aviso; si el usuario acepta, se repite
la petición por MOD-012; se registra en auditoría (DB-008).

## Por qué esta arquitectura (resumen de ADRs)
- **ADR-0001** Ollama como motor: instalación trivial en Windows, API OpenAI, gestión de modelos y
  carga/descarga automática. Alternativa (llama.cpp directo) queda para optimización futura.
- **ADR-0002** pywebview+FastAPI en vez de Tauri/Electron: mínimo consumo y sin toolchain pesado, acorde
  al hardware. El backend desacoplado permite migrar el shell sin tocar lógica.
- **ADR-0003** SQLite: cero servidores, un fichero, perfecto para local monousuario.
- **ADR-0004** Router por tabla determinista (no heurística oculta): reproducible y testeable.
- **ADR-0005** Guardarraíles de seguridad como código y máquina de estados, no como texto de prompt.
