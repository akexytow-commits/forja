# Matriz Módulo → Pantalla → Botón

> Documento **generado automáticamente** desde `catalogo/*.yaml`. Es la vista consolidada de la
> ingeniería: cada módulo, sus pantallas y **cada botón** con su acción, endpoint, estado y prueba.
> No editar a mano; se regenera desde los catálogos.

**Totales:** 17 módulos · 20 pantallas · 77 botones.

## MOD-001 · App Shell  _(ui+backend)_
Arranque, ventana, salud del sistema, enrutado de pantallas, estado global (modo/tier/esfuerzo).
- **Depende de:** MOD-013, MOD-070, MOD-011
- **Requisitos:** FR-003, FR-010, NFR-020, ST-060

### SCR-001 · Shell
Layout maestro con selector de modo (arriba) y de modelo/esfuerzo (abajo) + compositor.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-010 | Scripts/Firmware | Activar modo scripts (cambia área de trabajo e hilo). | — | TST-020 |
| BTN-011 | Seguridad | Activar modo seguridad; si no hay engagement autorizado, redirige al GATE (SCR-020). | — | TST-030 |
| BTN-012 | Tareas | Activar modo organizador de tareas. | — | TST-040 |
| BTN-020 | Pequeño | Fijar tier=pequeno. Puede recargar modelo (ST-020). | POST /modelos/cargar (indirecto vía router) | TST-003 |
| BTN-021 | Grande | Fijar tier=grande. Recarga a modelo grande; aviso 'cambiando de modelo'. | idem | TST-003 |
| BTN-022 | Nube | Fijar tier=nube. Deshabilitado si Nube no activada (tooltip -> Ajustes). | — | TST-011 |
| BTN-023 | bajo | esfuerzo=bajo (thinking off / respuesta directa). | — | TST-006 |
| BTN-024 | medio | esfuerzo=medio (thinking medium / razonar breve). | — | TST-006 |
| BTN-025 | extra | esfuerzo=extra (thinking high / razonar a fondo). | — | TST-006 |
| BTN-100 | Ver/plegar razonamiento | Muestra u oculta el bloque de 'thinking'. Junto al botón corre la línea de telemetría (tiempo, tokens, tok/s, ETA, fase). No es un botón de acción destructiva. | — | TST-079 |
| BTN-106 | Usar base de conocimiento | Toggle en el compositor: activa el RAG en la consulta actual; al enviar se recuperan fragmentos top-k y se anteponen al contexto con citas. | POST /kb/{id}/buscar (interno al chat) | TST-085 |
| BTN-107 | Ver fuentes citadas | Tras la respuesta, muestra qué fragmentos/fuentes de la base se usaron. | — | TST-085 |

## MOD-010 · Router de Modelos  _(backend)_
Traduce (modo, tier, esfuerzo, tamaño) a modelo+parámetros (tabla determinista).
- **Depende de:** MOD-011, MOD-012
- **Requisitos:** FR-001, FR-002, FR-004, ADR-0004

### SCR-002 · Panel de modelo/esfuerzo
El selector inferior; refleja tier/esfuerzo y si Nube está disponible.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-020 | Pequeño | Fijar tier=pequeno. Puede recargar modelo (ST-020). | POST /modelos/cargar (indirecto vía router) | TST-003 |
| BTN-021 | Grande | Fijar tier=grande. Recarga a modelo grande; aviso 'cambiando de modelo'. | idem | TST-003 |
| BTN-022 | Nube | Fijar tier=nube. Deshabilitado si Nube no activada (tooltip -> Ajustes). | — | TST-011 |
| BTN-023 | bajo | esfuerzo=bajo (thinking off / respuesta directa). | — | TST-006 |
| BTN-024 | medio | esfuerzo=medio (thinking medium / razonar breve). | — | TST-006 |
| BTN-025 | extra | esfuerzo=extra (thinking high / razonar a fondo). | — | TST-006 |

