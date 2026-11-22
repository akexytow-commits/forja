# FORJA — IA local de escritorio

Construida desde la especificación de `docs/spec/` (léela por el `README.md` de esa carpeta).

## Arrancar
**Como app (Rama 7):** doble clic en el acceso directo **FORJA** del Escritorio o del menú Inicio. No hace
falta terminal ni navegador: se abre su propia ventana.

```
build.bat               construye dist\FORJA.exe (PyInstaller, un solo archivo, sin consola, con icono)
build.bat instalar      además lo instala: %LOCALAPPDATA%\Programs\FORJA\FORJA.exe + accesos directos
dist\FORJA.exe --instalar   lo mismo, con un .exe ya construido
run.bat                 desarrollo: ventana nativa (pywebview + WebView2) desde el código
run.bat --sin-ventana   lo mismo, pero en el navegador
test.bat                pruebas (pytest)
```
Los datos se guardan en `%APPDATA%\FORJA\forja.db` (o en `FORJA_DATA_DIR`) y el registro en
`%APPDATA%\FORJA\logs\forja.log`. Backend en `127.0.0.1:8756` (si ese puerto lo ocupa otra aplicación, elige
uno libre solo).

Requisito externo: **Ollama** (`winget install Ollama.Ollama`) y como mínimo el modelo `qwen2.5-coder:3b`.
Si faltan, la propia app lo detecta y lo descarga desde la pantalla *Estado del sistema* (SCR-008).

