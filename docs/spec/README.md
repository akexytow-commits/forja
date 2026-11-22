# FORJA — Especificación de Ingeniería de Software

> **FORJA** es un nombre de trabajo (una "forja" donde fabricas scripts, firmware e informes). Puedes
> cambiarlo en `catalogo/pantallas.yaml` → `app.nombre`. Donde leas FORJA, es tu IA local.

Este repositorio **no es documentación suelta**: es la ingeniería completa para que Claude Code (u otro
agente) construya la aplicación **sin tener que inventar nada**. Cada archivo está conectado con los demás
por **identificadores estables** (FR-###, NFR-###, MOD-###, SCR-###, BTN-###, API-###, DB-###, ST-###,
TST-###, ADR-####). El "mapa interactivo" que acompaña a este repo dibuja esas cajitas y sus flechas.

## Qué es FORJA en una frase
Una aplicación de escritorio **100% local por defecto** que enruta tus peticiones entre varios modelos de
IA (uno **Pequeño** y uno **Grande** locales, y uno de **Nube** opcional para tareas enormes), con un
control de **esfuerzo de razonamiento** (bajo / medio / extra), y tres **modos** de trabajo:
**Scripts/Firmware**, **Seguridad (Bug Bounty)** y **Organizador de Tareas**.

## Cómo leer este repositorio (orden recomendado)
1. `00-vision-y-alcance.md` — qué hacemos y qué NO hacemos. Glosario.
2. `01-restricciones-hardware.md` — tu portátil manda. Presupuesto de RAM/disco. **Leer sí o sí.**
3. `02-SRS-requisitos.md` — requisitos funcionales (FR) y no funcionales (NFR), trazables.
4. `03-arquitectura.md` — visión de cajas: shell, backend, Ollama, BBDD.
5. `04-modelo-de-modelos.md` — la capa de modelos: registro, tiers y el router.
6. `05-escalado-y-estimador.md` — cómo decide la app "esto necesita la nube".
7. `06-datos-y-bbdd.md` — esquema SQLite completo (todas las tablas locales).
8. `07-api-contrato.md` — contrato del backend local (endpoints, JSON, streaming).
9. `08-ui-navegacion.md` — el shell, los **dos selectores** (arriba = modo, abajo = modelo+esfuerzo).
10. `09`, `10`, `11` — los tres modos, módulo a módulo, **botón a botón**.
11. `12-maquinas-de-estado.md` — FSM de sesión, generación, escalado y alcance.
12. `13-protocolo-personalizacion.md` — **las preguntas que Claude Code te hará** al construir cada pantalla.
13. `14-plan-de-pruebas.md` — casos de prueba y criterios de aceptación.
14. `15-build-run-despliegue.md` — stack, instalación y ejecución en Windows.
15. `16-roadmap-y-ramas.md` — en qué orden construir (ramas de trabajo) y "Definición de Hecho".
16. `adr/` — decisiones de arquitectura con su porqué.
17. `catalogo/*.yaml` — **la fuente de verdad máquina-legible** de módulos, pantallas y botones.

## Para Claude Code (el que va a construir esto)
- **No empieces a programar hasta leer `01-restricciones-hardware.md` y `16-roadmap-y-ramas.md`.**
- La fuente de verdad de "qué pantallas y qué botones existen" son los **YAML de `catalogo/`**. Los `.md`
  explican el porqué y los contratos; los `.yaml` son la lista exacta y enlazable.
- Antes de maquetar cada pantalla, ejecuta el **Protocolo de Personalización** (`13-...md`): hazle al
  usuario las preguntas marcadas como `PREGUNTAR` para esa pantalla y aplica sus respuestas.
- Respeta los **guardarraíles del Modo Seguridad** (`10-...md`, sección "Límites"). Son requisitos, no
  recomendaciones.
- Cada botón del catálogo tiene: `accion`, `estado_antes/estado_despues`, `endpoint` (si llama al backend)
  y `prueba` (TST-###). Si un botón no tiene prueba, falta trabajo.

## Convención de identificadores
| Prefijo | Significado | Dónde se define |
|---|---|---|
| `FR-###` | Requisito funcional | `02-SRS-requisitos.md` |
| `NFR-###` | Requisito no funcional | `02-SRS-requisitos.md` |
| `MOD-###` | Módulo (componente) | `catalogo/modulos.yaml` |
| `SCR-###` | Pantalla (screen) | `catalogo/pantallas.yaml` |
| `BTN-###` | Botón / control | `catalogo/botones.yaml` |
| `API-###` | Endpoint del backend | `07-api-contrato.md` |
| `DB-###` | Tabla / entidad | `06-datos-y-bbdd.md` |
| `ST-###` | Estado de una máquina de estados | `12-maquinas-de-estado.md` |
| `TST-###` | Caso de prueba | `14-plan-de-pruebas.md` |
| `ADR-####` | Decisión de arquitectura | `adr/` |

## Estado del documento
- Versión: 0.1 (base para construir). Fecha: 2026-11-21.
- Pendiente de tu personalización: nombre de la app, estética de cada pantalla, credenciales de nube (si
  activas el tier Nube), y confirmación de las herramientas de seguridad que ya tienes licenciadas.
