# 06 — Datos y Bases de Datos Locales (MOD-060)

**Todo en local**, en un único fichero SQLite `forja.db` (carpeta de datos de la app; ver `15-...md`).
Motor: SQLite 3 (incluido en Python). Acceso: SQLAlchemy recomendado (o `sqlite3` directo). Migraciones:
tabla `schema_version` + scripts incrementales.

> Convención: claves primarias `id` enteras autoincrement salvo que se diga UUID. Fechas en ISO-8601 texto
> (`YYYY-MM-DDTHH:MM:SS`). Booleanos como 0/1.

## Diagrama de relaciones (texto)
```
projects (DB-004) 1───∞ conversations (DB-002) 1───∞ messages (DB-003)
conversations ∞───1 modes(implícito por columna 'modo')
engagements (DB-006) 1───∞ findings (DB-006b)
task_lists (DB-005) 1───∞ tasks (DB-005b) 1───∞ plan_items(por día)
settings (DB-001)   models (DB-007)   audit_log (DB-008)
```

## DB-001 `settings` — ajustes clave/valor
| columna | tipo | notas |
|---|---|---|
| key | TEXT PK | p. ej. `nube.activada`, `nube.backend` (=`claude_code` por defecto), `nube.claude_bin`, `nube.modelo`, `tema`, `carpeta_proyectos`, `umbral.complejidad_nube`, `plan.capacidad_dia_min` (carga del día, FR-047), `seguridad.enfoque` (`ofensivo`|`defensivo`), `lab.backend` (`wsl`|`attackbox`|`virtualbox`), `lab.distro`, `lab.working_dir`, `lab.attackbox_url`, `ui.tema`, `ui.acento`, `ui.fuente`, `ui.densidad`, `ui.fondo`, `ui.acento_por_modo`. (Para el backend alternativo `api`: `nube.endpoint`, `nube.api_key_ref`.) |
| value | TEXT | JSON serializado si hace falta |
| updated_at | TEXT | |
> La API key de Nube **no** se guarda en claro si se puede evitar: usar el almacén de credenciales del
> SO (Windows Credential Manager vía `keyring`) y guardar aquí solo una referencia. (NFR-010)

## DB-002 `conversations` — un hilo por (modo) y opcionalmente por proyecto
| columna | tipo | notas |
|---|---|---|
| id | INTEGER PK | |
| modo | TEXT | `scripts`|`seguridad`|`tareas` |
| project_id | INTEGER FK→projects | nullable |
| engagement_id | INTEGER FK→engagements | nullable (solo seguridad) |
| titulo | TEXT | autogenerado del primer mensaje |
| created_at / updated_at | TEXT | |
| archivada | INTEGER | 0/1 |

## DB-003 `messages`
| columna | tipo | notas |
|---|---|---|
| id | INTEGER PK | |
| conversation_id | INTEGER FK | |
| rol | TEXT | `system`|`user`|`assistant`|`tool` |
| contenido | TEXT | |
| tier | TEXT | tier usado al generar (trazabilidad) |
| esfuerzo | TEXT | |
| modelo | TEXT | alias/etiqueta real usada |
| thinking | TEXT | contenido de razonamiento si lo hubo (nullable) |
| tokens_in / tokens_out | INTEGER | para métricas y estimador |
| created_at | TEXT | |

## DB-004 `projects` (Modo Scripts/Firmware)
| columna | tipo | notas |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT | |
| carpeta | TEXT | ruta local donde guardar archivos del proyecto |
| descripcion | TEXT | |
| created_at | TEXT | |

## DB-005 `task_lists` y DB-005b `tasks` (Modo Tareas)
`task_lists`: id, nombre, created_at.
`tasks`:
| columna | tipo | notas |
|---|---|---|
| id | INTEGER PK | |
| list_id | INTEGER FK | |
| texto | TEXT | lo que escribiste |
| prioridad | INTEGER | 1 (alta) … 5 |
| estimacion_min | INTEGER | minutos estimados (opcional) |
| dia_asignado | TEXT | fecha ISO (hoy/mañana/…) o NULL si sin asignar |
| orden | INTEGER | orden dentro del día |
| estado | TEXT | `pendiente`|`en_curso`|`hecha` |
| origen | TEXT | `usuario`|`ia`|`troceo`|`idea` (si viene del estimador o del mapa de ideas) |
| fijada | INTEGER | 0/1 — si 1, Reorganizar no la mueve (FR-046, BTN-058) |
| parent_id | INTEGER FK→tasks | subtarea anidada bajo otra tarea (FR-048, BTN-059); NULL si es raíz |
| created_at / updated_at | TEXT | |

> El "plan por días" (hoy/mañana/pasado) es una **vista** sobre `tasks` agrupando por `dia_asignado` y
> ordenando por `orden`. No necesita tabla propia.

