# 18 — Academia: Aprender Seguridad dentro de FORJA (ingeniería inversa de HTB / TryHackMe)

Añade al **Modo Seguridad** una actividad de **Aprendizaje** al estilo de **Hack The Box (HTB)** y
**TryHackMe (THM)**: FORJA actúa como **tutor/coach** que te guía por rutas, lecciones y laboratorios.
Aquí va qué patrones copiar, de qué plataforma, el mecanismo a replicar y cómo aterriza con IDs.

> Igual que antes, "ingeniería inversa" = replicar el **comportamiento pedagógico y la estructura** de esas
> plataformas con nuestros propios medios (el modelo local/nube como tutor + SQLite). No se copia su
> contenido ni su software.

## Dónde encaja: Enfoque y Actividad dentro de Seguridad
El Modo Seguridad pasa a tener dos ejes (tu idea de "ofensivo/defensivo" + "aprender"):
- **Enfoque** (nuevo selector): **Ofensivo** (red team: encontrar y explotar en laboratorio) o
  **Defensivo** (blue team: detectar y responder). Las plataformas de referencia separan ambos desde el
  inicio y recomiendan elegir dirección "con los ojos abiertos". → **FR-035**.
- **Actividad**: **Trabajo** (bug bounty autorizado — lo que ya existe en `10-...md`) o **Aprender**
  (la Academia de este documento). Puedes aprender en Ofensivo y en Defensivo.

El módulo nuevo es **MOD-090 Academia de Seguridad** (tutor + currículo local), dentro de la pestaña
Seguridad.

---

## Patrones a copiar

### A1 · Estructura Ruta → Módulo → Lección (HTB "Paths→Modules→Sections", THM "Paths→Modules→Rooms")
- **Mecanismo:** el aprendizaje se organiza en tres niveles: una **Ruta** agrupa **Módulos** sobre un tema,
  y cada módulo se divide en **lecciones/secciones** pequeñas, completables de una sentada.
- **En FORJA:** un **currículo local** (tablas DB-009/009b/009c) que el tutor recorre contigo. La Ruta marca
  el orden lógico; tú avanzas lección a lección. → **FR-036**.

### A2 · Dos tipos de ruta: por Habilidad y por Rol de trabajo (HTB "Skill Paths" vs "Job-Role Paths")
- **Mecanismo:** rutas centradas en una **habilidad** concreta (p. ej. "Fundamentos de red") y rutas
  centradas en un **rol** (p. ej. "Pentester Jr", "Analista SOC", "Red Teamer", "Bug Bounty Hunter").
- **En FORJA:** `learning_paths.tipo = skill | rol`. En SCR-024 eliges una u otra. → **FR-036**.

### A3 · Guiado + interactivo, nada de lectura pasiva (filosofía HTB/THM)
- **Mecanismo:** cada lección = **teoría breve** + **ejercicio práctico** (en un laboratorio) + una
  **pregunta** que compruebas; los módulos terminan con una **evaluación** que combina lo aprendido.
- **En FORJA:** cada `learning_section` tiene `tipo = teoria | interactiva`. En las interactivas, el tutor
  propone un ejercicio en tu laboratorio y **BTN-085 Comprobar respuesta** valida lo que encontraste.
  Al final del módulo, una **evaluación**. → **FR-037**.

### A4 · Sistema de pistas progresivas (el "dame una pista" de las salas)
- **Mecanismo:** si te atascas, pides pista y recibes ayuda **graduada**: primero un empujón, luego una
  dirección, luego más detalle — para que aprendas, no para que te den la solución masticada.
- **En FORJA:** **BTN-084 Pedir pista** escala por niveles (`pistas_usadas` cuenta cuántas gastaste; afecta
  al XP). El tutor nunca salta directo a un exploit listo para pegar. → **FR-037**.

### A5 · Progreso, XP y rangos (HTB "XP system", gamificación THM)
- **Mecanismo:** completar lecciones/evaluaciones da **XP acumulativo**; hay dificultad por módulo
  (Fundamental/Fácil/Medio/Difícil) y el perfil muestra tu avance y racha. Motiva y da sensación de
  progresión.
