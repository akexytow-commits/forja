# 23 — Verificador de código (MOD-110)

Resuelve tu preocupación ("muchos errores de código") **sin una segunda IA**: en vez de otro modelo, FORJA
pasa el código generado por las **herramientas reales** del lenguaje, que detectan errores de forma
**determinista, instantánea y sin gastar RAM** — y sin inventarse nada.

## Qué hace
- Un botón **"Comprobar"** (BTN-101) en cada bloque de código del Modo Scripts (SCR-010). Ejecuta el
  linter/compilador del lenguaje y muestra los errores con **línea y mensaje**.
- Si hay errores, aparece **"Corregir con la IA"** (BTN-102, opcional): devuelve el código + los errores al
  modelo para una pasada de corrección (lenta en CPU, por eso es opt-in).

## Regla de seguridad (importante)
El verificador hace **solo análisis estático / de sintaxis**: **NUNCA ejecuta el código**. Comprobar un
script no lo corre. (py_compile compila sin ejecutar; `bash -n` y `node --check` solo parsean; shellcheck y
el parser de PowerShell son estáticos.) Esto evita correr código generado sin querer.

## Herramientas por lenguaje (con degradación elegante)
| Lenguaje | Herramienta (estática) | Disponibilidad en tu equipo |
|---|---|---|
| Python | `python -m py_compile` (+ `ruff` si está) | **siempre** (Python ya está) |
| PowerShell | parser de PowerShell (+ PSScriptAnalyzer si está) | **sí** (Windows) |
| Bash | `bash -n` (+ `shellcheck` si está) | necesita WSL o Git-Bash |
| JS | `node --check` | necesita Node |

- El lenguaje se **detecta** del propio bloque (la etiqueta del fence, p. ej. ```python```).
- Si la herramienta no está instalada, el botón lo dice con claridad ("verificador de Bash no disponible:
  requiere WSL/Git-Bash") y ofrece instalarla con confirmación (ST-040), o se omite. Python y PowerShell
  cubren lo más habitual sin instalar nada.

## Honestidad sobre lo que pilla
Detecta **errores de sintaxis y fallos evidentes** (variables no cerradas, indentación, llamadas mal
formadas). **No** detecta bugs de lógica — esos se cazan probando. Aun así, elimina la mayoría de los
errores "tontos" que meten los modelos pequeños, que es justo lo que te molestaba.

## Contrato
- Endpoint **API-032** `POST /scripts/verificar` `{lenguaje, codigo}` →
  `{ ok: bool, herramienta: str, errores: [{linea, columna?, mensaje, severidad}] }`.
- "Corregir con la IA" reusa el Motor de Chat (MOD-013): manda `codigo + errores` con un prompt de
  corrección y devuelve el nuevo bloque (que puedes volver a Comprobar).

## Requisitos y pruebas
- **FR-080** Verificador: botón "Comprobar" que ejecuta el linter/compilador real (estático, sin ejecutar)
  y muestra errores con línea; detecta el lenguaje; degrada si falta la herramienta. → BTN-101, API-032
- **FR-081** "Corregir con la IA" (opcional): pasa código + errores al modelo para una corrección. → BTN-102
- Pruebas: **TST-080** (detecta un error de sintaxis Python con su línea), **TST-081** (NO ejecuta el
  código: un `print`/efecto no ocurre al comprobar), **TST-082** (corregir devuelve una versión nueva).

## Orden de construcción
**Rama 6b**, antes del empaquetado (Rama 7). Encaja en el Modo Scripts; no toca Seguridad ni sus guardarraíles.
