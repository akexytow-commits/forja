-- 005: Rama 3 — Modo Tareas (11-modo-tareas-organizador.md + 17-patrones-planificador.md P1–P4)
-- P2 fijada: Reorganizar no la mueve (FR-046, BTN-058).
ALTER TABLE tasks ADD COLUMN fijada INTEGER NOT NULL DEFAULT 0;
-- P4 parent_id: subtarea anidada bajo otra (FR-048, BTN-059). Al borrar el padre se borran sus hijas.
ALTER TABLE tasks ADD COLUMN parent_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE;
-- P1: hora extraída del lenguaje natural ("mañana 17:00"), opcional.
ALTER TABLE tasks ADD COLUMN hora TEXT;
CREATE INDEX idx_tasks_parent ON tasks(parent_id);
-- Resumen legible del último Organizar de la lista.
ALTER TABLE task_lists ADD COLUMN resumen TEXT;
ALTER TABLE task_lists ADD COLUMN organizada_at TEXT;

INSERT INTO task_lists (nombre)
  SELECT 'General' WHERE NOT EXISTS (SELECT 1 FROM task_lists);

INSERT OR IGNORE INTO settings (key, value) VALUES
  ('plan.capacidad_dia_min', '480'),   -- P3 carga del día (FR-047); ST2 = sí
  ('tareas.lista',           ''),      -- última lista abierta
  ('ui.tareas_vista',        'tablero'); -- ST1 = tablero por columnas
