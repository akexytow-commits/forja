# 09 — Modo Scripts / Firmware (MOD-020)

Perfil de "ingeniero de código" para escribir, explicar y depurar scripts y firmware. Pensado para tareas
pequeñas/medianas en local y para proponer la Nube cuando el proyecto es enorme.

## Objetivo del modo
Que escribas lo que necesitas (un script, una función, un firmware base) y la IA lo produzca, explique y
guarde en un proyecto local, con bloques de código copiables.

## Prompt de sistema (resumen; versión final en `prompts/scripts.txt`)
- Rol: asistente de programación en español; experto en Python, Bash, PowerShell, C/C++ embebido y
  firmware (incl. plataformas tipo microcontrolador/Flipper).
- Reglas: entrega código correcto y comentado; si falta información, pregunta antes de inventar; marca
  suposiciones; para tareas grandes, propone trocear o escalar (coordina con MOD-050).
- Formato: explicación breve → bloque(s) de código → cómo probarlo. Nada de relleno.
- Contexto inyectado: tier/esfuerzo actual y recordatorio de que corre en local con recursos limitados
  (sugerir soluciones eficientes).

## Herramientas (tool-calling) habilitadas
- `guardar_archivo(nombre, contenido)` → API-031. **Requiere confirmación** del usuario (modal) antes de
  escribir en disco. Nunca escribe fuera de la carpeta del proyecto activo.
- (futuro) `leer_archivo_proyecto(nombre)` para iterar sobre código existente.

## Pantallas y botones
### SCR-010 — Chat Scripts/Firmware
- Chat con streaming. Bloques de código con resaltado.
- **BTN-030 Copiar** (por bloque de código) → copia al portapapeles.
- **BTN-031 Guardar a archivo** (por bloque) → abre modal nombre → API-031 (confirmación).
- **BTN-032 Plantillas** → menú: "Script Python", "Script Bash", "Script PowerShell", "Firmware base".
  Inserta un andamiaje inicial en el compositor. Las plantillas viven en `plantillas/` (editable).
- **BTN-033 Nuevo hilo** → crea conversación (API-021) en modo scripts.
- Si el estimador marca grande → banner con BTN-028/029 (escalar/local troceado).

### SCR-011 — Proyectos
- Lista de proyectos (DB-004).
- **BTN-034 Nuevo proyecto** → nombre + carpeta local (selector de carpeta del SO).
- **BTN-035 Abrir carpeta** → abre el explorador en la carpeta del proyecto.
- **BTN-036 Asociar hilo a proyecto** → vincula la conversación actual a un proyecto.

## Flujos clave
1. **Script corto (local):** escribes → (estimador: cabe) → genera en Pequeño/código → copias o guardas.
2. **Firmware grande:** escribes "firmware completo de…" → estimador: RECOMENDADO_NUBE → SCR-006 →
   eliges Nube (si activa) o troceo (crea plan en Modo Tareas).
3. **Iterar:** guardas a archivo, pides cambios, vuelves a guardar (confirmación si sobrescribe).

## Pruebas asociadas
TST-020 (generación básica), TST-021 (guardar archivo con confirmación), TST-022 (plantillas),
TST-023 (escalado por tarea grande). Ver `14-...md`.