## MOD-011 · Gestor de Ollama  _(backend)_
Comprobar salud, listar/descargar modelos, cargar/descargar (uno a la vez), keep_alive.
- **Depende de:** —
- **Requisitos:** FR-005, NFR-002, NFR-020, ST-020

### SCR-008 · Estado del sistema / arranque
Diagnóstico cuando Ollama está caído o falta un modelo.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-070 | Arrancar Ollama | Guiar/lanzar Ollama si está caído. | GET /salud | TST-005 |
| BTN-071 | Descargar modelo faltante | Descargar el modelo que falta (con aviso de tamaño). | POST /modelos/descargar | TST-004 |
| BTN-072 | Reintentar | Recomprobar salud y, si ok, entrar al shell. | GET /salud | TST-001 |

## MOD-012 · Cliente Nube  _(backend)_
Tier Nube = tu suscripción de Claude vía Claude Code headless (ADR-0006). SOLO si está activada; re-emite por SSE; registra el envío.
- **Depende de:** MOD-080
- **Requisitos:** FR-006, FR-051, NFR-010, ST-050
- _(sin pantallas propias)_

## MOD-013 · Motor de Chat  _(backend)_
Bucle de conversación, streaming SSE, tool-calling con confirmación. Emite telemetría en vivo (tiempo, tokens, tok/s, ETA, fase pensando/respondiendo) estilo Claude Code (doc 22).
- **Depende de:** MOD-010, MOD-050, MOD-060
- **Requisitos:** NFR-001, ST-010, ST-040, FR-077, FR-078, FR-079
- _(sin pantallas propias)_

## MOD-020 · Modo Scripts/Firmware  _(backend+ui)_
Perfil de código, herramientas (guardar archivo), proyectos, plantillas.
- **Depende de:** MOD-013, MOD-050, MOD-060
- **Requisitos:** FR-020, FR-021, FR-022, FR-023, FR-024

### SCR-010 · Chat Scripts/Firmware
Chat con streaming, bloques de código, plantillas.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-030 | Copiar | Copiar el bloque de código al portapapeles. | — | TST-020 |
| BTN-031 | Guardar a archivo | Guardar bloque en carpeta del proyecto. Requiere confirmación (ST-040); no escribe fuera. | POST /proyectos/{id}/guardar-archivo | TST-021 |
| BTN-032 | Plantillas | Insertar andamiaje (Python/Bash/PowerShell/Firmware base) en el compositor. | — | TST-022 |
| BTN-033 | Nuevo hilo | Crear conversación nueva en modo scripts. | POST /conversaciones | TST-060 |
| BTN-060 | Exportar conversación | Exportar la conversación actual a Markdown/archivo. | POST /export | TST-062 |
| BTN-101 | Comprobar | Ejecuta el linter/compilador real del lenguaje del bloque (estático, NUNCA ejecuta el código) y muestra errores con línea. Degrada con aviso si falta la herramienta. | POST /scripts/verificar | TST-080 |
| BTN-102 | Corregir con la IA | (Aparece si hay errores) Devuelve el código + los errores al modelo para una pasada de corrección. Opcional (lento en CPU). | POST /chat (corrección) | TST-082 |

### SCR-011 · Proyectos
Proyectos locales (carpeta) y asociación de hilos.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-034 | Nuevo proyecto | Crear proyecto (nombre + carpeta local). | POST /proyectos | TST-021 |
| BTN-035 | Abrir carpeta | Abrir el explorador del SO en la carpeta del proyecto. | — | TST-021 |
| BTN-036 | Asociar hilo a proyecto | Vincular la conversación actual a un proyecto. | PATCH /conversaciones/{id} | TST-060 |

## MOD-030 · Modo Seguridad  _(backend+ui)_
Gate de alcance/autorización, análisis de recon aportado, hallazgos, informes. Guardarraíles como código.
- **Depende de:** MOD-013, MOD-060, MOD-080
- **Requisitos:** FR-030, FR-031, FR-032, FR-033, FR-034, NFR-030, ST-030, ADR-0005

