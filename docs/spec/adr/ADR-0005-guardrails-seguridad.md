# ADR-0005 — Guardarraíles del Modo Seguridad como código y FSM

**Estado:** aceptada · **Fecha:** 2026-11-21

## Contexto
El Modo Seguridad asiste en bug bounty **autorizado**: la IA orienta y redacta informes; el usuario
ejecuta y valida con su licencia. Hay que garantizar que la herramienta no se use para atacar de forma
autónoma, contra objetivos no autorizados, ni para generar malware/exploits armados. Un simple texto en el
prompt no basta como garantía.

## Decisión
Implementar los guardarraíles (`10-...md`, G-1..G-5) como **código y máquina de estados**, no solo como
prompt:
- **Gate de alcance/autorización (ST-030):** sin `engagement.autorizacion_confirmada=1` el modo está
  bloqueado a nivel de backend (no solo de UI).
- **Sin ejecución autónoma (G-2):** la IA tiene herramientas activas en este modo; cualquier
  integración externa es solo lectura o pasa por confirmación por acción o explotacion (ST-040).
- **Auditoría (G-5):** cambios de alcance, confirmaciones y escalados a Nube se registran (DB-008).

## Alternativas consideradas
- **Solo instrucciones en el prompt:** insuficiente y no auditable; el modelo local podría ignorarlas.

## Consecuencias
- +Los límites no dependen de la obediencia del modelo; son estructurales y auditables.
- +No estorban el trabajo legítimo (encajan con el flujo real: orientar → tú validas → informe).
- −Algo más de trabajo de implementación; se prioriza en la Rama 4 (guardarraíles primero).
