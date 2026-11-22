# 17 — Patrones a copiar en el Planificador (ingeniería inversa)

Qué patrones de los mejores organizadores/planificadores **debería copiar Claude Code** en el Modo Tareas
de FORJA, de qué herramienta sale cada uno, **qué mecanismo replicar** (el comportamiento observable, no el
código de nadie) y **cómo se integra** con IDs trazables. Pensado para funcionar en local y en tu hardware.

> "Ingeniería inversa" aquí = estudiar *cómo se comporta* la función en la app de referencia y reproducir
> ese comportamiento con nuestros propios medios (parser local + modelo Pequeño + SQLite). No se copia ni
> decompila software de terceros; se replica el patrón de UX/lógica.

---

## P1 · Captura en lenguaje natural → fecha y prioridad automáticas
- **Copiado de:** **Todoist** (su "natural language parsing").
- **Mecanismo a replicar:** el usuario escribe una línea normal — *"pagar factura mañana 17:00 !!"* — y el
  sistema extrae solo: fecha/hora (`mañana 17:00`) y prioridad (`!!`), y la tarea queda ya colocada.
- **Cómo en FORJA:**
  - Parser local de dos capas: (1) **regex/reglas** para fechas relativas (hoy, mañana, lun, "en 3 días",
    HH:MM) y marcadores de prioridad (`!`, `!!`, `!!!`, "urgente"); (2) si queda ambiguo, se lo pasa al
    **modelo Pequeño** con un prompt que devuelve JSON `{texto_limpio, dia_asignado, prioridad}`.
  - Se ejecuta en **BTN-050 Añadir** (API `POST /tareas` lo hace server-side). El usuario puede corregir.
- **Nuevo requisito:** **FR-045**. · **Prueba:** TST-045.

## P2 · Re-planificación que respeta lo que tú fijaste
- **Copiado de:** **Motion** y **Sunsama** (auto-reschedule).
- **Mecanismo a replicar:** cuando algo cambia, la app recoloca el plan **sola**, pero las tareas que tú has
  "fijado" o movido a mano **no se tocan**; solo se re-reparten las libres.
- **Cómo en FORJA:**
  - Columna `tasks.fijada` (0/1) y **BTN-058 Fijar tarea** (SCR-031). 
  - **BTN-056 Reorganizar** (ya existía) pasa a respetar `fijada=1` y el `dia_asignado` que tú pusiste a
    mano: la IA solo recompone el resto. Esto es lo que hace que la re-planificación no te deshaga el día.
- **Nuevo requisito:** **FR-046**. · **Prueba:** TST-046.

## P3 · "Carga del día" (time-boxing realista)
- **Copiado de:** **Sunsama** (daily planning con límite de capacidad).
- **Mecanismo a replicar:** cada tarea tiene minutos estimados; la app suma por día y **avisa si un día se
  pasa** de tu capacidad (p. ej. 8 h). Evita el clásico "meter 14 cosas en el martes".
- **Cómo en FORJA:**
  - Usa `tasks.estimacion_min` (ya existe). Ajuste `settings.plan.capacidad_dia_min` (p. ej. 480).
  - SCR-031 muestra por columna una **barra de carga** (suma/capacidad) y marca en ámbar los días
    sobrecargados. La IA, al Organizar/Reorganizar, intenta no superar la capacidad.
- **Nuevo requisito:** **FR-047**. · **Prueba:** TST-047.

## P4 · Outliner por bloques: subtareas y reordenar
- **Copiado de:** **Logseq** (y Obsidian outliner).
- **Mecanismo a replicar:** cada tarea es un "bloque" que puedes **anidar** bajo otro (crear subtareas) y
  **reordenar** arrastrando. Un proyecto se desglosa en pasos sin cambiar de pantalla.
- **Cómo en FORJA:**
  - Columna `tasks.parent_id` (FK a `tasks`, nullable). **BTN-059 Anidar / crear subtarea** (SCR-031).
  - El plan por días muestra las subtareas indentadas bajo su padre. Encaja con el **troceo** del estimador
    (MOD-050): un firmware troceado entra como una tarea padre con sus módulos como subtareas.
- **Nuevo requisito:** **FR-048**. · **Prueba:** TST-048.

## P5 · Mapa de ideas (capturar antes de planificar) — FASE 2 / opcional
- **Copiado de:** **Obsidian** (grafo) y **Xmind** (mind map).
- **Mecanismo a replicar:** un lienzo donde sueltas ideas como nodos, las **enlazas** entre sí y
  **ramificas** una idea grande en sub-ideas; luego una idea o una rama se **convierte en tarea(s)**.
- **Cómo en FORJA:**
  - Nueva pantalla **SCR-032 Mapa de ideas** (módulo MOD-040). Tablas opcionales `ideas` (DB-005c) y
    `idea_links` (DB-005d). **BTN-065 Convertir idea en tarea**, **BTN-066 Enlazar ideas**.
  - **Degradación por hardware:** en tu portátil, un lienzo con grafo pesado puede ir justo. Por eso esta
    fase es **opcional** y la versión mínima es una **lista anidada** (reutiliza P4) en vez de un canvas.
    El canvas completo queda para "mejora futura".
- **Nuevo requisito:** **FR-049** (marcado opcional/fase 2). · **Prueba:** TST-049.

---

## Qué NO copiamos (y por qué)
- **Sincronización en la nube / multidispositivo** (Todoist, TickTick): va contra "100% local". Fuera.
- **Calendario externo / integraciones** (Motion con Google Calendar): fuera del alcance v1 (N-5).
- **IA siempre re-planificando en segundo plano** (Motion): en CPU local sería caro; FORJA re-planifica
  **cuando tú pulsas** Reorganizar, no sola.
- **Grafo global tipo Obsidian de toda tu base**: pesado para 8 GB; nos quedamos con el mapa por lista.

## Orden de construcción (encaja en el roadmap)
- **Dentro de la Rama 3 (Modo Tareas):** P1, P2, P3, P4 (son baratos y de alto valor).
- **Rama futura / fase 2:** P5 (mapa de ideas con canvas). La versión lista-anidada de P5 ya la cubre P4.

## Resumen de trazabilidad (lo que este doc añade al spec)
| Patrón | Fuente | Requisito | Botón/Pantalla nuevos | BBDD | Prueba |
|---|---|---|---|---|---|
| P1 Lenguaje natural | Todoist | FR-045 | (mejora BTN-050) | — | TST-045 |
| P2 Fijar + re-plan | Motion/Sunsama | FR-046 | BTN-058 | `tasks.fijada` | TST-046 |
| P3 Carga del día | Sunsama | FR-047 | (SCR-031) | `settings.plan.capacidad_dia_min` | TST-047 |
| P4 Subtareas/outliner | Logseq | FR-048 | BTN-059 | `tasks.parent_id` | TST-048 |
| P5 Mapa de ideas | Obsidian/Xmind | FR-049 (opc.) | SCR-032, BTN-065, BTN-066 | `ideas`, `idea_links` | TST-049 |
