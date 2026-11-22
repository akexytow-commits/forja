# FORJA — IA local de escritorio

Construida desde la especificación de `docs/spec/` (léela por el `README.md` de esa carpeta).

## Arrancar
```
run.bat                 ventana nativa (pywebview + WebView2)
run.bat --sin-ventana   lo mismo, pero en el navegador
test.bat                pruebas (pytest)
```
Los datos se guardan en `%APPDATA%\FORJA\forja.db` (o en `FORJA_DATA_DIR`). Backend en `127.0.0.1:8756`.

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
| 6–7 | pendiente (empaquetado, etc.) |
| 8 Estudio de Apariencia | pendiente (doc 20, al final) |

Pruebas cubiertas (154): TST-001…006, 010…012, 020…023, 030…039, 040…048, 060…063, 070…072, 075…079, 100…102 (+ token, validación, CRUD).
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
- **Spec rev (7)**: copiada a `docs/spec`.
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
    con los topes de `num_predict`. Pendiente de decidir (es lógica, no prompt): subir `num_predict` cuando hay thinking
    y/o usar el modelo de código para respuestas cortas de comandos.
  - Tareas (qwen3:4b, medio): organizó 3 tareas en 3 días con estimaciones y un resumen directo; 85 s.
- **Academia**: `learning_sections.tipo` admite también `evaluacion` (la evaluación de final de módulo de A3) y
  guarda `pregunta`/`respuesta_esperada` (alternativas con `|`; nunca viaja a la UI). La lección generada se guarda
  en `learning_progress.leccion_md`. Las flags de salas externas no se pueden verificar: se registran como
  entregadas y se avisa. `GET /academia/leccion/{id}` devuelve la estructura; el texto del tutor se genera en
  streaming con `POST /academia/leccion/{id}/generar`. El copiloto tiene además `POST /academia/copiloto/chat`.
- **Laboratorio**: VirtualBox solo se instala (winget) y se abre la carpeta del ejercicio; crear y arrancar la VM
  queda a mano. La instalación de WSL se lanza con `Start-Process -Verb RunAs`, así que Windows pide su propio OK
  además del de FORJA.

## Personalización aplicada (13-protocolo-personalizacion.md)
G1 nombre FORJA · G2 dos temas: oscuro (negro + gris) y claro (gris claro + negro), con botón para cambiar ·
G3 acento naranja forja · G4 densidad cómoda · G5 tipografía del sistema. S1–S3, SC1 y SE1 (modal para Nube, banner para "justo") con sus
valores por defecto. Todo guardado en `settings` (`ui.*`).
