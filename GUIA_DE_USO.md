# FORJA — Guía de uso

FORJA es tu asistente de IA **local**: todo corre en tu portátil (Ollama + modelos pequeños, solo CPU) y nada
sale del equipo salvo que tú elijas la **Nube**. Esta guía es para *usarla*; para construirla está el
`README.md`.

---

## 1. Abrir FORJA

1. **Doble clic** en el acceso directo **FORJA** del Escritorio (o búscala en el menú Inicio).
   Se abre su propia ventana: no hace falta terminal ni navegador.
2. **La primera vez**, Windows SmartScreen puede avisar porque el `.exe` no está firmado:
   pulsa **«Más información» → «Ejecutar de todas formas»**. Solo ocurre una vez.
3. Tarda unos segundos en aparecer (el `.exe` se descomprime al arrancar). Si haces doble clic otra vez
   mientras está abierta, te avisa de que ya está abierta en lugar de abrir otra.

### Si Ollama no está arrancado → «Estado del sistema» (SCR-008)
FORJA comprueba el motor al arrancar. Si **Ollama no responde**, te lleva a la pantalla
**Estado del sistema**:
- **«Arrancar Ollama»** lo lanza por ti (si está instalado). Si no está instalado, te indica cómo:
  `winget install Ollama.Ollama` o desde ollama.com/download. Luego **«Reintentar»**.
- **Modelos**: la lista muestra cuáles tienes. El único **necesario** es `qwen2.5-coder:3b`; el resto son
  **opcionales**. Para bajar uno: **«Descargar» → «Confirmar descarga»** (verás el progreso; te dice cuánto
  ocupa y cuánta RAM/disco libre tienes).
- Con todo en verde, **«Reintentar»** te deja entrar. («Entrar igualmente» sirve si quieres ver la app aunque
  falte algo.)

Modelos que usa FORJA en tu equipo:

| Modelo | Para qué | Tamaño |
|---|---|---|
| `qwen2.5-coder:3b` | Scripts y Seguridad-bajo (comandos) — **necesario** | ~1,9 GB |
| `qwen3:4b-instruct-2507-q4_K_M` | Chat, Tareas, Seguridad-medio (responde sin razonar) | ~2,5 GB |
| `qwen3:4b-thinking-2507-q4_K_M` | Seguridad-extra (razona a fondo) | ~2,5 GB |
| `qwen2.5-coder:7b`, `qwen3:8b` | Tier **Grande** (opcionales; van justos con 8 GB de RAM) | ~4,7 / 5,2 GB |

Los tres primeros ya los tienes. Solo hay **un modelo cargado a la vez** en RAM: al cambiar de modelo verás
«cambiando de modelo…» unos segundos.

---

## 2. Los dos selectores

- **Arriba, el MODO** (pestañas): **Scripts/Firmware · Seguridad · Tareas**. Cada modo tiene su pantalla y sus
  conversaciones.
- **Abajo, junto a donde escribes**:
  - **Modelo**: **Pequeño** (el normal), **Grande** (más calidad, más lento y más RAM; cierra otras apps) y
    **Nube** (tu suscripción de Claude; gris hasta que la actives, ver §4).
  - **Esfuerzo**: **bajo · medio · extra** = cuánto piensa el modelo antes de responder.

### Qué esfuerzo usar (tiempos reales en tu portátil, solo CPU)

| Esfuerzo | Úsalo para | Tiempo típico |
|---|---|---|
| **bajo** | comandos y respuestas directas («dame el comando de ffuf para…», un snippet) | **~1 min** |
| **medio** | análisis normal: explicar un fallo, un script con algo de lógica | **~4 min** en Seguridad |
| **extra** | análisis profundo cuando el resultado importa más que el tiempo | **~18 min** en Seguridad |

En Scripts, el modelo de código escribe a ~8 tokens/s y la primera palabra tarda ~15 s. Mientras genera, la
línea de estado muestra **tiempo · fase · tokens · tok/s · ~tiempo restante** y el botón **Detener**. Si el
modelo razona, puedes ver u ocultar el razonamiento con **Ctrl+.**

Si pides algo demasiado grande para el portátil (p. ej. un firmware entero), FORJA te avisa **antes** de
generar: te propone **Subir a Grande**, **Trocear** la tarea en pasos (que van a Tareas) o **Escalar a Nube**.
Tú decides; también puedes **seguir igualmente**.

---

## 3. Cada modo, paso a paso

