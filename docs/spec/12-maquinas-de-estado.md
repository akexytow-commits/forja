# 12 — Máquinas de Estado

Comportamientos críticos modelados como FSM para que el builder los implemente sin ambigüedad.

## ST-010 — Sesión de generación (chat)
Estados: `inactivo → estimando → (esperando_decision_escalado?) → cargando_modelo? → generando →
(esperando_confirmacion_herramienta?) → completado | error | cancelado`.
Transiciones:
- `inactivo —[enviar]→ estimando` (MOD-050).
- `estimando —[CABE_LOCAL]→ cargando_modelo` (si requiere_carga) `→ generando`.
- `estimando —[RECOMENDADO_NUBE]→ esperando_decision_escalado` (SCR-006).
  - `—[usuario: escalar]→ generando (nube)`  `—[usuario: local]→ generando (troceado)`.
- `generando —[modelo pide tool]→ esperando_confirmacion_herramienta` (solo si la tool lo exige).
  - `—[aprueba]→ generando`  `—[rechaza]→ generando (sin tool)`.
- `generando —[fin]→ completado` · cualquier estado `—[ollama caído]→ error` · `—[botón detener]→ cancelado`.
Invariante: solo una generación activa por sesión.

## ST-020 — Carga de modelo (MOD-011)
`ninguno → comprobando → (descargando?) → descargando_pesos? → cargado → error`.
- `comprobando —[instalado]→ cargado` (tras asegurar que es el único cargado).
- `comprobando —[no instalado]→ descargando` (confirma tamaño en disco) `→ cargado`.
- Regla "uno a la vez": al pasar a `cargado` el modelo B, el A pasa a `descargado` (keep_alive 0).

## ST-030 — Alcance/autorización del Modo Seguridad (CRÍTICA, NFR-030/G-1)
`bloqueado → declarando_alcance → autorizacion_pendiente → autorizado → (operando) → [revocado]`.
- Entrada al modo sin engagement autorizado ⇒ `bloqueado` (no se puede chatear).
- `bloqueado —[crear engagement + alcance]→ declarando_alcance`.
- `declarando_alcance —[marca checkbox autorización]→ autorizacion_pendiente —[confirmar]→ autorizado`.
- `autorizado —[entrar]→ operando` (desbloquea SCR-021/022/023). Registra en auditoría.
- `operando —[editar alcance]→ autorizacion_pendiente` (re-confirmar) — el cambio de alcance se audita.
- Cualquier acción activa hacia herramientas externas: requiere confirmación por acción (no cambia de
  estado global, pero exige ST-040).
Invariante: **sin `autorizado` no hay análisis ni chat de seguridad.**

## ST-040 — Confirmación de herramienta (tool-calling con confirmación)
`propuesta → esperando_usuario → (aprobada → ejecutando → hecha) | (rechazada)`.
- Aplica a `guardar_archivo` (Scripts) y a **toda** acción activa externa (Seguridad).
- Timeout o cierre ⇒ `rechazada` por defecto (seguro por defecto).

## ST-050 — Escalado a Nube (MOD-050)
`local → sugerido → (aceptado_nube → enviando → recibido) | (rechazado → local_troceado)`.
- `sugerido` solo si Nube activada; si no, se muestra info y se queda en `local_troceado`.
- `aceptado_nube` registra en auditoría qué se envía (resumen). (NFR-010)

## ST-060 — Arranque de la app (MOD-001)
`iniciando → comprobando_backend → comprobando_ollama → (ok → shell) | (problema → SCR-008)`.
- `SCR-008` ofrece acciones: arrancar Ollama, descargar modelo faltante, reintentar.