### SCR-020 · Alcance y autorización (GATE)
Declarar alcance y confirmar autorización. Bloquea el modo hasta completarse.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-037 | Nuevo engagement | Crear engagement con alcance (dominios/activos). | POST /engagements | TST-030 |
| BTN-038 | Confirmar autorización | Declarar que se tiene autorización para probar esos activos (checkbox obligatorio). | PATCH /engagements/{id} | TST-030 |
| BTN-039 | Entrar al engagement | Desbloquear SCR-021/022/023. Registrar en auditoría. | — | TST-030 |

### SCR-021 · Análisis de reconocimiento
Pegar/importar recon aportado por el usuario y analizarlo (crea findings).

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-041 | Importar archivo | Cargar datos de reconocimiento que el usuario obtuvo con sus herramientas. | — | TST-031 |
| BTN-042 | Analizar | Analizar el recon aportado; crear findings en estado 'idea' con 'dónde enfocar'. No ejecuta acciones. | POST /engagements/{id}/analizar | TST-031 |

### SCR-022 · Redactor de informe
Unir enfoques/evidencias validados por el usuario en un informe exportable.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-040 | Generar informe | Unir dos enfoques/evidencias validados por el usuario en un informe presentable. | POST /findings/{id}/informe | TST-034 |
| BTN-045 | Exportar informe | Exportar el informe a Markdown/archivo para enviarlo al programa. | POST /export | TST-062 |

### SCR-023 · Hallazgos
Lista de findings con estado; marcar validado, añadir manual.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-043 | Marcar validado por mí | Cambiar finding a 'validado_por_usuario' y adjuntar evidencia. | POST /findings/{id} | TST-034 |
| BTN-044 | Añadir hallazgo manual | Documentar un hallazgo detectado por el usuario. | POST /findings/{id} | TST-034 |

## MOD-040 · Modo Organizador de Tareas  _(backend+ui)_
Captura de tareas, planificación con IA, plan por días editable y persistente.
- **Depende de:** MOD-013, MOD-060, MOD-050
- **Requisitos:** FR-040, FR-041, FR-042, FR-043, FR-044

### SCR-030 · Captura de tareas
Escribir tareas en texto libre y organizarlas.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-050 | Añadir | Crear tareas desde el texto libre (origen=usuario). | POST /tareas | TST-040 |
| BTN-055 | Organizar | Pedir a la IA que reparta por días según el esfuerzo (medio/extra). | POST /tareas/organizar | TST-041 |
| BTN-057 | Nueva lista | Crear una lista de tareas (p. ej. 'Bug bounty', 'Personal'). | POST /listas | TST-040 |

### SCR-031 · Plan por días
Hoy/Mañana/Pasado/Más adelante/Sin asignar; editable y persistente.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-051 | Mover de día | Cambiar dia_asignado de una tarea. | PATCH /tareas/{id} | TST-042 |
| BTN-052 | Reordenar | Cambiar el orden dentro del día. | PATCH /tareas/{id} | TST-042 |
| BTN-053 | Marcar hecha | Cambiar estado a hecha. | PATCH /tareas/{id} | TST-042 |
| BTN-054 | Editar tarea | Editar texto/prioridad/estimación. | PATCH /tareas/{id} | TST-042 |
| BTN-056 | Reorganizar | Recomponer el plan con IA respetando lo marcado/movido por el usuario. | POST /tareas/organizar | TST-041 |
| BTN-058 | Fijar tarea | Marcar tarea como fijada (fijada=1): Reorganizar no la moverá. (copia: Motion/Sunsama) | PATCH /tareas/{id} | TST-046 |
| BTN-059 | Anidar / subtarea | Convertir en subtarea de otra (parent_id) o crear subtarea; se muestra indentada. (copia: Logseq) | PATCH /tareas/{id} | TST-048 |

