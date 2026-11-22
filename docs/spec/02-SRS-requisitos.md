# 02 — Requisitos (SRS)

Requisitos **trazables**: cada uno enlaza con los módulos/pantallas/pruebas que lo cumplen. El builder
debe poder responder "¿qué satisface FR-012?" mirando los catálogos.

## Requisitos Funcionales (FR)

### Núcleo / Router
- **FR-001** El usuario puede elegir el **tier de modelo**: Pequeño | Grande | Nube. → MOD-010, SCR-002, BTN-020..022
- **FR-002** El usuario puede elegir el **esfuerzo**: bajo | medio | extra. → MOD-010, BTN-023..025
- **FR-003** El selector de tier+esfuerzo está **siempre visible** (abajo, junto al compositor). → SCR-001
- **FR-004** El router traduce (modo, tier, esfuerzo) a un **modelo concreto + parámetros** de forma
  determinista y documentada. → MOD-010, `04-...md`
- **FR-005** Solo hay **un modelo cargado a la vez**; cambiar de tier descarga el anterior. → MOD-010, MOD-011
- **FR-006** El tier **Nube** solo está disponible si el usuario lo ha **activado y configurado** (clave).
  Si no, el botón aparece deshabilitado con explicación. → MOD-012, SCR-007

### Modos
- **FR-010** El usuario puede cambiar de **modo**: Scripts/Firmware | Seguridad | Tareas, con el selector
  superior **siempre visible**. → SCR-001, BTN-010..012
- **FR-011** Cada modo tiene su **prompt de sistema**, su conjunto de herramientas y su interfaz. → MOD-020/030/040
- **FR-012** Cambiar de modo **no pierde** la conversación del modo anterior (cada modo tiene su hilo). → DB-002

### Modo Scripts/Firmware (MOD-020)
- **FR-020** Chat con el modelo para escribir/explicar/depurar código y scripts. → SCR-010
- **FR-021** Bloques de código con **copiar** y **guardar a archivo** (en una carpeta de proyecto local). → BTN-030..031
- **FR-022** Soporte de **proyectos**: agrupar conversaciones y archivos por proyecto. → DB-004, SCR-011
- **FR-023** El modo ofrece **plantillas** (script Python, script Bash/PowerShell, firmware base). → BTN-032
- **FR-024** Si la petición es "grande" (p. ej. firmware completo), se activa el **estimador de escalado**
  y se sugiere Nube. → MOD-050

### Verificador de código (MOD-110) · ver `23-...md`
- **FR-080** Botón **"Comprobar"** en cada bloque de código (Scripts): ejecuta el linter/compilador **real**
  del lenguaje (**análisis estático, nunca ejecuta el código**) y muestra errores con línea; detecta el
  lenguaje del bloque; degrada con aviso si falta la herramienta. → BTN-101, API-032
- **FR-081** **"Corregir con la IA"** (opcional): devuelve el código + los errores al modelo para una pasada
  de corrección. → BTN-102

### Modo Seguridad / Bug Bounty (MOD-030)
- **FR-030** Antes de usar el modo, el usuario declara el **alcance** (programa/objetivo) y **confirma
  autorización**. Sin ello, el modo permanece bloqueado. → ST-030, SCR-020
- **FR-031** El usuario pega/importa datos de reconocimiento (resultados que **él** obtuvo con sus
  herramientas) y la IA los **analiza** y señala **por dónde enfocar** y qué **clases de problema**
  podrían existir y su posible impacto. → SCR-021
- **FR-032** La IA **no ejecuta** acciones ofensivas por su cuenta. Cualquier integración con herramientas
  externas (p. ej. tu proxy) es **de solo lectura o requiere tu confirmación explícita** por acción. → NFR-030
- **FR-033** La IA ayuda a **redactar el informe** de bug bounty a partir de lo que tú has validado
  (puedes subir dos enfoques/evidencias y pedir que los una en un informe presentable). → SCR-022, BTN-040
- **FR-034** El modo mantiene un **registro de hallazgos** por engagement, con estado (idea → validado por
  ti → informe). → DB-006, SCR-023

### Modo Seguridad — Enfoque y Academia (MOD-090) · ver `18-...md`
- **FR-035** Selector de **Enfoque** en Seguridad: **Ofensivo** (red team) o **Defensivo** (blue team);
  filtra el contenido de la Academia (y a futuro, el encuadre del trabajo real). (copia: HTB/THM) → SCR-024