### Scripts / Firmware
1. Escribe lo que necesitas («Script en Python que renombre fotos por su fecha EXIF») y pulsa **Intro**
   (**Mayús+Intro** = salto de línea). Elige esfuerzo **bajo** para cosas cortas.
2. En cada bloque de código tienes:
   - **Comprobar**: pasa el código por el verificador real del lenguaje (ver §5).
   - **Guardar**: lo escribe en la carpeta de un proyecto, siempre con confirmación (y otra más si va a
     sobrescribir). FORJA nunca escribe fuera de la carpeta del proyecto.
   - **Copiar**.
3. **Proyectos** (botón «Sin proyecto» de la barra): **Nuevo proyecto** = nombre + carpeta (por defecto en
   `Documentos\FORJA proyectos`). Al asociar el hilo a un proyecto, el modelo ve el nombre y la lista de
   archivos (no su contenido).
4. **Plantillas**: andamiajes de Python, Bash, PowerShell y **Firmware base** (app FAP de Flipper Zero). Se
   insertan en el cuadro de texto para que pidas sobre ellos.
5. **Exportar** (icono de flecha): la conversación a Markdown en `Documentos\FORJA exportados`.
6. **Nuevo hilo** empieza una conversación limpia; el icono ☰ muestra tus hilos anteriores.

### Seguridad (bug bounty autorizado)
Arriba eliges **Trabajo** (engagements reales autorizados) o **Aprender** (la Academia), y el enfoque
**Ofensivo / Defensivo**.

**Trabajo — engagement autorizado** (el gate es un asistente en 3 pasos):
1. **Alcance**: nombre del programa (p. ej. «Acme – HackerOne») y los activos en alcance, uno por línea
   (`*.acme.com`, `api.acme.com`…).
2. **Reglas**: lo que FORJA hará y no hará en este engagement (léelas).
3. **Autorización**: marca la declaración de que tienes permiso y pulsa **Entrar al engagement**.
   Sin esto, el chat y el análisis de Seguridad quedan bloqueados. Todo queda en la auditoría.

Dentro del engagement tienes cuatro pestañas:
- **Chat**: pregunta sobre el engagement. Bajo = comandos directos; medio = análisis (nombra primero la clase
  de vulnerabilidad); extra = análisis profundo.
- **Análisis**: pega o importa **tu** reconocimiento (salidas de nmap, ffuf, HAR…) y pulsa **Analizar**:
  propone hallazgos posibles («ideas») con dónde enfocar y cómo verificarlo sin causar daño. FORJA no ejecuta
  nada contra nadie.
- **Hallazgos**: la lista (tabla). Abre uno, pega tu **evidencia** y **«Marcar validado por mí»**. Solo se
  informa de lo que tú has comprobado.
- **Informe**: elige el hallazgo validado y la **plantilla** (HackerOne, Bugcrowd, breve o la tuya), añade
  los enfoques/caminos con los que llegaste y **Generar informe**. Revísalo, **Guarda** y **Exportar .md**
  (en `Documentos\FORJA exportados\informes`).

**Aprender — la Academia** (estilo HackTheBox / TryHackMe):
1. **Declara tu laboratorio autorizado** (p. ej. una sala de TryHackMe o Juice Shop en tu WSL). Sin esto no
   hay lecciones prácticas, ni pistas de ejercicios, ni copiloto, ni Linux.
2. **Rutas**: elige una por habilidad o por rol e **Inscríbete**.
3. **Lección**: **Empezar lección** → el tutor prepara la teoría y el ejercicio. Responde la pregunta o pega la
   flag y **Comprobar respuesta**. Si te atascas, **Pedir pista** (hasta 3: empujón → dirección → más detalle;
   cada una resta XP). **Marcar como completada** suma XP y sube tu rango (pestaña **Progreso**).
4. **Abrir Linux del laboratorio**: abre una terminal Linux (tu WSL; en este equipo, Kali) ya situada en la carpeta del ejercicio
   (`%USERPROFILE%\FORJA-lab\…`) con un `README_LAB.md` con el objetivo y tus notas. En **Laboratorio Linux**
   eliges el sistema (WSL recomendado, attack box o VirtualBox) y, si falta algo, FORJA te propone instalarlo
   **y solo lo hace si confirmas**.
5. **Copiloto** (panel lateral): **Siguiente paso** te orienta sin darte el exploit hecho; pega un comando o la
   salida del terminal y **Explícame esto**. No ejecuta nada por su cuenta.

