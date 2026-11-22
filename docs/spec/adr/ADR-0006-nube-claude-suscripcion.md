# ADR-0006 — El tier Nube usa tu suscripción de Claude (vía Claude Code)

**Estado:** aceptada · **Fecha:** 2026-11-21 · **Sustituye** la parte "proveedor externo genérico" de ADR-0001/04.

## Contexto
El tier **Nube** es para tareas que no caben en local (p. ej. un firmware completo). El usuario ya paga una
suscripción de **Claude** y la usa a través de **Claude Code** en esta misma máquina. Quiere que la Nube de
FORJA use esa suscripción, no una API de pago aparte.

## Decisión
El **backend del tier Nube (MOD-012)** invoca **Claude Code en modo headless** (p. ej.
`claude -p "<prompt>" --output-format stream-json`) como subproceso local. Claude Code ya está autenticado
con la suscripción del usuario, así que FORJA no necesita ninguna clave de API ni facturación por tokens:
reutiliza la sesión que el usuario ya tiene.

- `settings.nube.backend = "claude_code"` (por defecto, elegido por el usuario).
- `settings.nube.claude_bin` = ruta al ejecutable `claude` (autodetectada; editable).
- `settings.nube.modelo` = modelo a pedir (p. ej. el Opus/Sonnet que tu plan permita).
- **No se guarda ninguna clave** en este modo (no hace falta). La referencia `nube.api_key_ref` solo existe
  para el backend alternativo.
- Se mantiene un **backend alternativo** `settings.nube.backend = "api"` (cliente HTTP a una API compatible
  OpenAI/Anthropic con clave propia), para quien prefiera pago por uso. Documentado pero no por defecto.

## Consecuencias
- **+** Sin claves ni facturación extra: la Nube "sale gratis" dentro de lo que ya pagas.
- **+** Encaja con lo que ya tienes instalado (Claude Code en esta máquina).
- **⚠ Comparte tu límite de uso de Claude.** Cada tarea que escales a Nube consume de tu plan, igual que si
  la escribieras tú en Claude Code. Por eso el tier Nube se reserva para lo "extra de verdad" (el estimador
  MOD-050 ya lo propone solo cuando hace falta). El aviso de escalado (SCR-006) debe recordarlo.
- **⚠ Dependencia de Claude Code.** Si no está instalado o no hay sesión iniciada, el tier Nube se deshabilita
  y la app guía al usuario (igual que hace con Ollama; ver SCR-008). El núcleo local sigue funcionando sin él.
- **−** Depende del formato/flags de Claude Code headless; MOD-012 aísla esa llamada para poder adaptarla.

## Requisitos afectados
FR-006 (Nube opt-in), FR-051 (propuesta de escalado), NFR-010 (privacidad: avisar qué se envía al escalar),
ST-050 (máquina de escalado), DB-001 (claves `nube.*`), DB-008 (auditar cada escalado).