### SCR-032 · Mapa de ideas
(Fase 2/opcional) Lienzo para capturar ideas como nodos, enlazarlas y convertirlas en tareas. Degrada a lista anidada en hardware limitado.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-065 | Convertir idea en tarea | Convierte una idea (o una rama) del mapa en tarea(s) del plan (origen=idea). (copia: Xmind) | POST /tareas | TST-049 |
| BTN-066 | Enlazar ideas | Crear un enlace entre dos ideas del lienzo. (copia: Obsidian) | POST /idea_links | TST-049 |

## MOD-050 · Estimador de Escalado  _(backend)_
Calcular tamaño/complejidad de tarea y veredicto local/justo/nube; plan de troceo.
- **Depende de:** MOD-040
- **Requisitos:** FR-050, FR-051, FR-052, ST-050

### SCR-006 · Aviso de escalado a Nube
Explica motivo, qué se enviaría y deja decidir al usuario.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-026 | Subir a Grande | Cambiar tier a grande y reintentar (veredicto JUSTO). | — | TST-010 |
| BTN-027 | Trocear | Generar plan de troceo y mandarlo al Organizador de Tareas (origen=troceo). | POST /estimar -> plan_troceo | TST-044 |
| BTN-028 | Escalar a Nube | Reenviar la petición por MOD-012; registrar en auditoría qué se envía. | POST /chat (tier=nube) | TST-012 |
| BTN-029 | Hacerlo en local (troceado) | Rechazar nube; quedarse en local con troceo. | — | TST-011 |

## MOD-060 · Persistencia  _(backend)_
Acceso a SQLite, migraciones, copias de seguridad del .db.
- **Depende de:** —
- **Requisitos:** FR-060, ADR-0003
- _(sin pantallas propias)_

## MOD-070 · Ajustes  _(backend+ui)_
Config, activación de Nube (keyring), tema, rutas, umbrales del estimador, registro de modelos.
- **Depende de:** MOD-060, MOD-011, MOD-012
- **Requisitos:** FR-061, NFR-010

### SCR-007 · Ajustes
Modelos, Nube, apariencia, rutas, umbrales.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-061 | Gestionar modelos | Ver/descargar modelos del registro (DB-007). | GET /modelos ; POST /modelos/descargar | TST-004 |
| BTN-062 | Activar Nube | Activar tier Nube y guardar clave en keyring (no en BBDD en claro). | PUT /ajustes | TST-061 |
| BTN-063 | Apariencia | Tema claro/oscuro, acento, densidad (ui.*). | PUT /ajustes | TST-060 |
| BTN-064 | Umbrales del estimador | Calibrar umbrales de complejidad/contexto para el escalado. | PUT /ajustes | TST-010 |

## MOD-090 · Academia de Seguridad  _(backend+ui)_
Tutor estilo HTB/TryHackMe (ingeniería inversa, doc 18). Enfoque ofensivo/defensivo, currículo Ruta→Módulo→Lección, pistas progresivas, XP/rangos y catálogo de herramientas. Práctica solo en laboratorios autorizados.
- **Depende de:** MOD-013, MOD-060, MOD-080
- **Requisitos:** FR-035, FR-036, FR-037, FR-038, FR-039, NFR-030, ADR-0005

### SCR-024 · Academia — enfoque y rutas
Elegir enfoque (Ofensivo/Defensivo), explorar rutas por habilidad o por rol, declarar entorno de laboratorio autorizado y enrolarse.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-080 | Enfoque Ofensivo | Fijar enfoque=ofensivo (red team): filtra rutas/contenido hacia encontrar y explotar en laboratorio. | PUT /ajustes (seguridad.enfoque) | TST-035 |
| BTN-081 | Enfoque Defensivo | Fijar enfoque=defensivo (blue team): filtra rutas/contenido hacia detectar y responder. | PUT /ajustes (seguridad.enfoque) | TST-035 |
| BTN-082 | Enrolar en ruta | Inscribirse en una ruta (por habilidad o por rol); crea progreso inicial. (copia: HTB/THM) | POST /academia/enrolar | TST-036 |
| BTN-087 | Declarar laboratorio autorizado | Confirmar que la práctica será en un entorno legal (HTB/THM, app vulnerable local, CTF). GATE: sin esto, el tutor no guía ejercicios. Se audita. | POST /academia/laboratorio | TST-038 |

