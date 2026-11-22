# 07 — Contrato de la API local (backend)

El backend (FastAPI) escucha en `http://127.0.0.1:8756` (puerto configurable; solo loopback). La UI es su
único cliente. Todas las respuestas son JSON salvo el streaming (SSE). Errores con forma uniforme:
`{ "error": { "codigo": "STR", "mensaje": "..." } }`.

## Salud y sistema
### API-001 `GET /salud`
Devuelve estado del sistema para arranque/diagnóstico (SCR-008).
```json
{ "ollama": "ok|caido", "modelos_instalados": ["qwen3:4b","..."],
  "modelo_cargado": "qwen3:4b|null", "ram_libre_mb": 4200, "disco_libre_mb": 29000,
  "nube_activada": false }
```

## Chat / generación
### API-002 `POST /chat`
Inicia una generación. Cuerpo:
```json
{ "sesion_id": 12, "modo": "scripts", "tier": "pequeno", "esfuerzo": "medio",
  "texto": "escríbeme un script que...", "adjuntos": [] }
```
Respuesta: **stream SSE** (ver API-003). Antes de generar, el backend ejecuta MOD-050 (estimador); si el
veredicto obliga a decisión del usuario, el primer evento SSE puede ser `sugerencia_escalado` en vez de
tokens (la UI decide; ver SCR-006).

### API-003 Streaming SSE (eventos)
`Content-Type: text/event-stream`. Tipos de evento:
| evento | datos | significado |
|---|---|---|
| `inicio` | {modelo, tier, esfuerzo, requiere_carga} | empieza; si requiere_carga, UI muestra "cambiando de modelo" |
| `thinking` | {texto_parcial} | razonamiento en curso (si thinking activo); la UI puede plegarlo |
| `token` | {texto} | fragmento de respuesta |
| `herramienta` | {nombre, args, requiere_confirmacion} | el modelo quiere usar una tool (ver tool-calling) |
| `sugerencia_escalado` | {motivo, resumen_envio} | el estimador propone Nube (SCR-006) |
| `telemetria` | {fase, elapsed_ms, tokens_out, tok_s, eta_ms, modelo, tier} | tick cada ~400–600 ms para el indicador en vivo (FR-077/078, doc 22). `eta_ms` null = "estimando…" |
| `tope_razonamiento` | {tokens_thinking, limite, num_predict, restante, modelo_respuesta} | el tope de razonamiento (doc 04) cortó el thinking; la respuesta final la dará `modelo_respuesta` (el instruct) |
| `reclasificar` | {thinking} | red de seguridad B (doc 04): lo mostrado como respuesta era razonamiento (llegó un `</think>`); se mueve al panel de razonamiento |
| `fin` | {tokens_in, tokens_out, mensaje_id, gen_ms} | terminó |
| `error` | {codigo, mensaje} | fallo (p. ej. Ollama caído) |

### API-002b `POST /chat/confirmar-herramienta`
Para tool-calling con confirmación (Modo Scripts: guardar archivo; Modo Seguridad: cualquier acción activa
**siempre** requiere esto). Cuerpo `{ sesion_id, herramienta_id, aprobado: true|false }`.

## Estimador
### API-004 `POST /estimar`
Cuerpo `{ sesion_id, modo, tier, esfuerzo, texto }` → veredicto (ver `05-...md`). La UI lo usa para avisos
previos sin generar.

## Modelos
### API-010 `GET /modelos` → lista del registro (DB-007) con estado instalado.
### API-011 `POST /modelos/descargar` `{ alias }` → inicia `ollama pull`; progreso por SSE (API-003 reuso).
### API-012 `POST /modelos/cargar` `{ alias }` → fuerza carga (descargando el actual). Para pruebas/manual.

## Conversaciones / mensajes
### API-020 `GET /conversaciones?modo=...` → lista (DB-002).
### API-021 `POST /conversaciones` `{ modo, project_id?, engagement_id? }` → crea hilo.
### API-022 `GET /conversaciones/{id}/mensajes` → mensajes (DB-003).
### API-023 `DELETE /conversaciones/{id}` y `PATCH` (archivar, renombrar).

## Proyectos (Scripts)
### API-030 `GET/POST /proyectos`, `PATCH/DELETE /proyectos/{id}` (DB-004).
### API-031 `POST /proyectos/{id}/guardar-archivo` `{ nombre, contenido }` → escribe en la carpeta del
proyecto. **Requiere confirmación** si sobrescribe. Registra en auditoría si se desea.
### API-032 `POST /scripts/verificar` `{ lenguaje, codigo }` → verificador de código (doc 23).
Ejecuta el linter/compilador **estático** del lenguaje (**nunca ejecuta el código**). Respuesta:
`{ ok, herramienta, errores: [{linea, columna?, mensaje, severidad}] }`. Si la herramienta no está
instalada, `ok:false` con un mensaje claro y, si procede, oferta de instalar (ST-040).

## Tareas
### API-040 `GET /listas`, `POST /listas`.
### API-041 `GET /tareas?lista=...`, `POST /tareas` `{ texto }` (origen=usuario).
### API-042 `POST /tareas/organizar` `{ lista_id, esfuerzo }` → la IA ordena y asigna días; devuelve el
plan. (Usa MOD-040 → MOD-013 con el modelo general y esfuerzo medio/extra.)
### API-043 `PATCH /tareas/{id}` (mover de día, reordenar, cambiar estado), `DELETE`.

## Seguridad
### API-050 `GET/POST /engagements`, `PATCH /engagements/{id}` (incluye confirmar autorización → ST-030).
### API-051 `POST /engagements/{id}/analizar` `{ datos_recon }` → análisis (crea `findings` en estado
`idea`). **Nunca** lanza acciones; solo analiza el texto que tú aportas.
### API-052 `POST /findings/{id}` (actualizar: marcar validado_por_usuario, adjuntar evidencia).
### API-053 `POST /findings/{id}/informe` `{ enfoques:[...] }` → genera/une el borrador de informe (DB-006b.informe_md).
### API-054 Integraciones MCP externas (Burp/Caido/ZAP del usuario): **opcionales**, **solo lectura** o
con confirmación por acción (API-002b). Si no hay integración configurada, el modo funciona con pegar/importar.
### API-055 `GET /seguridad/plantillas-informe` (añadido en Rama 6)
Devuelve las plantillas de informe disponibles (HackerOne, Bugcrowd, breve y la **propia del usuario**)
para que Ajustes y el redactor de informes (SCR-022) las ofrezcan.

## Ajustes / auditoría / export
### API-060 `GET/PUT /ajustes` (DB-001). Activar Nube: `PUT /ajustes` con `nube.activada=1` + guardar clave
vía keyring (el backend nunca devuelve la clave en claro).
### API-061 `GET /auditoria` (DB-008, solo lectura).
### API-062 `POST /export` `{ tipo: "conversacion"|"informe", id }` → devuelve Markdown/archivo.

## Seguridad del transporte
- Solo `127.0.0.1`. Sin CORS a orígenes externos. Token de sesión local simple entre UI y backend para
  evitar que otra app del equipo hable con el backend (cabecera `X-Forja-Token` generada al arrancar).
