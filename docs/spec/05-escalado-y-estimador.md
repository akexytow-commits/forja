# 05 — Estimador de Escalado a Nube (MOD-050)

Implementa tu idea: "si el proyecto es demasiado grande para el local, que la propia IA me lo diga y me
proponga la nube". No es magia: es un cálculo explícito y transparente.

## Qué estima
Dada una petición, calcula tres señales y emite un **veredicto**:

1. **Tokens de entrada previstos** = tokens del contexto + mensaje actual (aprox. palabras × 1.3).
2. **Longitud de salida pedida** = heurística por palabras clave e intención
   (p. ej. "firmware completo", "proyecto entero", "todas las funciones", "genérame el código entero de"
   → salida muy larga; "explícame", "corrige esta línea" → corta).
3. **Complejidad** = puntuación 0–100 por señales: nº de ficheros/módulos mencionados, dominios
   difíciles (firmware, drivers, criptografía, parsers binarios), petición de "todo de una vez".

## Veredicto
```
si tokens_entrada > tope_num_ctx(tier_actual)  → RECOMENDADO_NUBE (motivo: no cabe el contexto)
si salida_prevista > num_predict(extra) * 2     → RECOMENDADO_NUBE (motivo: salida demasiado larga)
si complejidad >= 70                            → RECOMENDADO_NUBE (motivo: tarea compleja)
si complejidad entre 45 y 69                     → JUSTO (sugerir subir a 'grande' o trocear)
resto                                            → CABE_LOCAL
```
Umbrales en Ajustes (SCR-007), para que los calibres con el uso.

## Qué hace la app con el veredicto
- **CABE_LOCAL:** procede normal.
- **JUSTO:** antes de generar, muestra una nota no bloqueante: "Esto es grande para el tier actual.
  ¿Subir a Grande o trocear la tarea?" (botones BTN-026 Subir / BTN-027 Trocear / seguir).
- **RECOMENDADO_NUBE:**
  - Si Nube **activada**: muestra SCR-006 con el motivo, qué se enviaría (resumen) y botones
    BTN-028 "Escalar a Nube" / BTN-029 "Hacerlo en local igualmente (troceado)". El usuario decide.
  - Si Nube **desactivada**: explica por qué convendría, cómo activarla (enlace a Ajustes), y ofrece la
    vía local troceada.

## Trocear (fallback local)
Cuando una tarea no cabe pero el usuario quiere quedarse en local, MOD-050 propone un **plan de troceo**:
dividir en sub-tareas secuenciales (p. ej. firmware → por módulos/ficheros), ejecutarlas una a una y
ensamblar. Este plan se puede **mandar al Modo Tareas** como un plan por pasos (integración MOD-050→MOD-040).

## Mensaje tipo (ejemplo de copy, editable en personalización)
> "Lo que pides (un firmware completo de Flipper Zero) es demasiado grande para ejecutarlo bien en este
> portátil: no cabría el contexto ni daría tiempo a una salida tan larga en CPU. Opciones:
> **1)** Escalar a la Nube para hacerlo de una vez. **2)** Quedarnos en local y trocearlo por módulos
> (te preparo un plan de pasos en el Organizador de Tareas). ¿Qué prefieres?"

## Nota para Claude Code (rama de ingeniería sugerida por la propia app)
Cuando el estimador marca RECOMENDADO_NUBE de forma recurrente para un tipo de tarea, la app puede sugerir
al usuario "esto merece una rama propia en tu proyecto" y crear una entrada en el Organizador de Tareas
con el alcance de esa rama. Es la materialización de tu idea de "otra rama que deberías hacer".

## Interfaz y datos
- Endpoint: `POST /estimar` (API-004) → devuelve {veredicto, motivo, tokens_entrada, salida_prevista,
  complejidad, plan_troceo?}.
- Se registra cada escalado aceptado en auditoría (DB-008) con qué se envió a la Nube (resumen, no el
  contenido íntegro, salvo que el usuario lo pida).
