# 14 — Plan de Pruebas

Cada FR importante tiene al menos una prueba. El builder no marca una rama como "hecha" (ver `16-...md`)
sin sus pruebas en verde. Pruebas de backend con pytest; de UI, manuales guiadas o con Playwright si se
añade.

## Núcleo / Router / Ollama
- **TST-001** `GET /salud` responde con Ollama ok y lista de modelos. (NFR-020)
- **TST-002** El router resuelve (scripts, pequeno, medio) → `pequeno-codigo` con num_ctx=8192. (FR-004)
- **TST-003** Cambiar de tier descarga el modelo anterior (solo uno cargado). (FR-005)
- **TST-004** Con modelo no instalado, API-011 lo descarga y reporta progreso. (MOD-011)
- **TST-005** Con Ollama caído, la generación emite evento `error` y la UI guía a SCR-008. (NFR-020)
- **TST-006** Esfuerzo extra activa thinking/reasoning_effort=high en modelos Qwen3. (FR-002)

## Escalado
- **TST-010** Entrada que supera num_ctx del tier → veredicto RECOMENDADO_NUBE (motivo contexto). (FR-050)
- **TST-011** Con Nube desactivada, se explica y se ofrece troceo; no se envía nada fuera. (FR-052, NFR-010)
- **TST-012** Con Nube activada y aceptación del usuario, se registra en auditoría qué se envió. (ST-050)

## Scripts/Firmware
- **TST-020** Generación de un script Python corto en local, con streaming. (FR-020)
- **TST-021** Guardar a archivo pide confirmación y escribe solo en la carpeta del proyecto. (FR-021, ST-040)
- **TST-022** Plantillas insertan andamiaje correcto. (FR-023)
- **TST-023** "Firmware completo" dispara escalado. (FR-024)

## Seguridad (incluye los guardarraíles)
- **TST-030** Entrar en Seguridad sin autorización confirmada deja el modo **bloqueado**. (FR-030, ST-030)
- **TST-031** `analizar` sobre recon pegado crea `findings` en estado `idea` con "dónde enfocar". (FR-031)
- **TST-032** La IA no ejecuta acciones activas; cualquier integración externa exige confirmación. (FR-032, G-2)
- **TST-033** Una petición que cruza la lista "nunca" (G-3) es rechazada con explicación y reconducción.
- **TST-034** El redactor une dos enfoques/evidencias en un informe exportable. (FR-033)
- **TST-035** Cambiar el alcance re-exige confirmación y queda auditado. (ST-030, FR-063)

## Academia de Seguridad (MOD-090, ver doc 18)
- **TST-035** Cambiar Enfoque (Ofensivo/Defensivo) filtra las rutas y el contenido mostrado. (FR-035)
- **TST-036** La estructura Ruta→Módulo→Lección es navegable y el enrolamiento crea progreso. (FR-036)
- **TST-037** La pista escala por niveles (empujón→dirección→más detalle) y nunca entrega un exploit
  listo; comprobar respuesta da feedback didáctico. (FR-037)
- **TST-038** Sin declarar entorno de laboratorio autorizado (BTN-087), el tutor **no guía ejercicios**;
  la declaración queda auditada; nunca guía sobre sistemas reales de terceros. (FR-038, guardarraíl)
- **TST-039** Completar una sección otorga XP (menos si hubo pistas) y el progreso/árbol de herramientas
  persiste. (FR-039)

## Laboratorio Linux (MOD-091, doc 19) y Apariencia (MOD-100, doc 20)
- **TST-070** "Abrir Linux del laboratorio" lanza la terminal en la carpeta del ejercicio con README_LAB.md
  del contexto (o abre el attack box mostrando el contexto al lado). Requiere laboratorio autorizado. (FR-070)
- **TST-071** La autodetección recomienda WSL2 o attack box en este hardware y marca VirtualBox como
  "pesado". (FR-071)
- **TST-072** La instalación/arranque del backend pide confirmación explícita y se audita; nada se instala
  sin OK del usuario. (FR-072, ST-040)
- **TST-073** El Estudio de Apariencia aplica un tema con vista previa en vivo, valida contraste y persiste
  en `ui.*` tras reiniciar. (FR-073)
- **TST-075** El Copiloto de Laboratorio propone un siguiente paso coherente con el contexto del lab cargado
  y respeta las pistas progresivas. (FR-075)
- **TST-076** Al pegar la salida de un comando, el copiloto la explica y sugiere el paso siguiente sin
  ejecutar nada por su cuenta. (FR-076)
- **TST-074** FORJA abre como ventana de escritorio propia (sin navegador). (FR-074)

## Telemetría de generación (MOD-013, doc 22)
- **TST-077** La telemetría se actualiza en vivo durante la generación (tiempo, tokens, tok/s). (FR-077)
- **TST-078** La ETA aparece, se afina con la velocidad real y nunca es negativa; muestra "estimando…"
  hasta ser fiable. (FR-078)
- **TST-079** Se distingue la fase "pensando" de "respondiendo" y el razonamiento se puede ver/plegar. (FR-079)

## Tareas
- **TST-040** Añadir tareas desde texto libre. (FR-040)
- **TST-041** Organizar produce un plan por días válido (JSON mapeado a `tasks`). (FR-041)
- **TST-042** Mover/marcar/editar persisten en SQLite. (FR-042/043)
- **TST-043** JSON de planificación imperfecto se sanea sin romper la app. (robustez)
- **TST-044** Un troceo de MOD-050 entra como tareas `origen=troceo`. (integración)
- **TST-045** La captura en lenguaje natural extrae fecha/hora y prioridad del texto. (FR-045, P1)
- **TST-046** Reorganizar respeta las tareas con `fijada=1` y lo movido a mano. (FR-046, P2)
- **TST-047** La carga del día avisa (ámbar) cuando un día supera `plan.capacidad_dia_min`. (FR-047, P3)
- **TST-048** Una subtarea anida bajo su padre (`parent_id`) y persiste indentada. (FR-048, P4)
- **TST-049** (opcional) Convertir una idea del mapa en tarea crea una tarea `origen=idea`. (FR-049, P5)

## Persistencia / Ajustes
- **TST-060** Conversaciones y mensajes se guardan y recargan tras reiniciar. (FR-060)
- **TST-061** Activar Nube guarda la clave en keyring, no en la BBDD en claro. (NFR-010)
- **TST-062** Export de conversación/informe a Markdown. (FR-062)
- **TST-063** Migración de esquema aplica sin perder datos (con copia previa del `.db`). (MOD-060)

## No funcionales
- **TST-100** App (sin modelo) consume <300 MB RAM. (NFR-002)
- **TST-101** UI responde <100 ms a interacciones locales; generación hace streaming. (NFR-001)
- **TST-102** Núcleo funciona sin red (desconecta y verifica todo salvo Nube). (NFR-004)

## Criterios de aceptación de la v1 (resumen)
Todas las TST-0xx de núcleo, los tres modos con sus flujos principales (TST-020/030/040) y los
guardarraíles de seguridad (TST-030..033) en verde. Rendimiento dentro de lo esperado para CPU (`01-...md`).