### Tareas
1. Escribe tus tareas, **una por línea**, en lenguaje natural: «pagar factura mañana 17:00 !!»,
   «revisar PR 30min», «estudiar el viernes». Con **Tab** debajo de una tarea creas sus **subtareas**. Verás
   una vista previa con la fecha, prioridad y duración que ha entendido. **Añadir**.
2. **Organizar**: reparte por días según tu **capacidad/día** (minutos). Con esfuerzo **bajo** es instantáneo
   (reglas por prioridad); con **medio/extra** lo hace la IA (1–3 min).
3. El **plan por días** (Hoy · Mañana · Pasado · Más adelante · Sin asignar) muestra la **carga** de cada día.
   Arrastra tareas entre días, márcalas hechas, edítalas, y **fija** (📌) las que no quieres que se muevan al
   reorganizar. Puedes tener varias listas.
4. «Trocear» un encargo grande desde Scripts lo convierte en una tarea con sus pasos aquí.

---

## 4. Bases de conocimiento (RAG): que el modelo lea tus docs

Un modelo de 3–4B **con la documentación correcta delante** escribe mucho mejor código específico (Flipper Zero,
tu proyecto…) que sin ella, sin cambiar de modelo. Medido en este portátil, misma pregunta («escribe el
`application.fam` de una app externa») con `qwen2.5-coder:3b`:
- **sin base**: se inventa un YAML con un `entry_point: hola_flipper.py`. Inservible.
- **con la base de Flipper**: el `App(appid=…, apptype=FlipperAppType.EXTERNAL, entry_point=…, fap_category=…)`
  correcto, en 28 s, citando la fuente.

**Montarla (una vez)**
1. Icono de **libro** (arriba a la derecha) → **Bases de conocimiento**. Escribe un nombre («Flipper Zero») →
   **Nueva base**.
2. **Añadir documento**, en una de sus pestañas:
   - **Pegar texto**: documentación, notas o código de referencia.
   - **Archivos**: `.md`, `.txt` o `.pdf` (hasta 5 MB cada uno).
   - **Carpeta**: todos los `.md/.txt/.pdf` de una carpeta y sus subcarpetas.
   - **Paquete Flipper Zero**: la carpeta de una copia del firmware (la oficial con
     `git clone https://github.com/flipperdevices/flipperzero-firmware`, o tu Momentum en
     `%USERPROFILE%\flipper-project\repo`). Importa `documentation/` (FAM, FAP, fbt/uFBT, JS SDK, BadUSB,
     formatos) y los ejemplos de `applications/examples/`.
3. **Añadir e indexar** trocea y embebe con `nomic-embed-text` (todo en local). La barra muestra el progreso.
   **Va lento en CPU**: ~1,4 s por fragmento. El paquete de Flipper (142 archivos, 366 fragmentos) tardó
   **~9 min**, pero es solo la primera vez. Después solo se indexa lo nuevo.
4. **Probar búsqueda** te enseña qué fragmentos recupera para una pregunta. Úsalo para comprobar que la base
   tiene lo que esperas.

**Usarla en el chat**
- Abajo, junto a Modelo y Esfuerzo, el botón **Base: Usar base: Flipper Zero** la activa o desactiva para
  tus mensajes, y la flecha ▾ elige otra o ninguna. Funciona en Scripts y en el chat de Seguridad.
- Con la base activa, cada mensaje recupera los 6 fragmentos más parecidos y se los pasa al modelo (cámbialo
  en Bases de conocimiento → **Fragmentos por pregunta**). Bajo la
  respuesta, **Ver fuentes citadas** muestra cuáles usó (las citadas, marcadas) y su texto.
- **Reindexar** rehace todos los vectores (por ejemplo, si cambias de modelo de embeddings).
- Basura dentro, basura fuera: mete los docs **oficiales** y buenos ejemplos.
- Si falta el modelo de embeddings, la app lo dice; se descarga con `ollama pull nomic-embed-text` o desde
  Estado del sistema.

---

## 5. La Nube (tu suscripción de Claude)

- Es **opcional** y está **apagada** hasta que la actives: **Ajustes (engranaje) → Nube → Cómo conectar:
  Claude Code (tu suscripción)** → **Activar el tier Nube**. Necesitas Claude Code instalado y con sesión
  iniciada (`claude auth login`); el estado aparece en «Estado del sistema».
- **Cuándo se ofrece**: cuando el estimador ve que la tarea es demasiado grande para el portátil, el aviso te
  propone **Escalar a Nube** y te enseña **qué saldría del equipo**. También puedes elegir **Nube** en el
  selector de modelo para un mensaje concreto.
