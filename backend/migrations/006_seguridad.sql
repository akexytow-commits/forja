-- 006: Rama 4 — Modo Seguridad con guardarraíles como código (10-...md, ADR-0005, ST-030).

-- ST-030 explícito en la fila: declarando_alcance → autorizacion_pendiente → autorizado → operando → revocado
ALTER TABLE engagements ADD COLUMN estado TEXT NOT NULL DEFAULT 'declarando_alcance'
  CHECK (estado IN ('declarando_alcance','autorizacion_pendiente','autorizado','operando','revocado'));
ALTER TABLE engagements ADD COLUMN autorizado_at TEXT;
ALTER TABLE engagements ADD COLUMN updated_at TEXT;
ALTER TABLE engagements ADD COLUMN archivado INTEGER NOT NULL DEFAULT 0;
UPDATE engagements SET estado = 'autorizado' WHERE autorizacion_confirmada = 1;

-- Hallazgos: cómo verificar de forma segura y de dónde salen (análisis de la IA o manual del usuario).
ALTER TABLE findings ADD COLUMN como_verificar TEXT;
ALTER TABLE findings ADD COLUMN origen TEXT NOT NULL DEFAULT 'ia' CHECK (origen IN ('ia','manual'));
CREATE INDEX IF NOT EXISTS idx_findings_eng ON findings(engagement_id, estado);

-- Auditoría (G-5): nuevos tipos para entrar a un engagement, bloqueos de la lista "nunca" (G-3) y análisis.
CREATE TABLE audit_log_v6 (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  tipo    TEXT NOT NULL CHECK (tipo IN ('cambio_alcance','escalado_nube','accion_seguridad_confirmada',
                                        'descarga_modelo','export','engagement','guardarrail')),
  detalle TEXT
);
INSERT INTO audit_log_v6 (id, ts, tipo, detalle) SELECT id, ts, tipo, detalle FROM audit_log;
DROP TABLE audit_log;
ALTER TABLE audit_log_v6 RENAME TO audit_log;

INSERT OR IGNORE INTO settings (key, value) VALUES
  ('ui.gate',                     'pantalla_completa'),  -- SG1
  ('ui.hallazgos',                'tabla'),              -- SG2
  ('seguridad.plantilla_informe', 'hackerone'),          -- SG3 (Resumen/Impacto/Pasos/Evidencia/Mitigación)
  ('seguridad.engagement',        ''),                   -- último engagement abierto
  ('export.dir',                  '');                   -- '' = Documentos\FORJA
