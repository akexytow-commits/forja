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
| `pequeno-general` | pequeno | `qwen3:4b` | ~2.6 GB | sí (conmutable) | chat, tareas, scripts cortos |
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
| seguridad | `pequeno-general` | `grande-general` | `nube-frontera` |
| tareas | `pequeno-general` | `grande-general` | `nube-frontera` |

### Paso 2 — parámetros por esfuerzo
Para modelos **con thinking** (familia Qwen3):
| esfuerzo | enable_thinking | reasoning_effort | temperatura | num_predict (máx salida) |
|---|---|---|---|---|
| bajo | false | — | 0.3 | 512 |
| medio | true | medium | 0.5 | 1024 |
| extra | true | high | 0.7 | 2048 |

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