### SCR-025 · Lección / sala guiada
Teoría breve + ejercicio en laboratorio + pregunta verificada + pistas progresivas; marcar sección completada.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-083 | Empezar lección | Abrir la siguiente lección/sección de la ruta; el tutor presenta teoría + ejercicio. | GET /academia/leccion/{id} | TST-036 |
| BTN-084 | Pedir pista | Pista PROGRESIVA (empujón → dirección → más detalle); nunca un exploit listo. Incrementa pistas_usadas (afecta XP). | POST /academia/pista | TST-037 |
| BTN-085 | Comprobar respuesta | Validar lo que el usuario encontró en el laboratorio (flag/respuesta); da feedback didáctico. | POST /academia/comprobar | TST-037 |
| BTN-086 | Marcar sección completada | Marcar la sección como completada; otorga XP según dificultad y pistas usadas. | POST /academia/progreso | TST-039 |
| BTN-089 | Abrir Linux del laboratorio | Abre la terminal Linux ya situada en la carpeta del ejercicio, con README_LAB.md (objetivo, pistas, notas). En attack box, abre la máquina hospedada y muestra el contexto al lado. Requiere laboratorio autorizado (BTN-087). | POST /academia/lab/abrir | TST-070 |

### SCR-026 · Progreso y árbol de herramientas
XP, rango, racha, rutas completadas y el árbol de herramientas/habilidades que enseña cada ruta.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-088 | Ver árbol de herramientas | Mostrar el catálogo de herramientas/habilidades (para qué sirve cada una y en qué lección aparece). | GET /academia/herramientas | TST-039 |

## MOD-091 · Laboratorio Linux  _(backend+ui)_
Abrir un Linux con el contexto del lab (doc 19) + Copiloto de Laboratorio (asistente en vivo que da el siguiente paso, resuelve dudas y explica comandos/salidas, usando la experticia en código/firmware). Autodetecta y recomienda backend (WSL2 / attack box / VirtualBox opcional); instalación con confirmación. Solo tras declarar laboratorio autorizado.
- **Depende de:** MOD-090, MOD-013, MOD-080
- **Requisitos:** FR-070, FR-071, FR-072, FR-075, FR-076, NFR-030, ST-040

### SCR-027 · Laboratorio Linux
Elegir el backend ACTIVO (WSL2 y attack box de serie; VirtualBox opcional), configurarlo/instalarlo con confirmación, y abrir el Linux con el contexto del ejercicio. Incluye el panel del Copiloto de Laboratorio (siguiente paso, explicar, dudas). El backend se puede cambiar aquí y por laboratorio.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-089 | Abrir Linux del laboratorio | Abre la terminal Linux ya situada en la carpeta del ejercicio, con README_LAB.md (objetivo, pistas, notas). En attack box, abre la máquina hospedada y muestra el contexto al lado. Requiere laboratorio autorizado (BTN-087). | POST /academia/lab/abrir | TST-070 |
| BTN-090 | Configurar laboratorio Linux | Elegir backend (WSL2 recomendado / attack box / VirtualBox 'pesado'); si falta, mostrar comandos e instalar CON CONFIRMACIÓN (ST-040). Autodetecta y recomienda según hardware. | POST /academia/lab/configurar | TST-071 |
| BTN-091 | Enviar contexto al Linux | Escribe README_LAB.md con el contexto del laboratorio en la carpeta de trabajo del Linux. | POST /academia/lab/contexto | TST-070 |
| BTN-092 | Cambiar backend activo | Selector para cambiar el backend de laboratorio activo (WSL2 / attack box / VirtualBox). Cambia settings.lab.backend al instante; también se puede elegir por laboratorio al abrir. | PUT /ajustes (lab.backend) | TST-071 |
| BTN-093 | Siguiente paso | El copiloto propone el próximo paso según dónde estás y el contexto del lab (metodología, no exploit listo). Mantiene pistas progresivas. | POST /academia/copiloto/siguiente | TST-075 |
| BTN-094 | Explícame esto | Pegas un comando, concepto o la salida del terminal y el copiloto lo explica y sugiere el siguiente paso. No ejecuta nada por su cuenta. | POST /academia/copiloto/explicar | TST-076 |