## Estado por ramas (16-roadmap-y-ramas.md)
| Rama | Estado |
|---|---|
| 0 Andamiaje y salud | ✅ FastAPI + `/salud`, SQLite con todas las tablas (001_init.sql), ventana pywebview |
| 1 Router + Ollama + chat | ✅ verificada con Ollama 0.40.16 real: qwen2.5-coder:3b a ~8,5 tok/s, 1.er token ~16 s con el modelo sin cargar; cambio de modelo deja uno solo en RAM; thinking de qwen3 llega separado |
| 2 Estimador + escalado | ✅ estimador (05-...md) con umbrales en Ajustes; aviso SCR-006 como modal (Nube) o banner (justo); troceo con el modelo local → tareas `origen=troceo`; Nube = Claude por **tu suscripción vía Claude Code headless** (ADR-0006, `nube.backend=claude_code`, verificado con plan Pro) o, opcional, por la API con clave (`nube.backend=api`, clave en el Administrador de credenciales); sin sesión de Claude Code el tier se deshabilita y SCR-008 guía; cada envío auditado |
| 3 Modo Tareas | ✅ tablero Hoy/Mañana/Pasado/Más adelante/Sin asignar (ST1) con minutos y **carga del día** (ST2/P3); captura en **lenguaje natural** con vista previa (P1: fechas, hora, prioridad, duración; lo ambiguo lo resuelve el modelo Pequeño); **Organizar/Reorganizar** (bajo = reglas, medio/extra = IA con JSON saneado) que respeta lo **fijado** (P2); **subtareas** por sangría, menú o Alt+→ (P4); arrastrar y soltar, editar, marcar, varias listas; el troceo entra como tarea padre con subtareas. Verificado con qwen3:4b real (~3 min por organización en medio) |
| 4 Modo Seguridad | ✅ gate de alcance y autorización a pantalla completa (SG1, ST-030 en backend: sin engagement autorizado no hay chat ni análisis; cambiar el alcance obliga a reconfirmar); guardarraíles como código (`modes/guardarrailes.py`: alcance por dominio/comodín/IP/CIDR y lista «nunca» G-3 — malware, evasión de AV/EDR, borrar rastros, DoS, phishing, objetivos fuera de alcance — se bloquea antes de llamar al modelo y se audita); chat por engagement; análisis de recon con salida estructurada → hallazgos «idea»; tabla de hallazgos (SG2) con validación que exige evidencia; informe estilo HackerOne (SG3) en streaming que une varios enfoques; export .md a «Documentos\FORJA exportados\informes» (no dentro del proyecto: en Windows Documents\FORJA = Documents\forja) |
| 4b Academia + Laboratorio Linux + Copiloto | ✅ en Seguridad, selector **Trabajo / Aprender** y **Ofensivo / Defensivo** (FR-035, auditado). Academia: currículo semilla Ruta → Módulo → Lección (8 rutas por habilidad y por rol, 18 módulos, 32 lecciones, 17 herramientas; migración 007); el tutor prepara cada lección (teoría + ejercicio + herramientas + pregunta) y la guarda; **gate de laboratorio** (BTN-087: sin declarar no hay prácticas, pistas de ejercicios, copiloto ni Linux; auditado); **pistas progresivas** 1-2-3 (sin código en los niveles 1-2; la respuesta se tapa aunque el modelo la suelte); comprobar respuesta (local y determinista si hay respuesta conocida, feedback del modelo si fallas, flags de salas externas se registran); XP por dificultad (−25 % por pista, mín. 25 %, evaluación ×2), rango, racha y árbol de herramientas (SCR-026). Laboratorio Linux (SCR-027): detecta WSL, VirtualBox y RAM; recomienda WSL2 o attack box y marca VirtualBox «pesado»; instalación solo con confirmación explícita + UAC (ST-040, auditado); «Abrir Linux del laboratorio» escribe `README_LAB.md` + `notas.md` en `%USERPROFILE%\FORJA-lab\NNN-lección` y abre `wsl --cd` en Windows Terminal (o el attack box en el navegador). **Copiloto** junto a la lección/terminal: siguiente paso, «Explícame esto» y dudas, con el contexto del lab y tus notas; no ejecuta nada. G-3 se aplica antes del modelo; el «alcance» son IPs privadas, *.htb/*.thm/localhost y lo que declaraste |
| 5 Proyectos, plantillas, export, telemetría y pulido | ✅ **Proyectos** (SCR-011, desplegable SC1): nuevo proyecto con nombre + carpeta (sugerida en `Documentos\FORJA proyectos\<nombre>` o elegida con el selector nativo de la ventana), abrir carpeta, asociar el hilo; el modelo ve el nombre, la descripción y la lista de archivos del proyecto del hilo. **Guardar a archivo** (BTN-031) en cada bloque de código cerrado: sugiere la ruta que el modelo escribió antes del bloque (`src/main.py`), diálogo de confirmación con la ruta final, segunda confirmación para sobrescribir, auditado; el backend rechaza `..`, rutas absolutas, nombres reservados de Windows y enlaces/uniones que salgan de la carpeta. **Plantillas** (BTN-032): Python, Bash, PowerShell y Firmware base (FAP de Flipper Zero) en `backend/plantillas/*.md`; las tuyas en `%APPDATA%\FORJA\plantillas` mandan. **Exportar conversación** a Markdown (BTN-060, con el razonamiento plegado en `<details>`) en `Documentos\FORJA exportados\conversaciones`. **Ajustes** por pestañas (SA1): Modelos (registro, descargas, qué modelo usa cada modo, precarga), Nube, Apariencia (tema, 6 acentos, densidad, tipografía, plegar razonamiento, telemetría; vista previa en vivo), Rutas y Avanzado (umbrales + `lab.*`). **Telemetría en vivo** (doc 22): `⏱ tiempo · fase · tokens · tok/s · ~ETA · Detener` junto al compositor y **BTN-100** ver/plegar razonamiento (también Ctrl+.); al terminar queda el resumen (tiempo, tokens, cuánto pensó) en la línea y en el mensaje |
| 6 Personalización de interfaces | ✅ **Protocolo del doc 13 ejecutado**: las 17 preguntas PREGUNTAR (G1–G5, S1–S3, SC1–SC2, SG1–SG3, ST1–ST2, SE1, SA1), una clave `ui.*` por pregunta, con tus respuestas en la migración 010. Ajustes › **Interfaces**: una fila por pregunta, por pantalla; **se repinta al momento** (vista previa en vivo, Guardar persiste, Cerrar deshace) y se puede **re-pulir** cualquier pantalla sin tocar las demás. Todas las opciones de cada pregunta están implementadas: pestañas icono+texto/texto/icono · esfuerzo en segmentos o deslizador · modelo en tooltip o a la vista · proyectos desplegable o fijo a la izquierda · resaltado de código (nuevo, sin dependencias) acorde/siempre oscuro/alto contraste · gate a pantalla completa o **asistente por pasos** (Alcance → Reglas → Autorización) · hallazgos en tabla o tarjetas · plantilla de informe HackerOne/Bugcrowd/breve/**propia** (editable) · tareas en tablero o lista, con o sin minutos y carga · escalado modal+banner/siempre modal/siempre banner · Ajustes en pestañas o una página · tema claro/oscuro/**seguir el sistema** |
| 6b Verificador de código | ✅ **Comprobar** (BTN-101) en cada bloque de Python, PowerShell, Bash o JavaScript de Scripts → `POST /scripts/verificar` (API-032): **solo análisis estático, nunca ejecuta el código** — Python con `compile()` (= py_compile) + ruff si está; PowerShell con su parser (AST) + PSScriptAnalyzer si está; Bash con `bash -n` (Git-Bash o WSL) + shellcheck si está; JS con `node --check`. Errores con línea y mensaje bajo el bloque; si falta la herramienta, aviso claro y oferta de instalarla con winget **tras confirmar** (auditado). Si hay errores, **Corregir con la IA** (BTN-102): código + errores al Motor de Chat en el mismo hilo; el bloque nuevo se puede volver a Comprobar |
| 7 Empaquetado a .exe | ✅ `dist\FORJA.exe` (~25 MB) con PyInstaller `--onefile`: backend + pywebview + `ui/`, prompts, migraciones y plantillas como datos; **sin consola** e **icono** propio (el yunque de la UI, en tu violeta). `FORJA.exe --instalar` lo copia a `%LOCALAPPDATA%\Programs\FORJA` (sin admin) y crea los **accesos directos** del Escritorio y del menú Inicio. **Primer arranque limpio**: crea `%APPDATA%\FORJA\` y aplica las migraciones; secuencia **ST-060**: backend → Ollama (`/salud`) → shell, o **SCR-008** con la guía (arrancar Ollama / descargar el modelo) si falta Ollama o un modelo necesario. Ollama sigue siendo externo. Una sola instancia (un segundo doble clic avisa); los errores de arranque salen en un cuadro de diálogo con la ruta del registro |
| 8 Estudio de Apariencia | ✅ **SCR-040** (icono de paleta en la barra, o Ajustes › Apariencia, que ahora es su acceso directo, BTN-063). **Presets** (BTN-095): FORJA oscuro, FORJA claro, Alto contraste y tres con personalidad: Fragua, Medianoche y Papel. **Color y acento** (BTN-096): tema base oscuro/claro/sistema/alto contraste, 6 acentos o cualquier color, y colores base propios (fondo, superficie, texto); el resto de tonos se derivan solos. **Contraste comprobado** (WCAG AA): informe en vivo con cada ratio, y «Aplicar» se bloquea si algo no se lee (el backend lo vuelve a validar). **Tipografía y densidad** (BTN-097): sistema, mono, serif, redondeada (Bahnschrift) o humanista (Verdana); cómoda/compacta. **Fondo** (BTN-098): liso, degradado suave o una imagen tuya con opacidad del 5 % al 45 %. **Acento por modo** (opcional) y **una sola animación** (los mensajes aparecen), desactivable. **Vista previa en vivo** (BTN-099): toda la app se repinta al momento, más una maqueta con los dos selectores y una conversación de ejemplo; «Aplicar» lo guarda en `ui.*` y «Cancelar» (o Esc) lo deshace |

Pruebas cubiertas (219): TST-001…006, 010…012, 020…023, 030…039, 032b, 040…048, 060…063, 070…072, 075…079, 100…102 (+ token, validación, CRUD) TST-073 (`tests/test_estudio.py`: presets y acentos legibles, CSS = backend, combinaciones ilegibles rechazadas, persistencia tras reiniciar y, en Edge headless, vista previa en vivo, bloqueo por contraste y el tema aplicado tras reiniciar el servidor), empaquetado (`tests/test_empaquetado.py`: abre el `dist\FORJA.exe` real como un doble clic, con `%APPDATA%` vacío y sin Ollama → ventana «FORJA», BBDD migrada, SCR-008 y una sola instancia; se salta si no se ha construido), TST-080…082 (`tests/test_verificador.py`, contra las herramientas reales del equipo; las que falten se saltan) y Rama 6 (`tests/test_rama6.py`: las preferencias `ui.*` persisten tras reiniciar, se re-pulen sin perder nada y **se aplican**, comprobado en Edge headless contra un servidor reiniciado; se salta si no hay Edge).
La UI de la Rama 5 se recorrió además en Edge headless (CDP) con un Ollama falso lento: plantillas, nuevo proyecto,
telemetría (esperando → pensando → respondiendo), BTN-100, guardar y sobrescribir, export, ajustes y cambio de tema/acento, sin errores de consola.

## Desviaciones conscientes respecto a la spec
- **API nativa de Ollama (`/api/chat`) en lugar de `/v1/chat/completions`.** Solo la nativa acepta
  `num_ctx`/`num_gpu` por petición (presupuesto de RAM y CPU-only) y devuelve el *thinking* separado.
- **`reasoning_effort`**: Ollama solo admite activar o desactivar el thinking en Qwen3. *medio* y *extra* se
  diferencian por `num_predict` y temperatura; el valor `medium/high` queda en el plan del router.
- **Nuevo hilo (BTN-033)** no crea la conversación al momento: se crea con el primer mensaje, así no
  quedan hilos vacíos.
- **Nube (ADR-0006)**: Claude Code se llama sin herramientas, sin sesión guardada, en una carpeta aislada y sin
  `ANTHROPIC_API_KEY` en el entorno; el historial va como un único prompt etiquetado. Claude Opus 5.5 por defecto (elegible Sonnet/Haiku 5.5 en Ajustes), pensamiento adaptativo con
  resumen visible, esfuerzo bajo/medio/extra → `low/medium/high`, fallback del servidor ante rechazos.
  "Escalar a Nube" envía solo esa petición; el selector inferior no cambia.
- **Botón extra en SCR-006**: "Enviar en local igualmente", para cuando el estimador se pase de prudente.
- **Modo Tareas**: mover una tarea a mano la fija (como en Sunsama), igual que poner fecha al escribirla;
  el pin la suelta. Las tareas con subtareas son contenedores: se planifican las hojas y el padre toma el
  primer día de sus hijas. La carga cuenta solo hojas (sin estimación = 30 min). Lo que no cabe en la
  capacidad pasa al día siguiente. P5 (mapa de ideas, fase 2) no está construido; lo cubren las subtareas.
- **Guardar a archivo** es un botón por bloque de código (BTN-031), no *tool-calling* del modelo: los modelos de 3–4B
  llaman mal a herramientas. El efecto es el mismo que pide la spec (confirmación + solo dentro del proyecto). La
  confirmación se exige también en el backend (`confirmado`, y `sobrescribir` si existe). Si el hilo no tenía proyecto,
  guardar en uno lo asocia. Un proyecto no puede vivir en la raíz de una unidad, en carpetas del sistema ni en las de FORJA.
  Borrar un proyecto no borra su carpeta.
- **Asociar un hilo nuevo** (sin mensajes) a un proyecto crea el hilo en ese momento (excepción a «se crea con el primer mensaje»).
- **Selector de carpetas** del SO: solo existe con la ventana nativa (pywebview); en `--sin-ventana` se escribe la ruta.
- **Telemetría**: fases `esperando`/`cargando` además de `pensando`/`respondiendo` (antes del primer token en CPU pasan
  10–20 s). La ETA usa la salida prevista del estimador + razonamiento típico por esfuerzo, topada por `num_predict` y
  mezclada con la mediana de las últimas respuestas del mismo modelo; es pesimista en respuestas cortas y se redondea
  (`~40 s`, `~2 min`). El evento lleva también `thinking_ms`; `messages` guarda `gen_ms` y `thinking_ms` (migración 008).
  En la Nube los tokens en vivo son aproximados (por caracteres).
- **Apariencia** en Ajustes es la versión básica (presets cerrados); el estudio completo con contraste y fondos es la Rama 8.
- **Spec rev (15)**: copiada a `docs/spec` (doc 23: aviso sobre «Corregir con la IA»). Rev. 14: doc 23 verificador, API-032, FR-080/081, TST-080…082, BTN-101/102, MOD-110). Antes, rev. 13 (doc 07: API-055). Doc 04 (rev. 12 recoge el prompt de medio implementado y los tiempos medidos): registro 2507, etiquetas reales, override de Seguridad, tope de razonamiento y mejora del prompt de medio. Doc 07: eventos `tope_razonamiento` y `reclasificar`. TST-032b.
- **Doc 21 (Política de Restricciones) aplicado** a `backend/prompts/scripts.txt`, `seguridad.txt` y `tareas.txt`
  (2026-11-22): tono de experto autorizado, directo, sin moralinas ni descargos; en Seguridad, la lista de lo permitido
  sobre objetivos en alcance (recon, fuzzing, prueba de credenciales si el programa lo permite, PoC mínima, Metasploit/
  Hydra/ffuf/Burp/nuclei, forense) y los límites mínimos (solo alcance, nada de malware ni exploits armados para dañar,
  sin ejecución autónoma), con la respuesta de una frase + alternativa legítima. Solo cambia el texto: los guardarraíles
  siguen como código (`modes/guardarrailes.py`, ADR-0005) y no cambia lógica ni endpoints. `academia.txt` no se tocó
  (el doc 21 nombra solo esos tres). El tier Nube conserva la seguridad propia de Anthropic.
  Verificado con Ollama 0.40.16 real (CPU):
  - Scripts (qwen2.5-coder:3b, bajo): script de puertos TCP en escucha con `psutil`, explicación + código + cómo
    probarlo, sin descargos; 78 s, 402 tokens, telemetría en vivo.
  - Seguridad (qwen3:4b): arranca y genera tras el gate; «hazme un ransomware…» lo corta G-3 en código antes del
    modelo, con su reconducción. **Pero** pidiendo un comando de ffuf no llega a una respuesta final: en *bajo*
    razona en inglés dentro de la respuesta y agota los 512 tokens; en *medio* gasta los 1024 pensando. Con el prompt
    **antiguo** pasa exactamente lo mismo, así que no lo causa el doc 21: es el modelo (qwen3 ignora a veces `think:false`)
    con los topes de `num_predict`. Resuelto en la sección «Modo Seguridad con modelos thinking en CPU» de abajo.
  - Tareas (qwen3:4b, medio): organizó 3 tareas en 3 días con estimaciones y un resumen directo; 85 s.
- **Modo Seguridad con modelos thinking en CPU** (doc 04 rev. 10, 2026-11-22).
  - **Causa raíz.** El `qwen3:4b` de Ollama es **Qwen3-4B Thinking-2507**: no es híbrido. Su plantilla abre siempre
    `<think>`, y ni `/no_think` ni `think:false` lo apagan. Con `think:false`, Ollama deja de separar el
    razonamiento y este llega mezclado en la respuesta, terminado en `</think>`. Para responder sin razonar no
    vale un flag: hace falta **otro modelo**.
  - **Registro** (migración 009). Etiquetas reales de Ollama: las del doc 04 sin sufijo no existen en el
    registro de Ollama, así que llevan `-q4_K_M`.
    - `pequeno-general` → `qwen3:4b-instruct-2507-q4_K_M` (instruct, sin thinking).
    - Nuevo `pequeno-razonador` → `qwen3:4b-thinking-2507-q4_K_M` (mismo blob que el antiguo `qwen3:4b`).
    - La migración solo cambia `pequeno-general` si seguía en `qwen3:4b`; si se había editado en Ajustes, se respeta.
    - Consecuencia: Chat y Tareas en tier pequeño usan ahora el instruct; el thinking de esfuerzo extra se emula por prompt.
  - **Router** (`OVERRIDE_ESFUERZO` en `router.py`):
    - **bajo** → modelo de **código** (`pequeno-codigo`/`grande-codigo`), `num_predict` 768: comandos y
      snippets directos (ffuf, nmap…).
    - **medio** → `pequeno-general` = **instruct**, `num_predict` 1536: análisis directo. En grande, qwen3:8b
      (híbrido) va con thinking apagado + `/no_think`. Doc 04 rev. 11: el prompt de medio exige empezar con
      «**Clase:** …», el nombre estándar de la vulnerabilidad, **sin números** de CWE ni de OWASP
      (`INSTRUCCION_SEGURIDAD_MEDIO`).
    - **extra** → `pequeno-razonador` = **thinking-2507**, `num_predict` 3072, con tope de razonamiento. El
      análisis de hallazgos (`/seguridad/.../analizar`) usa también el razonador en extra.
    - Si la BBDD no tiene `pequeno-razonador`, se usa `pequeno-general`.
    - El estimador mantiene su límite de salida en 2048 × factor (`SALIDA_LOCAL_BASE`).
  - **`/no_think`** (`ollama_client.sin_thinking`): solo para qwen3 que razonan (no para los `*instruct*`) cuando
    el thinking va apagado. Se añade al último mensaje y `num_predict` sube a 768 como mínimo. Trabaja sobre copias.
  - **Tope de razonamiento** (`MotorChat._stream_con_tope`, reutilizable para cualquier llamada con thinking del chat):
    - Si el thinking llega al 60 % de `num_predict` sin que haya empezado la respuesta, cierra el stream.
    - Emite `tope_razonamiento` {tokens_thinking, limite, num_predict, restante, modelo_respuesta}.
    - Hace una segunda llamada con la pregunta + lo pensado (`<razonamiento>…`, hasta 12 000 caracteres) y el
      presupuesto restante, con el **modelo de respuesta**:
      - con el razonador, el instruct del tier (`PlanDeModelo.etiqueta_respuesta`). Antes descarga el que
        razona, para que solo haya un modelo en RAM;
      - con un modelo híbrido, el mismo con thinking apagado + `/no_think`.
    - `fin.tokens_out` suma las dos llamadas.
    - El evento `tope_razonamiento` está en API-003 desde la rev. 11.
  - **Red de seguridad (B)** (`ollama_client.FiltroThink`). Con el thinking apagado o sin pedir, en cualquier modo:
    - lo que va entre `<think>` y `</think>` sale como `thinking`;
    - si llega un `</think>` cuando ya se mostraba como respuesta, se emite `reclasificar`: el Motor mueve ese
      texto al razonamiento y la UI lo pliega;
    - en las respuestas completas (`chat_completo`, JSON de Tareas/Seguridad) se descarta lo anterior al `</think>`.
    - El evento SSE `reclasificar` está en API-003 desde la rev. 11.
  - La UI muestra en la línea de estado el modelo real según el esfuerzo (`/modelos` expone `override`).
  - Pruebas: TST-032b y el resto en `tests/test_router_seguridad.py`.
  - **Verificación con Ollama real**: 2026-11-22, portátil de 7,3 GB, solo CPU, mismo engagement de laboratorio.
    - **bajo** (`qwen2.5-coder:3b`): comando `ffuf … -fc 404` directo; 66 s, 245 tokens.
    - **medio** (instruct): análisis completo y en español que termina solo (1237 de 1536 tokens, sin cortes ni
      razonamiento mezclado); **318 s**, no los 1–2 min del doc 04. En CPU va a ~4 tok/s. Calidad justa: lo llama
      «enumeración de IDs / control de acceso» en vez de IDOR por su nombre.
    - **extra** (thinking-2507 → instruct): el tope saltó a 1843 tokens de razonamiento. La respuesta del instruct
      **se completó** («IDOR… Impacto: Alto… Cómo verificar… Conclusión»; 3005 de 3072 tokens en total). En total
      **1072 s (~18 min)**, casi todo razonando. Antes (rev. 9), medio y extra se cortaban sin respuesta.
    - **medio tras la mejora de la rev. 11** (pruebas sucesivas con la misma pregunta):
      - con «clase + OWASP/CWE», empieza por «**Clase:** IDOR…», pero se inventa el número (CWE-601);
      - con «el CWE solo si estás seguro», da CWE-602, también incorrecto;
      - sin CWE, da OWASP «A03», incorrecto: es A01;
      - con **solo el nombre** (versión final), sale «**Clase:** IDOR (Insecure Direct Object Reference)» en 224 s.
      Medio ha bajado a **~4 min** (219–310 s) porque la respuesta es más concisa.
- **Academia**: `learning_sections.tipo` admite también `evaluacion` (la evaluación de final de módulo de A3) y
  guarda `pregunta`/`respuesta_esperada` (alternativas con `|`; nunca viaja a la UI). La lección generada se guarda
  en `learning_progress.leccion_md`. Las flags de salas externas no se pueden verificar: se registran como
  entregadas y se avisa. `GET /academia/leccion/{id}` devuelve la estructura; el texto del tutor se genera en
  streaming con `POST /academia/leccion/{id}/generar`. El copiloto tiene además `POST /academia/copiloto/chat`.
- **Laboratorio**: VirtualBox solo se instala (winget) y se abre la carpeta del ejercicio; crear y arrancar la VM
  queda a mano. La instalación de WSL se lanza con `Start-Process -Verb RunAs`, así que Windows pide su propio OK
  además del de FORJA.

- **Rama 6**: **API-055** `GET /seguridad/plantillas-informe` (en el doc 07 desde la rev. 13) da las plantillas de informe (HackerOne, Bugcrowd, breve y la propia) a Ajustes › Interfaces y al redactor (SCR-022), que tiene su propio selector de plantilla: es el mismo ajuste `ui.informe_plantilla`. Claves extra: `ui.informe_estructura` (la plantilla propia de SG3, hasta 4000 caracteres) y `ui.protocolo_respondido` (fecha). Además de lo que pide SC2 se añade un resaltado de sintaxis mínimo (`ForjaMD.resaltar`): antes los bloques no tenían color, así que las tres opciones no se habrían distinguido. El panel de proyectos fijo se oculta por debajo de 720 px de ancho.

- **Rama 6b (verificador)**: «Corregir con la IA» usa `POST /scripts/corregir` (el catálogo dice «POST /chat (corrección)»): es el mismo Motor de Chat y el mismo streaming, pero el prompt de corrección se arma en el backend (`verificador.prompt_correccion`). Extras: `GET /scripts/verificar/herramientas` y `POST /scripts/verificar/instalar` (ST-040: sin `confirmado` solo propone; con él abre winget en una ventana aparte y se audita como `verificador_instalar`, migración 011). Python se compila con `compile()` dentro del proceso en vez de `python -m py_compile` (hace lo mismo y funciona también empaquetado en .exe); como el compilador, informa del primer error de sintaxis — tras corregirlo, Comprobar muestra el siguiente. A los procesos se les quita del entorno `BASH_ENV`, `ENV`, `NODE_OPTIONS`… para que no carguen código al arrancar; PowerShell va con `-NoProfile`.
  - Verificado en este equipo (2026-11-22): Python, PowerShell 5.1, Bash (Git-Bash) y Node detectan el error con su línea; ruff, shellcheck y PSScriptAnalyzer no están instalados (se usan si aparecen). TST-081 comprueba con las herramientas reales que escribir un archivo / `print` / `Set-Content` / `touch` / `writeFileSync` no ocurre.
  - «Corregir con la IA» con qwen2.5-coder:3b real: 42 s; el bloque corregido pasa el verificador, pero la explicación que lo acompañaba era incorrecta (hablaba de una «coma» y un «corchete»). Fíate de Comprobar, no del texto. Por eso (doc 23 rev. 15) el bloque corregido **se vuelve a comprobar solo** y lleva ese aviso debajo.

- **Rama 7 (empaquetado)**: `--onefile` como pide el doc 15. El precio es que cada arranque descomprime el .exe en una carpeta temporal: tarda unos segundos más que `run.bat` en abrir la ventana. El .exe no está firmado: la primera vez Windows SmartScreen puede avisar («Más información» → «Ejecutar de todas formas»). El icono (`assets/forja.ico`) se genera con `tools/generar_icono.py` desde el yunque de la UI (Edge headless, sin Pillow). `FORJA_SIN_DIALOGOS=1` desactiva los cuadros de diálogo (lo usan las pruebas). El doc 15 lista `qwen3:4b` en «Preparación»; el registro real es el de la rev. 10 del doc 04 (instruct/thinking 2507), y la propia app ofrece descargarlos desde SCR-008.

- **Rama 8 (Estudio de Apariencia)**:
  - **Fuente única de los colores:** `backend/apariencia.py` guarda paletas, presets, derivación de tonos y contraste. La UI le pide la paleta resultante (`POST /apariencia/previa`) en vez de calcularla, y `PUT /ajustes` rechaza con `CONTRASTE_INSUFICIENTE` cualquier combinación ilegible (con «seguir el sistema» comprueba las dos variantes).
  - **Mínimos:** texto ≥ 4,5:1, texto secundario ≥ 3:1 (se corrige solo) y acento sobre fondo ≥ 3:1. La tinta sobre el acento se elige sola, negra o blanca.
  - **Colores en línea:** solo con colores propios (acento `#rrggbb`, colores base o acento por modo) se pone la paleta en línea; sin ellos mandan los temas afinados a mano en el CSS.
  - **Nombres de clave:** el doc 20 habla de `ui.fuente`; la clave es `ui.tipografia` (existe desde la Rama 5). Claves nuevas (migración 012, sin tocar tu tema): `ui.base`, `ui.fondo`, `ui.acento_por_modo`, `ui.animacion` y `ui.preset`.
  - **Imagen de fondo:** se guarda en `%APPDATA%\FORJA\fondos` (`POST /apariencia/fondo`, PNG/JPG/WebP/GIF de 8 MB como máximo; endpoints no listados en el doc 07). La UI la pide con el token y la usa como blob.

## Personalización aplicada (13-protocolo-personalizacion.md)
Protocolo respondido el 2026-11-22 (Rama 6). Guardado en `settings` (`ui.*`, migración 010); se cambia y se
re-pule en **Ajustes › Apariencia** (globales) y **Ajustes › Interfaces** (por pantalla), sin reiniciar.

| Pregunta | Clave | Tu elección |
|---|---|---|
| G1 nombre | `ui.nombre_app` | FORJA |
| G2 tema | `ui.tema` | **claro** (también oscuro y *seguir el sistema*; el botón de la barra alterna) |
| G3 acento | `ui.acento` | **violeta** |
| G4 densidad | `ui.densidad` | **compacta** |
| G5 tipografía | `ui.tipografia` | **monoespaciada** |
| S1 pestañas de modo | `ui.pestanas` | icono + texto |
| S2 esfuerzo | `ui.esfuerzo_control` | segmentos |
| S3 modelo | `ui.mostrar_modelo` | tier, modelo real en tooltip |
| SC1 proyectos | `ui.proyectos` | desplegable |
| SC2 resaltado | `ui.codigo_tema` | **alto contraste** |
| SG1 gate | `ui.gate` | **asistente por pasos** |
| SG2 hallazgos | `ui.hallazgos` | tabla |
| SG3 informe | `ui.informe_plantilla` | HackerOne (editable: «Propia» usa `ui.informe_estructura`) |
| ST1 plan | `ui.tareas_vista` | tablero |
| ST2 carga | `ui.tareas_carga` | sí (minutos y carga del día) |
| SE1 escalado | `ui.aviso_escalado` | modal si Nube, banner si justo |
| SA1 ajustes | `ui.ajustes` | pestañas |

Lo FIJADO del doc 13 no depende de estas claves: los dos selectores siempre visibles, el gate obligatorio (en
el asistente, «Entrar» solo aparece en el paso 3 y sigue exigiendo la declaración), la explicación del
escalado y la decisión del usuario. La migración solo cambia una clave si seguía en su DEFAULT anterior, así
que lo que ya hubieras retocado en Ajustes se respeta.
