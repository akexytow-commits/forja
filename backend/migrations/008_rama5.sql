-- 008: Rama 5 — proyectos (guardar archivo), export de conversaciones, telemetría de generación (doc 22), ajustes.

-- DB-004: fecha de actualización para ordenar la lista de proyectos.
ALTER TABLE projects ADD COLUMN updated_at TEXT;

-- DB-003 (doc 22): duración de la generación y del razonamiento, para el histórico y para afinar futuras ETAs.
ALTER TABLE messages ADD COLUMN gen_ms INTEGER;
ALTER TABLE messages ADD COLUMN thinking_ms INTEGER;

-- Auditoría: escribir un archivo en la carpeta de un proyecto (ST-040) es una acción sensible.
CREATE TABLE audit_log_v8 (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  tipo    TEXT NOT NULL CHECK (tipo IN ('cambio_alcance','escalado_nube','accion_seguridad_confirmada',
                                        'descarga_modelo','export','engagement','guardarrail',
                                        'academia_laboratorio','academia_enfoque','lab_accion',
                                        'guardar_archivo','proyecto')),
  detalle TEXT
);
INSERT INTO audit_log_v8 (id, ts, tipo, detalle) SELECT id, ts, tipo, detalle FROM audit_log;
DROP TABLE audit_log;
ALTER TABLE audit_log_v8 RENAME TO audit_log;

INSERT OR IGNORE INTO settings (key, value) VALUES
  ('ui.proyectos',      'desplegable'),   -- SC1 (13-...md, valor por defecto)
  ('ui.codigo_tema',    'acorde'),        -- SC2 (resaltado acorde al tema global)
  ('ui.ajustes',        'pestanas'),      -- SA1 (Modelos / Nube / Apariencia / Avanzado)
  ('ui.razonamiento',   'plegar'),        -- BTN-100: plegar el thinking al terminar (o 'mostrar')
  ('ui.telemetria',     '1'),             -- FR-077: línea de telemetría junto al compositor
  ('proyectos.dir',     ''),              -- '' = Documentos\FORJA proyectos
  ('plantillas.dir',    ''),              -- '' = %APPDATA%\FORJA\plantillas (las tuyas, encima de las de serie)
  ('estado.hilo.proyecto', '');