- **En FORJA:** `learning_progress` guarda estado + XP; SCR-026 muestra XP, rango, racha y rutas
  completadas. XP configurable por dificultad. → **FR-039**.

### A6 · Catálogo de herramientas / árbol de habilidades ("coge todas las herramientas de ellos")
- **Mecanismo:** cada ruta enseña un **conjunto de herramientas** estándar (reconocimiento de red, proxy
  web, análisis de tráfico, etc.) y conceptos; el aprendiz ve qué herramienta aprende y en qué lección.
- **En FORJA:** tabla **DB-011 `tool_catalog`**: nombre de la herramienta, **para qué sirve**, enfoque
  (ofensivo/defensivo) y en qué lección aparece. Se muestra como **árbol de habilidades/herramientas**
  (SCR-026, BTN-088). El tutor las explica **conceptualmente** y las practicas en el laboratorio; FORJA no
  las ejecuta por ti. → **FR-039**.
  - *Semilla recomendada del catálogo* (conceptos que las plataformas enseñan primero): redes y protocolos,
    Linux/Windows/Active Directory básicos, reconocimiento, web (el Top 10 de OWASP), proxy web, análisis de
    tráfico, y por el lado defensivo: SIEM, análisis de logs, respuesta a incidentes, forense. El orden
    recomendado empieza por **redes** porque todo lo demás lo asume.

### A7 · Rutas de ejemplo (semilla del currículo)
Estructura inicial sugerida para `learning_paths` (editable; el contenido lo genera el tutor):
- **Ofensivo:** Fundamentos (redes → Linux/Windows → web) → Pentester Jr → Red Teamer → Bug Bounty
  (enlaza con el flujo de `10-...md`).
- **Defensivo:** Fundamentos → Analista SOC Nivel 1 → Respuesta a incidentes / Forense.
- Un intro "elige dirección" antes de especializarte (como el intro ofensivo/defensivo de THM).

---

## Límites de la Academia (guardarraíles — coherentes con ADR-0005 / `10-...md`)
- 
## Qué NO copiamos
- Las **máquinas/labs alojados** de HTB/THM (requieren su infraestructura y cuenta): FORJA no los aloja; te
  **acompaña** mientras tú practicas en ellos o en tu laboratorio local. 
- Su **contenido propietario**: el currículo de FORJA es una estructura propia que el tutor rellena; las
  rutas de ejemplo son orientativas.

## Trazabilidad (lo que este doc añade)
| Patrón | Fuente | Requisito | Pantalla/Botón | BBDD | Prueba |
|---|---|---|---|---|---|
| A1 Ruta→Módulo→Lección | HTB/THM | FR-036 | SCR-024/025 | DB-009/009b/009c | TST-036 |
| A2 Rutas habilidad/rol | HTB | FR-036 | SCR-024, BTN-082 | DB-009 | TST-036 |
| A3 Guiado+interactivo | HTB/THM | FR-037 | SCR-025, BTN-085/086 | DB-009c | TST-037 |
| A4 Pistas progresivas | HTB/THM | FR-037 | BTN-084 | DB-010 | TST-037 |
| A5 XP/rangos | HTB/THM | FR-039 | SCR-026 | DB-010 | TST-039 |
| A6 Catálogo herramientas | HTB/THM | FR-039 | SCR-026, BTN-088 | DB-011 | TST-039 |
| Enfoque Ofensivo/Defensivo | THM | FR-035 | SCR-024, BTN-080/081 | — | TST-035 |
| Gate de laboratorio | guardarraíl | FR-038 | BTN-087 | DB-008 | TST-038 |

## Orden de construcción
Nueva **Rama 4b — Academia de Seguridad**, después de la Rama 4 (que trae los guardarraíles y el gate del
Modo Seguridad). La Academia reutiliza esos guardarraíles y añade el gate de laboratorio (L-A1).
