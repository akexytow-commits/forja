# 04 — Capa de Modelos y Router (MOD-010)

El corazón de FORJA. Convierte tus **dos selectores** (modo + modelo/esfuerzo) en una llamada concreta.

## Conceptos
- **Tier** (lo elige el selector inferior, eje 1): `pequeno` | `grande` | `nube`.
- **Esfuerzo** (selector inferior, eje 2): `bajo` | `medio` | `extra`.
- **Modo** (selector superior): `scripts` | `seguridad` | `tareas`.

El router combina los tres para decidir: **qué modelo**, **qué prompt de sistema**, **qué parámetros**
(temperatura, num_ctx, thinking/reasoning), y **qué herramientas** habilitar.

## Registro de modelos (model registry)
Tabla **DB-007 `models`**, precargada con un catálogo por defecto. Valores **a verificar en
ollama.com al construir** (las etiquetas cambian). Recomendación para TU hardware:

| alias FORJA | tier | etiqueta Ollama sugerida | tamaño Q4 | thinking | uso |
|---|---|---|---|---|---|
| `pequeno-general` | pequeno | `qwen3:4b-instruct-2507` | ~2.6 GB | **no (instruct)** | chat, Tareas, **Seguridad medio** |
| `pequeno-razonador` | pequeno | `qwen3:4b-thinking-2507` | ~2.6 GB | **sí (solo razona)** | **Seguridad extra** (fase de razonar) |
| `pequeno-codigo` | pequeno | `qwen2.5-coder:3b` | ~2.0 GB | no | autocompletar/snippets rápidos |
| `grande-general` | grande | `qwen3:8b` | ~5.0 GB | sí | respuestas de más calidad |
| `grande-codigo` | grande | `qwen2.5-coder:7b` | ~4.7 GB | no | scripts/firmware de más enjundia |
| `nube-frontera` | nube | **tu suscripción de Claude vía Claude Code** | — | n/a | tareas enormes (firmware completo) |

> Alternativas de respaldo si 8B va demasiado justo de RAM: `llama3.2:3b`, `phi4-mini`, `gemma3:4b`
> (o la familia Gemma que esté disponible). El registro es editable en Ajustes (SCR-007).

## Backend del tier Nube (ADR-0006)
El tier **Nube no usa Ollama ni una API de pago**: usa **tu suscripción de Claude a través de Claude Code**.
MOD-012 invoca Claude Code en modo headless como subproceso local:
```
claude -p "<prompt construido por FORJA>" --output-format stream-json
```
Claude Code ya está autenticado con tu suscripción, así que **no hace falta clave de API** y no hay
facturación por tokens aparte.
- **Comparte tu límite de uso de Claude:** cada escalado a Nube consume de tu plan. Por eso la Nube se
  reserva para lo "extra de verdad" y el estimador (MOD-050) solo la propone cuando hace falta. El aviso de
  escalado (SCR-006) debe recordar esto antes de enviar.
- **Si Claude Code no está instalado o sin sesión:** el tier Nube se deshabilita y la app guía (como con
  Ollama, SCR-008). El núcleo local sigue funcionando igual.
- **Alternativa opcional** (`settings.nube.backend="api"`): cliente HTTP a una API compatible con clave
  propia, para quien prefiera pago por uso. No es el modo por defecto.
- El streaming de Claude Code se re-emite por los mismos eventos SSE (API-003) para que la UI lo pinte igual
  que el local.

## Tabla de resolución del router (determinista)
El router aplica esta tabla. Es **la** regla; nada de magia oculta (ADR-0004).

### Paso 1 — elegir familia de modelo por (modo, tier)
| modo | pequeno | grande | nube |
|---|---|---|---|
| scripts | `pequeno-codigo` | `grande-codigo` | `nube-frontera` |
| seguridad | ver override ↓ | ver override ↓ | `nube-frontera` |
| tareas | `pequeno-general` | `grande-general` | `nube-frontera` |