- **FR-036** **Academia**: currículo local en tres niveles **Ruta → Módulo → Lección**, con rutas por
  **habilidad** y por **rol** (Pentester Jr, Analista SOC, Red Teamer, Bug Bounty). (copia: HTB/THM) →
  MOD-090, SCR-024/025, DB-009
- **FR-037** **Aprendizaje guiado e interactivo**: cada lección = teoría + ejercicio en laboratorio +
  pregunta verificada + **pistas progresivas**; evaluación al final del módulo. (copia: HTB/THM) → SCR-025,
  BTN-084/085
- **FR-038** **Práctica solo en laboratorios autorizados** (HTB/THM, apps vulnerables locales, CTF). El
  usuario declara el entorno de laboratorio antes de que el tutor guíe ejercicios; nunca sistemas reales de
  terceros. (guardarraíl) → BTN-087, ST-030/academia
- **FR-039** **Progreso, XP, rangos y árbol de herramientas/habilidades** (catálogo de herramientas que
  enseña cada ruta). (copia: HTB/THM) → SCR-026, DB-010/011

### Modo Organizador de Tareas (MOD-040)
- **FR-040** El usuario escribe sus tareas / lo que tiene que hacer en texto libre. → SCR-030, BTN-050
- **FR-041** La IA (con esfuerzo medio/extra) **organiza** las tareas en un **plan por días** (hoy /
  mañana / pasado / …) priorizado. → MOD-040, SCR-031
- **FR-042** El plan es **editable** por el usuario (reordenar, mover de día, marcar hecho). → BTN-051..054
- **FR-043** El plan se **lee** desde la app en cualquier momento (persistente). → DB-005, SCR-031
- **FR-044** Este modo es el que ofrece de forma natural el esfuerzo **medio/extra** para "razonar" la
  mejor organización. → `04-...md`
- **FR-045** **Captura en lenguaje natural**: al añadir, un parser local (reglas + modelo Pequeño) extrae
  fecha/hora y prioridad del texto y prerrellena la tarea. (copia: Todoist) → `17-...md` P1, BTN-050
- **FR-046** **Tareas fijadas**: el usuario puede fijar una tarea; Reorganizar respeta las fijadas y lo
  movido a mano, y solo recoloca el resto. (copia: Motion/Sunsama) → `17-...md` P2, BTN-058, DB-005b
- **FR-047** **Carga del día**: la app suma minutos estimados por día y avisa si se supera la capacidad
  configurable; barra de carga por día. (copia: Sunsama) → `17-...md` P3, SCR-031
- **FR-048** **Subtareas / outliner**: una tarea puede anidarse bajo otra (parent_id) y reordenarse como
  bloques; encaja con el troceo de MOD-050. (copia: Logseq) → `17-...md` P4, BTN-059, DB-005b
- **FR-049** (opcional/fase 2) **Mapa de ideas**: lienzo para capturar ideas como nodos, enlazarlas y
  convertirlas en tareas; degrada a lista anidada en hardware limitado. (copia: Obsidian/Xmind) →
  `17-...md` P5, SCR-032

### Escalado / Nube
- **FR-050** El **estimador** calcula un "tamaño de tarea" (tokens de entrada previstos, longitud de salida
  pedida, complejidad) y un veredicto: *cabe en local* | *justo* | *recomendado Nube*. → MOD-050, `05-...md`
- **FR-051** Si el veredicto es *recomendado Nube* y la Nube está activada, la app **propone** escalar con
  un mensaje claro; el usuario **decide**. → SCR-006
- **FR-052** Si la Nube no está activada, la app explica **por qué** convendría y cómo activarla, y ofrece
  una alternativa local degradada (trocear la tarea). → MOD-050

### Laboratorio Linux (MOD-091) · ver `19-...md`
- **FR-070** Desde la Academia se puede **abrir un Linux con el contexto del laboratorio** (carpeta +
  README del ejercicio) con un botón, sin salir de FORJA. → BTN-089, SCR-025/027
- **FR-071** **Backends de laboratorio**: se construyen **WSL2 y attack box hospedado de inicio** (ambos),
  con autodetección y recomendación según hardware; **VirtualBox** queda opcional (marcado "pesado"). El
  usuario **cambia el backend activo desde una interfaz** (SCR-027, BTN-092) y puede elegirlo por
  laboratorio al abrir. → SCR-027, DB-001