- Usa **tu suscripción de Claude**, así que **comparte el mismo límite de uso** que claude.ai y Claude Code:
  lo que gastes aquí cuenta ahí. Por eso FORJA nunca escala sola: siempre lo decides tú y queda registrado.
- Sin Nube, todo lo local sigue funcionando igual.

---

## 6. El verificador de código: fíate de «Comprobar»

- **Comprobar** pasa el bloque por la herramienta **real** del lenguaje: Python (compilador), PowerShell (su
  parser), Bash (`bash -n` con Git-Bash) y JavaScript (`node --check`). Muestra cada error con su **línea**.
- **Nunca ejecuta el código**: solo lo analiza. No detecta fallos de lógica (eso se caza probando), pero sí los
  errores «tontos» de sintaxis que meten los modelos pequeños.
- Si hay errores, **«Corregir con la IA»** manda el código y los errores al modelo. El bloque corregido **se
  vuelve a comprobar solo**.
- **Fíate del resultado de «Comprobar», no de la explicación del modelo**: un modelo pequeño puede arreglar
  bien el código y aun así describir mal lo que cambió (en las pruebas habló de una «coma» que no existía).
- Si falta una herramienta (p. ej. Node), te lo dice y te ofrece instalarla, solo si confirmas.

---

## 7. Tus datos y el mantenimiento

### Dónde vive cada cosa
| Qué | Dónde |
|---|---|
| Base de datos (conversaciones, tareas, engagements, ajustes, bases de conocimiento y sus vectores) | `%APPDATA%\FORJA\forja.db` (+ copias `forja.db.bak-*` antes de cada actualización) |
| Registro (por si algo falla) | `%APPDATA%\FORJA\logs\forja.log` |
| Tus plantillas y tus imágenes de fondo | `%APPDATA%\FORJA\plantillas` · `%APPDATA%\FORJA\fondos` |
| Proyectos | `Documentos\FORJA proyectos\…` (o la carpeta que elijas) |
| Exportaciones e informes | `Documentos\FORJA exportados\` (`conversaciones`, `informes`) |
| Laboratorio de la Academia | `%USERPROFILE%\FORJA-lab\` |
| El programa | `%LOCALAPPDATA%\Programs\FORJA\FORJA.exe` |
| La clave de la API (si la usaras) | el Administrador de credenciales de Windows, nunca en la base de datos |

(Escribe `%APPDATA%\FORJA` en la barra del Explorador para llegar.) Las rutas de proyectos, exportación,
plantillas y laboratorio se cambian en **Ajustes → Rutas**.

### Re-pulir la apariencia
- **Icono de paleta** (arriba a la derecha) o **Ajustes → Apariencia** → **Estudio de Apariencia**: presets
  (FORJA oscuro/claro, Alto contraste, Fragua, Medianoche, Papel), acento y colores propios, fuente,
  densidad, fondo (liso, degradado o una imagen tuya) y un acento distinto por modo. Lo ves en vivo;
  **Aplicar** guarda y **Cancelar** (Esc) deshace. Si una combinación no se lee bien, no te deja aplicarla.
- **Ajustes → Interfaces**: la forma de cada pantalla (pestañas, selector de esfuerzo, panel de proyectos,
  resaltado de código, gate en pasos o pantalla completa, hallazgos en tabla o tarjetas, plantilla de informe,
  tareas en tablero o lista…). El botón ☀/☾ de la barra cambia claro/oscuro al momento.

### Actualizar la app tras cambios en el código
1. En la carpeta del proyecto (`Documents\forja`), doble clic en **`build.bat`**… o, para construir **e
   instalar** de una vez, abre una terminal ahí y ejecuta: `build.bat instalar`.
2. Eso genera `dist\FORJA.exe`, lo copia a `%LOCALAPPDATA%\Programs\FORJA` y rehace los accesos directos.
   Cierra FORJA antes (si está abierta, no se puede sobrescribir el `.exe`).
3. Tus datos no se tocan: al abrir la versión nueva, la base de datos se actualiza sola (con copia previa).

### Si algo va mal
- **No arranca**: verás un aviso con la ruta del registro (`%APPDATA%\FORJA\logs\forja.log`).
- **Va muy lento**: usa el tier Pequeño y esfuerzo bajo/medio; cierra apps pesadas; un solo modelo a la vez.
- **Una respuesta se corta o no llega**: pulsa **Detener** y repite con menos esfuerzo, o trocea la petición.
