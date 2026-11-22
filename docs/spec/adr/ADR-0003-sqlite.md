# ADR-0003 — Persistencia: SQLite local

**Estado:** aceptada · **Fecha:** 2026-11-21

## Contexto
Requisito de que **todo** viva en el ordenador, sin nube, monousuario. Hace falta guardar conversaciones,
tareas, planes, proyectos, hallazgos, ajustes y auditoría.

## Decisión
**SQLite** en un único fichero `forja.db`. Incluido en Python (sin servidor), transaccional, fiable y
fácil de respaldar (copiar el fichero). Acceso con SQLAlchemy (o `sqlite3`). Migraciones incrementales con
`schema_version`.

## Alternativas consideradas
- **Ficheros JSON sueltos:** simples pero frágiles para relaciones y consultas (plan por días, findings).
- **Postgres/MySQL:** sobredimensionado; exige servidor; contrario a "local y ligero".

## Consecuencias
- +Cero infraestructura; respaldo trivial; consultas relacionales para planes y hallazgos.
- +Encaja con el presupuesto de recursos.
- −Un solo escritor a la vez (irrelevante en monousuario). La clave de Nube NO va aquí en claro: va en
  keyring (Windows Credential Manager). (NFR-010)
