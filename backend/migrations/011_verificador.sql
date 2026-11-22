-- 011: Rama 6b — Verificador de código (MOD-110, doc 23). Instalar una herramienta del verificador
-- (Git-Bash, Node, shellcheck, ruff) es una acción con confirmación (ST-040): queda en la auditoría.
CREATE TABLE audit_log_v11 (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  tipo    TEXT NOT NULL CHECK (tipo IN ('cambio_alcance','escalado_nube','accion_seguridad_confirmada',
                                        'descarga_modelo','export','engagement','guardarrail',
                                        'academia_laboratorio','academia_enfoque','lab_accion',
                                        'guardar_archivo','proyecto','verificador_instalar')),
  detalle TEXT
);
INSERT INTO audit_log_v11 (id, ts, tipo, detalle) SELECT id, ts, tipo, detalle FROM audit_log;
DROP TABLE audit_log;
ALTER TABLE audit_log_v11 RENAME TO audit_log;
