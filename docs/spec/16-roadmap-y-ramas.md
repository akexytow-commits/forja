# 16 — Roadmap y Ramas de Trabajo (para Claude Code)

Orden de construcción por **ramas**. Cada rama tiene una **Definición de Hecho (DoD)**: no se pasa a la
siguiente sin cumplirla (pruebas incluidas). Construir en este orden da algo usable cuanto antes y evita
dependencias rotas.

## Rama 0 — Andamiaje y salud
- Crear estructura (`15-...md`), backend FastAPI vacío con API-001 `/salud`, conexión a SQLite y
  migración `001_init.sql` (todas las tablas de `06-...md`), ventana pywebview que carga `ui/index.html`.
- **DoD:** la app arranca, abre ventana, `/salud` responde, BBDD creada. TST-001, TST-060 (parcial).

## Rama 1 — Router + Ollama + chat básico (un modo)
- MOD-010 (tabla de resolución), MOD-011 (gestor Ollama, un modelo a la vez, descarga guiada), MOD-013
  (chat con streaming SSE), SCR-001 (shell con los dos selectores) y SCR-010 (chat Scripts) mínimo.
- **DoD:** puedes chatear en Modo Scripts con tier Pequeño y ver streaming; cambiar de tier recarga
  modelo. TST-002/003/004/005/006, TST-020.

## Rama 2 — Estimador + escalado
- MOD-050 (estimador y veredicto), SCR-006 (aviso), integración en el flujo de chat (ST-010/ST-050).
  Cliente Nube (MOD-012) tras bandera en Ajustes (puede quedar "simulado" hasta que configures proveedor).
- **DoD:** tareas grandes disparan el aviso; sin Nube, ofrece troceo; con Nube, registra auditoría.
  TST-010/011/012, TST-023.

## Rama 3 — Modo Tareas (el "más normal")
- MOD-040 completo: captura (SCR-030), organizar con IA (API-042), plan por días editable (SCR-031),
  persistencia. Protagonismo del esfuerzo medio/extra.
- **DoD:** escribes tareas, las organiza por días, editas y persiste. TST-040..044.

## Rama 4 — Modo Seguridad (con guardarraíles primero)
- **Primero** los guardarraíles y el gate (ST-030, G-1..G-5) y su auditoría (MOD-080). Luego SCR-020/021/
  022/023 y las API-050..053. Integraciones externas (API-054) solo si decides, y con confirmación.
- **DoD:** el gate bloquea sin autorización; análisis crea findings; informe une enfoques; la IA rechaza
  lo que cruza G-3. TST-030..035.

## Rama 4b — Academia de Seguridad (aprender estilo HTB/THM)
- MOD-090: Enfoque Ofensivo/Defensivo, currículo Ruta→Módulo→Lección (DB-009..011), tutor guiado con
  pistas progresivas, XP/rangos y catálogo de herramientas (SCR-024/025/026). Reutiliza los guardarraíles
  de la Rama 4 y añade el **gate de laboratorio autorizado** (FR-038, BTN-087). Ver `18-...md`.
- **DoD:** sin declarar laboratorio no se guían ejercicios; rutas navegables; pistas progresivas; XP
  persiste. TST-035..039.
- **Extensión — Laboratorio Linux (MOD-091, doc 19):** construir **WSL2 y attack box hospedado (ambos)**,
  con **selector de backend activo** (SCR-027, BTN-092) y elección por laboratorio; VirtualBox opcional al
  final. Botón "Abrir Linux del laboratorio" con contexto; instalación guiada con confirmación. TST-070..072.
- **Extensión — Copiloto de Laboratorio (MOD-091, doc 19 §Copiloto):** panel de asistente en vivo que da el
  siguiente paso, resuelve dudas y explica comandos/salidas (reutiliza el tutor MOD-090/MOD-013). TST-075/076.

## Rama 5 — Proyectos, plantillas, export, telemetría, pulido
- Proyectos (SCR-011), plantillas (BTN-032), export (API-062), Ajustes completos (SCR-007), temas.
- **Telemetría de generación (MOD-013, doc 22):** indicador en vivo estilo Claude Code (tiempo, tokens,
  tok/s, ETA, fase pensando/respondiendo) + ver/plegar razonamiento (BTN-100). Especialmente útil en CPU.
- **DoD:** TST-021/022/061/062/063, TST-077..079, y los no funcionales TST-100..102.

## Rama 6 — Personalización de interfaces (contigo)
- Ejecutar el Protocolo de Personalización (`13-...md`) pantalla por pantalla, guardando tus elecciones en
  `settings` (`ui.*`), y retocar la estética según tus respuestas.
- **DoD:** cada pantalla refleja tus decisiones; se puede re-pulir sin perder lo elegido.

## Rama 6b — Verificador de código (MOD-110, doc 23)
- Botón "Comprobar" en los bloques de código (SCR-010) que ejecuta linters/compiladores **estáticos**
  (py_compile/ruff, parser PowerShell, `bash -n`/shellcheck, `node --check`), **sin ejecutar el código**;
  detección de lenguaje y degradación si falta la herramienta. "Corregir con la IA" opcional (BTN-102).
- **DoD:** Comprobar marca errores con línea en Python/PowerShell sin ejecutar nada; corrige opcionalmente.
  TST-080..082.

## Rama 7 — Empaquetado
- PyInstaller a `.exe`, detección de Ollama ausente, primer arranque limpio.
- **DoD:** doble clic arranca; si falta Ollama/modelo, SCR-008 guía.

## Rama 8 — Estudio de Apariencia (la cara de la app, AL FINAL)
- MOD-100 (doc 20): presets de tema, color/acento con contraste, tipografía, densidad, fondo/imagen y vista
  previa en vivo; persiste en `ui.*`. Se hace al final, cuando el resto ya funciona.
- **DoD:** aplicar un tema cambia toda la app y persiste, con contraste legible. TST-073.

## Mejora futura (fuera de v1)
- Tauri como shell (ADR-0002, alternativa ligera-nativa), llama.cpp directo para exprimir rendimiento,
  más modos, integración MCP más rica en Seguridad (siempre con los guardarraíles).

## Cómo usar los catálogos al construir
- `catalogo/modulos.yaml` → crea un archivo/componente por `MOD-###` con sus dependencias.
- `catalogo/pantallas.yaml` → una vista por `SCR-###`; respeta `siempre_visible` en los selectores.
- `catalogo/botones.yaml` → implementa cada `BTN-###`: su `accion`, su `endpoint` y su `prueba`. Si un
  botón del catálogo no está implementado o no tiene prueba verde, la rama no está hecha.