> **Override de Seguridad por esfuerzo (CPU + thinking).** Para que pedir un comando no se quede pensando
> sin responder:
> - **Seguridad + esfuerzo bajo** → modelo de **código** (`pequeno-codigo`/`grande-codigo`, sin thinking),
>   `num_predict = 768`. Comandos/snippets directos (ffuf, nmap…): rápido y fiable.
> - **Seguridad + esfuerzo medio** → `pequeno-general` = **instruct-2507** (sin razonamiento, no es un flag:
>   es otro modelo), `num_predict = 1536`. Análisis directo, rápido (~1–2 min) y fiable.
> - **Seguridad + esfuerzo extra** → `pequeno-razonador` = **thinking-2507** para la fase de razonar,
>   `num_predict = 3072`, **con tope de razonamiento**: al saltar, la respuesta final la da el **instruct**
>   (ver abajo). Análisis profundo, siempre responde.
>
> Resultado: bajo = comando ágil; medio = análisis rápido sin pensar; extra = análisis profundo acotado.
> Motivo: en CPU, el "medium thinking" de qwen3:4b tarda ~8 min y a menudo agota el presupuesto pensando
> sin responder; por eso medio va sin thinking y el thinking se reserva a extra con red de seguridad.

## Tope de razonamiento (reasoning cap) — red de seguridad para modelos thinking
Mecanismo reutilizable de MOD-013 para que un modelo con thinking **nunca** se quede sin responder:
- Durante la generación se cuentan los tokens de **thinking**. Si llegan a ~**60 %** de `num_predict` sin
  que haya empezado la respuesta, se **corta el razonamiento** y se hace una segunda llamada **con el modelo
  instruct** (`qwen3:4b-instruct-2507`), pasándole lo ya pensado como contexto, para obtener la respuesta
  final. (No vale re-llamar al modelo thinking: volvería a razonar; por eso la respuesta forzada la da el
  instruct.)
- **Red de seguridad (B):** si aun así algún texto llega con `…</think>` mezclado, se trata como
  razonamiento y no se muestra como respuesta en el chat.
- Garantiza respuesta y **acota el tiempo** (peor caso ~8 min en extra). Cubre la variabilidad de qwen3
  (que razona más o menos de una vez a otra).
- Se aplica siempre que se use un modelo thinking (hoy, Seguridad extra). Pruebas: TST-032b (el tope
  dispara y produce respuesta).

### Paso 2 — parámetros por esfuerzo
Para modelos **con thinking** (familia Qwen3):
| esfuerzo | enable_thinking | reasoning_effort | temperatura | num_predict (máx salida) |
|---|---|---|---|---|
| bajo | false (+ `/no_think`) | — | 0.3 | 768 |
| medio | true | medium | 0.5 | 2048 |
| extra | true | high | 0.7 | 3072 |

> **Importante — las variantes de Qwen3 4B NO son híbridas.** En este equipo, `qwen3:4b` es
> **Thinking-2507**: solo sabe razonar, su plantilla siempre abre `<think>`, y `/no_think` / `think:false`
> **no lo desactivan** (con `think:false` el razonamiento se mezcla con la respuesta). Por eso, para una
> respuesta **sin razonar** no se usa un flag: se usa **otro modelo**, el **instruct** (`pequeno-general` =
> `qwen3:4b-instruct-2507`). El modelo que razona (`pequeno-razonador`) se reserva a esfuerzo extra.
> `num_predict` debe presupuestar **pensamiento + respuesta** juntos cuando sí se razona; un valor bajo hace
> que agote el presupuesto pensando y no responda.
>
> **Etiquetas reales (verificado en el equipo):** `qwen3:4b-instruct-2507` y `qwen3:4b-thinking-2507` **no
> existen tal cual** en Ollama; las reales llevan **sufijo de cuantización** (p. ej. `...-q4_K_M`). Usa la
> etiqueta exacta instalada. El thinking-2507 suele ser **el mismo archivo** que tu `qwen3:4b`.
>
> **Efecto colateral (correcto):** como Chat y Tareas del tier pequeño comparten `pequeno-general`, ahora
> usan el **instruct**; en esfuerzo extra **ya no razonan de verdad**, el razonamiento se **simula con
> instrucciones en el prompt** (como con los modelos de código). El `pequeno-razonador` se usa solo en
> Seguridad extra.
>
> **Rendimiento real medido:** medio (instruct) ~5 min y análisis algo flojo (puede no nombrar la clase de
> vulnerabilidad); extra ~18 min y análisis correcto. Mejora recomendada: en el prompt de Seguridad-medio,
> exigir **nombrar la clase de vulnerabilidad primero** y luego explicar.