## MOD-110 · Verificador de código  _(backend+ui)_
Comprueba el código generado con linters/compiladores reales (doc 23), SOLO análisis estático, nunca ejecuta el código. Python/PowerShell siempre; Bash (WSL/Git-Bash) y JS (Node) si están. Opción 'Corregir con la IA' vía MOD-013.
- **Depende de:** MOD-013
- **Requisitos:** FR-080, FR-081, ST-040
- _(sin pantallas propias)_

## MOD-100 · Estudio de Apariencia  _(backend+ui)_
Módulo final para la cara de la app (doc 20) - presets, color/acento con contraste, tipografía, densidad, fondo/imagen, vista previa en vivo. Persiste en ui.*.
- **Depende de:** MOD-070, MOD-060
- **Requisitos:** FR-073

### SCR-040 · Estudio de Apariencia
Módulo final: presets de tema, color/acento, tipografía, densidad, fondo/imagen y vista previa en vivo sobre una maqueta con los dos selectores.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-095 | Preset de tema | Aplicar un tema listo (oscuro/claro/alto contraste/otros) como punto de partida. | PUT /ajustes (ui.tema) | TST-073 |
| BTN-096 | Color y acento | Editar acento y colores base; valida contraste para legibilidad. | PUT /ajustes (ui.acento) | TST-073 |
| BTN-097 | Tipografía y densidad | Elegir fuente (sistema o concreta) y densidad (compacta/cómoda). | PUT /ajustes (ui.fuente, ui.densidad) | TST-073 |
| BTN-098 | Fondo / imagen | Fondo liso, degradado o imagen local con opacidad (sin restar legibilidad). | PUT /ajustes (ui.fondo) | TST-073 |
| BTN-099 | Vista previa / aplicar | Previsualiza en vivo sobre una maqueta con los dos selectores; al aplicar, persiste y la app repinta sin reiniciar. | PUT /ajustes | TST-073 |

## MOD-120 · Base de Conocimiento (RAG)  _(backend+ui)_
RAG local (doc 24): bases de conocimiento, indexado con nomic-embed-text, vectores en SQLite, recuperación top-k por coseno e inyección en el contexto del chat con fuentes citadas. Semilla Flipper Zero.
- **Depende de:** MOD-011, MOD-013, MOD-060
- **Requisitos:** FR-082, FR-083, FR-084, FR-085

### SCR-050 · Bases de conocimiento
Crear bases de conocimiento (RAG), añadir/importar documentos, ver estado de indexado y reindexar. Importar el paquete semilla de Flipper Zero.

| Botón | Etiqueta | Acción | Endpoint | Prueba |
|---|---|---|---|---|
| BTN-103 | Nueva base | Crear una base de conocimiento (p. ej. 'Flipper Zero'). | POST /kb | TST-083 |
| BTN-104 | Añadir documento | Pegar texto o importar archivos (.md/.txt/.pdf) o una carpeta; o importar el paquete semilla de Flipper. Lanza el indexado. | POST /kb/{id}/documentos ; POST /kb/{id}/indexar | TST-083 |
| BTN-105 | Reindexar | Vuelve a trocear y embeber los documentos de la base. | POST /kb/{id}/indexar | TST-083 |

## MOD-080 · Auditoría  _(backend)_
Registrar acciones sensibles (alcance, escalados, confirmaciones, descargas, export).
- **Depende de:** MOD-060
- **Requisitos:** FR-063, NFR-030
- _(sin pantallas propias)_
