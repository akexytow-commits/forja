# ADR-0004 — Router determinista por tabla (modo × tier × esfuerzo)

**Estado:** aceptada · **Fecha:** 2026-11-21

## Contexto
Los dos selectores (modo, y modelo+esfuerzo) deben traducirse a un modelo y unos parámetros concretos de
forma predecible y testeable. Nada de heurísticas ocultas que hagan la app impredecible.

## Decisión
Un **router por tablas** (ver `04-...md`): (modo, tier) → familia de modelo; esfuerzo → parámetros
(thinking/reasoning_effort/temperatura/num_predict); tier → num_ctx. Todo explícito, versionado y cubierto
por pruebas (TST-002/006). El esfuerzo se implementa con el "thinking" nativo de los modelos Qwen3 y se
**emula** por prompt+parámetros en los modelos de código sin thinking.

## Alternativas consideradas
- **Selección automática por el propio modelo o por un clasificador:** más "mágico" pero menos predecible
  y más difícil de depurar en un equipo con recursos limitados.

## Consecuencias
- +Reproducible, testeable, fácil de explicar y de ajustar (tabla editable).
- +Permite calibrar sin tocar código (umbrales/num_ctx en Ajustes).
- −Hay que mantener la tabla cuando cambien los modelos del registro (DB-007).
