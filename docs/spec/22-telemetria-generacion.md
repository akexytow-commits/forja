# 22 — Telemetría de generación (indicador estilo Claude Code)

Copia, por ingeniería inversa del **comportamiento**, el indicador de estado que muestra Claude Code
mientras trabaja: **cuánto lleva pensando, cuánto puede tardar (aprox.), cuántos tokens lleva y a qué
velocidad**. En tu equipo (CPU, respuestas de ~1 min) esto no es un lujo: te dice que la app está viva y
cuánto falta.

## Qué se copia (mecanismo a replicar)
1. **Tiempo transcurrido en vivo** desde que empieza la generación (contador que corre).
2. **Fase actual:** *pensando* vs *respondiendo*. Los modelos Qwen3 tienen "thinking", así que separamos el
   tiempo de razonamiento del de la respuesta (como el "pensando…" de Claude Code).
3. **Tokens generados** y **velocidad** (tokens/segundo).
4. **ETA aproximada:** una estimación de **cuánto puede tardar en total / cuánto queda**, a partir de la
   velocidad actual y de la **salida estimada** (reutiliza el estimador MOD-050).
5. **Pista de interrumpir** (botón "Detener"), como el "esc to interrupt".
6. **Ver / plegar el razonamiento** (el bloque de thinking), para enseñarlo u ocultarlo.

## Cómo se implementa
### Backend (MOD-013, sobre el streaming SSE de API-003)
Durante la generación, además de los `token`/`thinking`, emite un evento ligero **`telemetria`** cada
~400–600 ms:
```json
{ "fase": "pensando|respondiendo", "elapsed_ms": 23000, "tokens_out": 180,
  "tok_s": 7.4, "eta_ms": 41000, "modelo": "qwen3:4b", "tier": "pequeno" }
```
- `elapsed_ms`: ahora − inicio.
- `tok_s`: media móvil de los últimos ~2 s (no el total, para que reaccione).
- `eta_ms`: `max(0, (salida_estimada_tokens − tokens_out) / tok_s) · 1000`. Si `tok_s` aún no es estable,
  manda `null` (la UI muestra "estimando…"). `salida_estimada_tokens` sale del plan de modelo / MOD-050.
- `fase`: *pensando* mientras llegan tokens de thinking; *respondiendo* cuando llega la respuesta.

### UI (línea de estado junto al compositor, SCR-001/SCR-002)
Una línea discreta mientras genera, al estilo:
> `⏱ 23s · pensando… · 180 tok · 7 tok/s · ~41s restantes · [Detener]`
- Al pasar a *respondiendo*, cambia la etiqueta de fase.
- Cuando `eta_ms` es `null`: "~estimando…".
- Al terminar (`fin`), muestra un resumen breve: tiempo total y tokens (y se puede guardar en el mensaje).
- **Ver/plegar razonamiento** (BTN-100): muestra u oculta el bloque de thinking.

## Datos
- Reutiliza `messages.tokens_in/tokens_out` (DB-003). Opcional: añadir `messages.gen_ms` (duración) para
  histórico y para afinar futuras ETAs.

## Requisitos y pruebas
- **FR-077** Telemetría en vivo: tiempo, tokens y tok/s durante la generación. → SSE `telemetria`, SCR-001
- **FR-078** ETA aproximada de la respuesta, basada en velocidad + salida estimada; "estimando…" si aún no
  es fiable. → MOD-013 + MOD-050
- **FR-079** Separar y mostrar el **tiempo de "pensando"** del de respuesta; ver/plegar el razonamiento. →
  BTN-100
- Pruebas: **TST-077** (telemetría actualiza en vivo), **TST-078** (ETA aparece y se afina, nunca negativa),
  **TST-079** (fase pensando/respondiendo y plegado del razonamiento).

## Honestidad de la ETA
La ETA es **aproximada**: en CPU la velocidad es bastante estable, así que una estimación por throughput es
razonable, pero puede variar si cambian el contexto o la carga del equipo. Preséntala siempre como "~" y
nunca como una cuenta atrás exacta.

## Orden de construcción
Mejora de MOD-013; se construye en la **Rama 5** (pulido) junto a proyectos/plantillas/export/ajustes.
