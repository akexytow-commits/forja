# 01 — Restricciones de Hardware (LEER PRIMERO)

Esta app se diseña **alrededor de tu máquina**, no al revés. Si ignoras esta sección, construirás algo
que no arranca o que va a 1 token/segundo.

## Perfil exacto del equipo
| Componente | Valor | Implicación para IA |
|---|---|---|
| CPU | AMD Ryzen 3 5425U (Zen 3, 6 núcleos / 12 hilos, ~2.7 GHz, U-series bajo consumo) | Inferencia **solo CPU**. Correcta para 3–8B cuantizados; lenta para más. |
| RAM | 8 GB (≈7.31 GB usable), 3200 MT/s | **El cuello de botella principal.** Windows ya usa 2–4 GB. Para el modelo quedan ~3.5–5 GB reales. |
| GPU | AMD Radeon integrada (~0.5 GB dedicada, comparte RAM) | **No usable para inferencia seria.** Tratamos la máquina como CPU-only. |
| Disco | 238 GB, ~209 GB usados → **~29 GB libres** | Cada modelo ocupa disco. Hay que liberar espacio y presupuestarlo. |
| SO | Windows 10/11 | WebView2 ya viene instalado (bien para la UI). Ollama tiene instalador Windows. |

## Presupuesto de RAM (regla de oro)
`RAM_modelo ≈ tamaño_fichero_cuantizado + KV_cache(contexto)`

- Con ~5 GB disponibles para el modelo, el **tope práctico** es:
  - **Pequeño:** 3–4B en **Q4_K_M** → fichero ~2.3–2.8 GB, deja aire para contexto. **Fluido.**
  - **Grande (local):** 7–8B en **Q4_K_M** → fichero ~4.4–4.9 GB. **Cabe pero va justo y lento.**
    Mantener contexto corto (≤4–8k) y cerrar apps. Si hay inestabilidad, usar **Q4_0** o bajar a 7B.
  - **> 8B o MoE grandes (p. ej. 30B):** **no caben.** Para eso está el tier **Nube**.
- **Contexto cuesta RAM.** Cada 1k tokens de contexto añade decenas–cientos de MB de KV cache. El router
  limitará el contexto por tier (ver `04-...md`).

## Presupuesto de disco
| Elemento | Disco aprox. |
|---|---|
| Ollama (motor) | ~1.5 GB |
| Modelo Pequeño (3–4B Q4) | ~2.5 GB |
| Modelo Grande (7–8B Q4) | ~4.7 GB |
| Backend + UI + venv Python | ~0.5–1.5 GB |
| Bases de datos + logs (crecen con uso) | arranca en MB |
| **Total mínimo recomendado** | **~10–11 GB** |

Con 29 GB libres **cabe**, pero conviene liberar espacio. En `15-build-run-despliegue.md` hay una tarea
(`libera-disco`) donde la propia app (Modo Tareas) puede listarte candidatos a desinstalar; la decisión
siempre es tuya.

## Decisiones que impone este hardware
1. **CPU-only.** El backend fuerza inferencia en CPU; no asumimos CUDA/ROCm. (ADR-0001)
2. **Shell ligero.** Nada de Electron pesado. Recomendado **pywebview + FastAPI** (pura Python + web
   estática), que apenas consume RAM y no exige toolchain de Rust/Node para compilar. Tauri queda como
   mejora futura opcional. (ADR-0002)
3. **Un modelo cargado a la vez.** No cargamos Pequeño y Grande simultáneamente: no hay RAM. El router
   **descarga** el anterior antes de cargar el siguiente (Ollama lo hace con `keep_alive`).
4. **Cuantización agresiva por defecto** (Q4_K_M) y contexto acotado por tier.
5. **El tier Nube es la vía para lo grande** (p. ej. firmware completo de Flipper Zero). La app lo
   **propone** cuando el estimador detecta que la tarea no cabe en local (ver `05-...md`).

## Expectativa de rendimiento (honesta)
- Pequeño (3–4B, CPU): aprox. **8–15 tokens/s**. Bien para chat, scripts cortos, organizar tareas.
- Grande (7–8B, CPU): aprox. **3–7 tokens/s**. Usable para respuestas puntuales; tedioso para textos muy
  largos. Por eso existe el esfuerzo "extra" y el escalado a nube.
- Primer token ("time to first token") puede tardar varios segundos al cargar el modelo por primera vez.

> Resumen: tu intuición era correcta. Lo pequeño y mediano, en local sin problema. Lo "extra/grande de
> verdad", a la nube. La app está construida exactamente sobre esa idea.