Para modelos **sin thinking** (coder 3B/7B), el esfuerzo se emula:
| esfuerzo | estrategia | temperatura | num_predict |
|---|---|---|---|
| bajo | respuesta directa | 0.2 | 512 |
| medio | "piensa paso a paso brevemente antes de responder" (en el prompt) | 0.4 | 1024 |
| extra | "razona en un bloque `<plan>` antes del código; luego el código" | 0.6 | 2048 |

### Paso 3 — contexto por tier (presupuesto de RAM, ver `01-...md`)
| tier | num_ctx por defecto | tope |
|---|---|---|
| pequeno | 8192 | 16384 |
| grande | 4096 | 8192 |
| nube | 32768 | según proveedor |

> El tier `grande` usa **menos** contexto que `pequeno` a propósito: el modelo ya ocupa más RAM, así que
> recortamos KV cache para no quedarnos sin memoria. El estimador (MOD-050) puede recomendar Nube si la
> entrada no cabe en estos topes.

## Contrato interno del router
```
resolver(modo, tier, esfuerzo, longitud_entrada_tokens) -> PlanDeModelo
PlanDeModelo = {
  alias, etiqueta_ollama | proveedor_nube,
  system_prompt (según modo, ver 09/10/11),
  params { temperatura, num_ctx, num_predict, enable_thinking?, reasoning_effort? },
  herramientas [...],        # p. ej. en scripts: guardar_archivo; en seguridad: ninguna activa
  requiere_carga: bool       # true si hay que cambiar de modelo en Ollama
}
```

## Reglas de carga/descarga (MOD-011)
- **Invariante:** solo un modelo local cargado. Antes de cargar B, se descarga A
  (`keep_alive: 0` sobre A, o confiar en la expulsión por memoria de Ollama; preferimos explícito).
- Al cambiar de tier/modo que implique otro modelo: mostrar en UI "Cambiando de modelo… (puede tardar)".
- Si falta el modelo en Ollama: MOD-011 ofrece **descargarlo** (`ollama pull`) con barra de progreso
  (SCR-008). Avisar del tamaño en disco antes.
- Si Ollama no responde en `localhost:11434`: estado de error guiado (NFR-020).

## Prompts de sistema por modo
Viven en el backend en `prompts/` y se referencian por modo. Los detalles de cada uno están en:
- Scripts/Firmware → `09-modo-scripts-firmware.md` (§ Prompt)
- Seguridad → `10-modo-seguridad-bugbounty.md` (§ Prompt + Guardarraíles)
- Tareas → `11-modo-tareas-organizador.md` (§ Prompt)

El prompt de sistema **siempre** incluye: idioma español, que corre en local y con qué modelo/tier, y las
reglas del modo. En Seguridad incluye además los guardarraíles (que también se aplican como código).

Todos los prompts de los modelos **locales** siguen la **Política de Restricciones** (`21-...md`): tono de
experto autorizado, directo y sin moralinas, con **mínima fricción en lo legítimo** y solo los límites
mínimos (gate de alcance, no malware para dañar, no fuera de alcance). El tier Nube conserva la seguridad
propia de Anthropic.
