# 08 — UI y Navegación (el Shell y los dos selectores)

Fuente de verdad de pantallas/botones: `catalogo/pantallas.yaml` y `catalogo/botones.yaml`. Aquí va la
estructura y el comportamiento. La **estética** concreta la decides tú en el Protocolo de Personalización
(`13-...md`); aquí solo se fija la **función**.

## Layout maestro (SCR-001 "Shell")
Tu petición: **dos selectores, uno arriba y otro abajo.**

```
┌───────────────────────────────────────────────────────────┐
│  [ Scripts/Firmware ] [ Seguridad ] [ Tareas ]   (SELECTOR  │  ← SELECTOR SUPERIOR = MODO (BTN-010..012)
│                                                   SUPERIOR) │
├───────────────────────────────────────────────────────────┤
│                                                             │
│   Área de trabajo del modo activo                           │
│   (chat + paneles propios de cada modo)                     │
│                                                             │
│                                                             │
├───────────────────────────────────────────────────────────┤
│  [ escribe aquí ................................ ] [▶]      │  ← compositor
│  Modelo: (•)Pequeño ( )Grande ( )Nube   Esfuerzo:[bajo|medio|extra]  │  ← SELECTOR INFERIOR (BTN-020..025)
└───────────────────────────────────────────────────────────┘
```

- **SELECTOR SUPERIOR = Modo.** Pestañas siempre visibles (FR-010). Cambiar de modo cambia el área de
  trabajo y el hilo (cada modo tiene su conversación, FR-012). "De momento 2 pestañas" → arrancamos con
  Scripts y Seguridad visibles y **Tareas** como tercera pestaña (la pediste explícitamente). Las pestañas
  salen de `catalogo/pantallas.yaml`, así que ampliar es trivial.
- **SELECTOR INFERIOR = Modelo + Esfuerzo.** Siempre visible junto al compositor (FR-003):
  - Modelo (tier): Pequeño | Grande | Nube (Nube deshabilitado si no está activada, FR-006).
  - Esfuerzo: bajo | medio | extra. En Modo Tareas, el esfuerzo medio/extra es el protagonista (planificar).
- El estado (modo, tier, esfuerzo) es **global y persistente** entre arranques (se recuerda el último).

## Pantallas (resumen; detalle en catálogo y en 09/10/11)
| SCR | Nombre | Dónde | Módulo |
|---|---|---|---|
| SCR-001 | Shell (layout + 2 selectores) | raíz | MOD-001 |
| SCR-002 | Selector de modelo/esfuerzo (el panel inferior) | dentro del shell | MOD-010 |
| SCR-006 | Aviso de escalado a Nube | modal/inline | MOD-050 |
| SCR-007 | Ajustes | menú | MOD-070 |
| SCR-008 | Estado del sistema / arranque (Ollama, modelos) | primera vez / error | MOD-011 |
| SCR-010 | Chat Scripts/Firmware | pestaña Scripts | MOD-020 |
| SCR-011 | Proyectos | pestaña Scripts | MOD-020 |
| SCR-020 | Alcance y autorización (gate) | pestaña Seguridad (entrada) | MOD-030 |
| SCR-021 | Análisis de reconocimiento | pestaña Seguridad | MOD-030 |
| SCR-022 | Redactor de informe | pestaña Seguridad | MOD-030 |
| SCR-023 | Hallazgos (lista) | pestaña Seguridad | MOD-030 |
| SCR-030 | Captura de tareas | pestaña Tareas | MOD-040 |
| SCR-031 | Plan por días (hoy/mañana/pasado) | pestaña Tareas | MOD-040 |

## Reglas de navegación
1. Al arrancar: MOD-001 llama a API-001. Si Ollama está caído o faltan modelos → SCR-008 guía antes de
   entrar al shell. (NFR-020)
2. Entrar en pestaña **Seguridad** sin engagement con autorización confirmada → te lleva a **SCR-020**
   (gate). No se puede chatear en Seguridad sin pasar el gate (ST-030, FR-030).
3. El selector inferior **Nube** deshabilitado → tooltip "Actívala en Ajustes" (enlace a SCR-007).
4. Cambiar de tier/modelo que implique recarga → feedback "Cambiando de modelo…" (evento SSE `inicio`).
5. El compositor (campo de texto + ▶) es común a los tres modos; su comportamiento varía por modo
   (en Seguridad, por ejemplo, la entrada se trata como "datos a analizar", no como orden de ataque).

## Estados visuales que la UI debe cubrir (para cada modo)
- vacío (sin conversación) · generando (streaming + thinking plegable) · error (Ollama caído, modelo
  faltante) · cambiando de modelo · esperando confirmación de herramienta · aviso de escalado.

## Accesibilidad / idioma
- Español por defecto; textos en un único `strings.es.json` (NFR-050). Objetivos de clic ≥ 40px.
- Tema claro/oscuro (Ajustes). El Protocolo de Personalización recoge tu preferencia estética.