## DB-005c `ideas` y DB-005d `idea_links` (Mapa de ideas — opcional/fase 2, FR-049)
`ideas`: id, list_id (nullable), texto, x, y (posición en el lienzo), created_at.
`idea_links`: id, origen_id FK→ideas, destino_id FK→ideas, etiqueta (opcional).
> Opcional. Si no se construye la fase 2, el "mapa de ideas" se cubre con subtareas anidadas (DB-005b.parent_id).

## DB-006 `engagements` y DB-006b `findings` (Modo Seguridad)
`engagements` (un programa/objetivo autorizado):
| columna | tipo | notas |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT | p. ej. "Programa X - HackerOne" |
| alcance | TEXT | dominios/activos en alcance (texto/JSON) |
| autorizacion_confirmada | INTEGER | 0/1 — **debe ser 1 para operar** (ST-030) |
| notas | TEXT | |
| created_at | TEXT | |

`findings`:
| columna | tipo | notas |
|---|---|---|
| id | INTEGER PK | |
| engagement_id | INTEGER FK | |
| titulo | TEXT | |
| clase | TEXT | clase/categoría de la posible vulnerabilidad (etiqueta) |
| severidad_estim | TEXT | info/baja/media/alta/crítica (estimada, a validar por ti) |
| donde_enfocar | TEXT | orientación de la IA: dónde mirar |
| estado | TEXT | `idea`|`validado_por_usuario`|`en_informe`|`reportado` |
| evidencia_usuario | TEXT | lo que TÚ validaste/aportaste (texto/rutas) |
| informe_md | TEXT | borrador de informe generado |
| created_at / updated_at | TEXT | |

## DB-009 Academia: `learning_paths` / `learning_modules` / `learning_sections` (MOD-090, FR-036)
`learning_paths`: id, nombre, enfoque (`ofensivo`|`defensivo`), tipo (`skill`|`rol`), descripcion.
`learning_modules` (DB-009b): id, path_id FK, nombre, dificultad (`fundamental`|`facil`|`medio`|`dificil`), orden.
`learning_sections` (DB-009c): id, module_id FK, titulo, tipo (`teoria`|`interactiva`), contenido_guia, orden.
> El contenido lo genera el tutor (MOD-013) al abrir la lección; estas tablas son la **estructura** del
> currículo, editable. Rutas de ejemplo (semilla) en `18-...md` §A7.

## DB-010 `learning_progress` (FR-039)
| columna | tipo | notas |
|---|---|---|
| id | INTEGER PK | |
| section_id | INTEGER FK→learning_sections | |
| estado | TEXT | `pendiente`|`en_curso`|`completada` |
| xp | INTEGER | XP otorgado (por dificultad, menos si usaste pistas) |
| pistas_usadas | INTEGER | nº de pistas progresivas gastadas (BTN-084) |
| completed_at | TEXT | |
> El perfil/rango se deriva sumando `xp`; ajuste `settings.academia.xp_por_dificultad`.

## DB-011 `tool_catalog` — catálogo de herramientas/habilidades (FR-039, A6)
| columna | tipo | notas |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT | nombre de la herramienta/habilidad |
| para_que | TEXT | para qué sirve (explicación conceptual) |
| enfoque | TEXT | `ofensivo`|`defensivo`|`ambos` |
| seccion_id | INTEGER FK→learning_sections | en qué lección aparece (nullable) |
> FORJA explica las herramientas conceptualmente y las practicas en tu laboratorio; **no las ejecuta por ti**.

## DB-007 `models` — registro de modelos
| columna | tipo | notas |
|---|---|---|
| alias | TEXT PK | p. ej. `pequeno-codigo` |
| tier | TEXT | pequeno/grande/nube |
| etiqueta | TEXT | etiqueta Ollama o id de proveedor nube |
| tamano_disco_mb | INTEGER | informativo |
| thinking | INTEGER | 0/1 |
| instalado | INTEGER | 0/1 (si está en Ollama) |
| notas | TEXT | |

## DB-008 `audit_log` — auditoría local (MOD-080)
| columna | tipo | notas |
|---|---|---|
| id | INTEGER PK | |
| ts | TEXT | |
| tipo | TEXT | `cambio_alcance`|`escalado_nube`|`accion_seguridad_confirmada`|`descarga_modelo`|`export` |
| detalle | TEXT | JSON con lo relevante |
> Sirve para que siempre puedas reconstruir qué se hizo, especialmente en Seguridad y en envíos a Nube.

## Migraciones
- `schema_version(version INTEGER)`. Al arrancar, MOD-060 compara y aplica scripts `migrations/00X_*.sql`
  en orden. Nunca borrar datos del usuario en una migración sin copia de seguridad del fichero `.db`.
