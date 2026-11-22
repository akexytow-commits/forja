# 11 — Modo Organizador de Tareas (MOD-040)

El modo "más normal" que pediste: escribes lo que tienes que hacer y la IA lo **organiza** en un plan por
días (hoy / mañana / pasado…) que puedes **leer y editar** desde la app. Es el modo donde el **esfuerzo
medio/extra** luce, porque "razonar la mejor organización" es justo una tarea de razonamiento.

## Objetivo
Capturar tareas en texto libre → convertirlas en un plan priorizado y repartido por días → mantenerlo
vivo (mover, marcar hecho) de forma persistente y local.

## Prompt de sistema (resumen; final en `prompts/tareas.txt`)
- Rol: planificador personal en español.
- Reglas: a partir de la lista del usuario, estima prioridad y esfuerzo de cada tarea, detecta
  dependencias ("esto antes que aquello"), y reparte en días de forma realista (no sobrecargar un día).
  Devuelve un **JSON estructurado** (ver abajo) además de un resumen legible.
- Esfuerzo: con `medio` hace un reparto decente; con `extra` razona dependencias y equilibrio de carga.

## Formato de salida de la planificación (contrato con MOD-040)
La IA, al "Organizar", devuelve JSON que el backend mapea a `tasks` (DB-005b):
```json
{ "plan": [
   { "texto": "...", "prioridad": 1, "estimacion_min": 60, "dia_asignado": "2026-11-21", "orden": 1 },
   { "texto": "...", "prioridad": 2, "estimacion_min": 30, "dia_asignado": "2026-11-22", "orden": 1 }
 ],
 "resumen": "Hoy céntrate en X e Y; mañana Z..." }
```
Si el modelo local devuelve JSON imperfecto, el backend lo **sanea** (parser tolerante) y, si falla, pide
al modelo reformatear. (Robustez: nunca romper por JSON mal formado.)

## Pantallas y botones
### SCR-030 — Captura de tareas
- Área de texto: escribes tus tareas (una por línea o en prosa).
- **BTN-050 Añadir** → API-041 crea tareas `origen=usuario` (sin día asignado aún).
- **BTN-055 Organizar** → API-042 con el esfuerzo actual → la IA reparte por días → va a SCR-031.

### SCR-031 — Plan por días
- Columnas/listas por día: **Hoy**, **Mañana**, **Pasado**, **Más adelante**, **Sin asignar**.
- Cada tarea muestra texto, prioridad y estimación; checkbox de estado.
- **BTN-051 Mover de día** (arrastrar o menú) → API-043 (`dia_asignado`).
- **BTN-052 Reordenar** dentro del día → API-043 (`orden`).
- **BTN-053 Marcar hecha** → API-043 (`estado=hecha`).
- **BTN-054 Editar tarea** → texto/prioridad/estimación.
- **BTN-056 Reorganizar** → vuelve a pedir a la IA que recomponga respetando lo que ya marcaste/moviste.
- **BTN-057 Nueva lista** → varias listas (p. ej. "Proyecto FORJA", "Bug bounty", "Personal").

## Integraciones
- **Con el Estimador (MOD-050):** cuando una tarea de otro modo se trocea (p. ej. firmware por módulos),
  los pasos entran aquí como tareas `origen=troceo`, para que el plan grande viva en el organizador.
- **Con Scripts/Seguridad:** desde esos modos, "mandar al organizador" crea tareas aquí.

## Por qué el esfuerzo importa aquí
- `bajo`: solo ordena por prioridad declarada, sin repartir fino.
- `medio`: reparte por días equilibrando carga (recomendado por defecto en este modo).
- `extra`: además razona dependencias y hueco realista; útil cuando tienes muchas tareas entrelazadas.

## Patrones copiados de los mejores planificadores (ingeniería inversa)
Ver **`17-patrones-planificador.md`** para el detalle. Resumen de lo que este modo incorpora:
- **P1 (Todoist)** captura en lenguaje natural → fecha/prioridad automáticas. FR-045.
- **P2 (Motion/Sunsama)** fijar tareas; Reorganizar respeta lo fijado. FR-046, BTN-058.
- **P3 (Sunsama)** carga del día con aviso de sobrecarga. FR-047.
- **P4 (Logseq)** subtareas anidadas / outliner. FR-048, BTN-059.
- **P5 (Obsidian/Xmind, opcional)** mapa de ideas (SCR-032). FR-049.

## Pruebas asociadas
TST-040 (añadir tareas), TST-041 (organizar genera plan por días válido), TST-042 (editar/mover/marcar
persisten), TST-043 (JSON imperfecto se sanea sin romper), TST-044 (troceo entra como tareas),
TST-045..049 (patrones P1–P5 del doc 17).
