# 00 — Visión y Alcance

## Visión
Una IA **propia**, de escritorio, que vive en tu portátil y funciona **sin depender de la nube** para el
día a día. Tú eliges con **dos selectores** qué cerebro usa y para qué tarea, y la app se encarga de
enrutar la petición al modelo adecuado, de razonar más o menos según el esfuerzo que pidas, y de guardar
todo (conversaciones, tareas, hallazgos) en **bases de datos locales**.

## Objetivos (lo que SÍ hace)
1. **O-1. Router de modelos.** Elegir entre un modelo **Pequeño** (rápido, 3–4B) y uno **Grande** (local,
   7–8B) con un clic, y un tier **Nube** opcional para tareas que no caben en local.
2. **O-2. Esfuerzo de razonamiento.** Controlar cuánto "piensa" el modelo: **bajo / medio / extra**
   (inspirado en el selector de esfuerzo de Claude Code, adaptado a modelos locales con "thinking").
3. **O-3. Tres modos especializados.** Cada modo es un "perfil de cerebro" con su prompt de sistema, sus
   herramientas y su interfaz:
   - **Scripts/Firmware** — escribir y explicar código, scripts, firmware.
   - **Seguridad (Bug Bounty)** — análisis y orientación sobre vulnerabilidades en objetivos **para los
     que tienes autorización**, y redacción de informes. (Ver límites en `10-...md`.)
   - **Organizador de Tareas** — escribes lo que tienes que hacer y la IA lo organiza en un plan
     (hoy / mañana / pasado) que puedes leer y editar.
4. **O-4. Escalado inteligente.** La app **estima el tamaño** de una tarea y, si es demasiado grande para
   el hardware local, te avisa y te ofrece subir al tier Nube (si lo has activado).
5. **O-5. Persistencia local.** Todo se guarda en SQLite en tu disco: conversaciones, tareas, planes,
   proyectos, hallazgos de seguridad, ajustes y un registro de auditoría.
6. **O-6. Construible por fases.** La especificación permite que Claude Code construya la app por ramas,
   empezando por lo mínimo usable y ampliando.

## No-objetivos (lo que NO hace — alcance cerrado para la v1)
- **N-1.** No es un servicio multiusuario ni en red. Es para **tu** portátil, un solo usuario, localhost.
- **N-2.** No entrena ni afina modelos. Usa modelos ya existentes vía Ollama (y nube opcional).
- **N-3.** En Modo Seguridad **no ataca ni explota de forma autónoma**, no genera malware ni exploits
  armados, y no actúa contra objetivos fuera de alcance o sin autorización. Es un **asesor/analista/
  redactor de informes**; tú ejecutas la prueba con tus herramientas y tu licencia. (Guardarraíles en
  `10-...md`.)
- **N-4.** No sincroniza con la nube por defecto. La nube es **opt-in** y solo para el tier "extra/grande".
- **N-5.** No es una herramienta de productividad general (no calendario externo, no email). El
  Organizador de Tareas es **local y propio**.

## Usuarios y contexto
- **Usuario único:** tú. Perfil técnico (escribes scripts/firmware, haces bug bounty con autorización).
- **Entorno:** Windows, portátil de gama de entrada (ver `01-...md`). Sin GPU utilizable para IA.
- **Conectividad:** normalmente offline; conexión solo cuando tú actives el tier Nube.

## Principios de diseño (guían cada decisión)
1. **Local primero, honesto con el hardware.** Nunca prometemos lo que 8 GB de RAM no pueden dar. La app
   es transparente sobre velocidad y límites.
2. **Dos selectores, cero fricción.** Cambiar de modelo/esfuerzo o de modo es un clic, siempre visible.
3. **Todo deja rastro local.** Nada se pierde; nada sale del equipo sin que tú lo pidas.
4. **La seguridad es un requisito, no un añadido.** El Modo Seguridad nace con alcance y autorización.
5. **Construible y personalizable.** El builder pregunta antes de maquetar (Protocolo de Personalización).

## Glosario
- **Tier / nivel de modelo:** categoría de capacidad: *Pequeño*, *Grande*, *Nube*.
- **Esfuerzo:** cuánto razona el modelo antes de responder (*bajo/medio/extra*). En modelos con "thinking"
  se traduce en presupuesto de pensamiento; en modelos sin thinking, en instrucciones + parámetros.
- **Modo:** perfil de trabajo (*Scripts/Firmware*, *Seguridad*, *Tareas*).
- **Router:** componente que, dados (modo, tier, esfuerzo), elige el modelo concreto y sus parámetros.
- **Escalado:** pasar una tarea del local a la Nube por tamaño/complejidad.
- **Alcance (scope):** conjunto de objetivos autorizados en una sesión de Seguridad.
- **Sidecar:** el backend (Python/FastAPI) que arranca junto a la ventana de la app.
- **Ollama:** el motor local que sirve los modelos con una API compatible OpenAI en `localhost:11434`.