- **FR-072** **Instalación/arranque guiados con confirmación explícita** (ST-040) y permisos del usuario;
  nada se instala sin su OK; se audita (DB-008). → BTN-090
- **FR-075** **Copiloto de Laboratorio**: panel de asistente en la interfaz del laboratorio que, con el
  contexto del lab cargado, propone el **siguiente paso**, **resuelve dudas** y **explica** conceptos (es
  el tutor de MOD-090 mostrado como copiloto libre). No ejecuta por su cuenta; mantiene pistas progresivas.
  → BTN-093, SCR-027
- **FR-076** El copiloto **lee la salida del terminal / comandos que le pegas** y los explica y propone el
  siguiente paso (aprovechando la experticia en código/firmware/scripts). → BTN-094

### Apariencia (MOD-100, módulo final) · ver `20-...md`
- **FR-073** **Estudio de Apariencia**: presets de tema, color/acento (con contraste válido), tipografía,
  densidad, fondo/imagen y **vista previa en vivo**; persiste en `ui.*`. Amplía Ajustes→Apariencia. →
  SCR-040, BTN-095..099

### Arranque de la app
- **FR-074** FORJA se abre como **aplicación de escritorio** (ventana propia vía pywebview / `.exe` con
  acceso directo), **no** requiere abrir un navegador ni una página web. En desarrollo se lanza con un
  `.bat`; empaquetada, con doble clic. → `15-...md`, NFR-060

### Telemetría de generación (MOD-013) · ver `22-...md`
- **FR-077** **Telemetría en vivo** durante la generación: tiempo transcurrido, tokens generados y
  velocidad (tok/s), por SSE. (copia: indicador de Claude Code) → SCR-001
- **FR-078** **ETA aproximada** de la respuesta, calculada con la velocidad actual y la salida estimada
  (MOD-050); muestra "estimando…" hasta que sea fiable; nunca negativa. → MOD-013
- **FR-079** Separar y mostrar el **tiempo de "pensando"** (thinking) del de respuesta, y poder **ver/
  plegar el razonamiento**. → BTN-100

### Persistencia / Ajustes
- **FR-060** Todas las conversaciones, mensajes, proyectos, tareas, planes y hallazgos se guardan en
  **SQLite local**. → DB-001..008
- **FR-061** Pantalla de **Ajustes**: rutas, modelos instalados, activación de Nube, tema, carpeta de
  proyectos. → SCR-007
- **FR-062** El usuario puede **exportar** una conversación o un informe a Markdown/archivo. → BTN-060
- **FR-063** **Registro de auditoría** local de acciones sensibles (cambios de alcance, escalados a nube,
  confirmaciones de acciones en Modo Seguridad). → DB-008

## Requisitos No Funcionales (NFR)
- **NFR-001 (Rendimiento).** La UI responde en <100 ms a interacciones locales; la generación hace
  **streaming** token a token para percibir fluidez pese a la CPU. → API-003
- **NFR-002 (Memoria).** La app (sin contar el modelo) consume <300 MB RAM. Un solo modelo cargado. → MOD-011
- **NFR-003 (Disco).** Instalación base (sin modelos) <1.5 GB. → `01-...md`
- **NFR-004 (Offline).** Todo el núcleo funciona **sin red**. Solo el tier Nube usa red. → O-5
- **NFR-010 (Privacidad).** Ningún dato sale del equipo salvo cuando el usuario escala explícitamente a
  Nube; en ese caso se avisa qué se envía. → FR-051
- **NFR-020 (Robustez).** Si Ollama no está arrancado o falta un modelo, la app lo **detecta** y guía al
  usuario a arrancarlo/descargarlo, sin crashear. → MOD-011, SCR-008
- **NFR-030 (Seguridad del Modo Seguridad).** Guardarraíles del `10-...md` implementados como código:
  bloqueo sin alcance, confirmación por acción activa, lista de "nunca" (no malware, no exploit armado, no
  objetivos no autorizados). → ST-030
- **NFR-040 (Mantenibilidad).** Catálogos YAML como fuente de verdad; añadir un botón = editar YAML +
  implementar + prueba. → `catalogo/`
- **NFR-050 (Accesibilidad/Idioma).** UI en **español** por defecto, textos centralizados para traducir.
- **NFR-060 (Portabilidad futura).** El backend no depende del shell; migrar de pywebview a Tauri no toca
  la lógica. → ADR-0002
