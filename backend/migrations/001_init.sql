-- 001_init: todas las tablas de 06-datos-y-bbdd.md (DB-001..DB-008)
-- Fechas ISO-8601 en hora local; booleanos 0/1.

-- DB-001 settings
CREATE TABLE settings (
  key        TEXT PRIMARY KEY,
  value      TEXT,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

-- DB-004 projects
CREATE TABLE projects (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre      TEXT NOT NULL,
  carpeta     TEXT NOT NULL,
  descripcion TEXT,
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

-- DB-006 engagements
CREATE TABLE engagements (
  id                      INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre                  TEXT NOT NULL,
  alcance                 TEXT NOT NULL DEFAULT '',
  autorizacion_confirmada INTEGER NOT NULL DEFAULT 0 CHECK (autorizacion_confirmada IN (0,1)),
  notas                   TEXT,
  created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

-- DB-002 conversations
CREATE TABLE conversations (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  modo          TEXT NOT NULL CHECK (modo IN ('scripts','seguridad','tareas')),
  project_id    INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  engagement_id INTEGER REFERENCES engagements(id) ON DELETE SET NULL,
  titulo        TEXT,
  created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  archivada     INTEGER NOT NULL DEFAULT 0 CHECK (archivada IN (0,1))
);
CREATE INDEX idx_conversations_modo ON conversations(modo, archivada, updated_at);

-- DB-003 messages
CREATE TABLE messages (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  rol             TEXT NOT NULL CHECK (rol IN ('system','user','assistant','tool')),
  contenido       TEXT NOT NULL,
  tier            TEXT,
  esfuerzo        TEXT,
  modelo          TEXT,
  thinking        TEXT,
  tokens_in       INTEGER,
  tokens_out      INTEGER,
  created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);
CREATE INDEX idx_messages_conv ON messages(conversation_id, id);

-- DB-005 task_lists / DB-005b tasks
CREATE TABLE task_lists (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre     TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);
CREATE TABLE tasks (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  list_id        INTEGER NOT NULL REFERENCES task_lists(id) ON DELETE CASCADE,
  texto          TEXT NOT NULL,
  prioridad      INTEGER NOT NULL DEFAULT 3 CHECK (prioridad BETWEEN 1 AND 5),
  estimacion_min INTEGER,
  dia_asignado   TEXT,
  orden          INTEGER NOT NULL DEFAULT 0,
  estado         TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','en_curso','hecha')),
  origen         TEXT NOT NULL DEFAULT 'usuario' CHECK (origen IN ('usuario','ia','troceo')),
  created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);
CREATE INDEX idx_tasks_plan ON tasks(list_id, dia_asignado, orden);

-- DB-006b findings
CREATE TABLE findings (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_id     INTEGER NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
  titulo            TEXT NOT NULL,
  clase             TEXT,
  severidad_estim   TEXT CHECK (severidad_estim IN ('info','baja','media','alta','critica') OR severidad_estim IS NULL),
  donde_enfocar     TEXT,
  estado            TEXT NOT NULL DEFAULT 'idea'
                    CHECK (estado IN ('idea','validado_por_usuario','en_informe','reportado')),
  evidencia_usuario TEXT,
  informe_md        TEXT,
  created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);

-- DB-007 models (registro)
CREATE TABLE models (
  alias           TEXT PRIMARY KEY,
  tier            TEXT NOT NULL CHECK (tier IN ('pequeno','grande','nube')),
  etiqueta        TEXT NOT NULL,
  tamano_disco_mb INTEGER,
  thinking        INTEGER NOT NULL DEFAULT 0 CHECK (thinking IN (0,1)),
  instalado       INTEGER NOT NULL DEFAULT 0 CHECK (instalado IN (0,1)),
  notas           TEXT
);

-- DB-008 audit_log
CREATE TABLE audit_log (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  tipo    TEXT NOT NULL CHECK (tipo IN ('cambio_alcance','escalado_nube','accion_seguridad_confirmada','descarga_modelo','export')),
  detalle TEXT
);

-- Registro de modelos por defecto (04-modelo-de-modelos.md). Editable más adelante en Ajustes.
INSERT INTO models (alias, tier, etiqueta, tamano_disco_mb, thinking, notas) VALUES
  ('pequeno-general', 'pequeno', 'qwen3:4b',          2500, 1, 'chat, tareas, scripts cortos'),
  ('pequeno-codigo',  'pequeno', 'qwen2.5-coder:3b',  1900, 0, 'snippets y scripts rápidos'),
  ('grande-general',  'grande',  'qwen3:8b',          5200, 1, 'más calidad; va justo de RAM'),
  ('grande-codigo',   'grande',  'qwen2.5-coder:7b',  4700, 0, 'scripts/firmware de más enjundia'),
  ('nube-frontera',   'nube',    '',                  NULL, 0, 'configurable: tu proveedor (Rama 2)');

-- Ajustes por defecto + respuestas del Protocolo de Personalización (13-...md, preguntas globales)
INSERT INTO settings (key, value) VALUES
  ('ui.nombre_app',        'FORJA'),
  ('ui.tema',              'oscuro'),
  ('ui.acento',            'naranja-forja'),
  ('ui.densidad',          'comoda'),
  ('ui.tipografia',        'sistema'),
  ('ui.pestanas',          'icono+texto'),
  ('ui.esfuerzo_control',  'segmentos'),
  ('ui.mostrar_modelo',    'tier+tooltip'),
  ('ui.panel_hilos',       'desplegable'),
  ('estado.modo',          'scripts'),
  ('estado.tier',          'pequeno'),
  ('estado.esfuerzo',      'medio'),
  ('nube.activada',        '0'),
  ('modelos.precargar',    '1');
