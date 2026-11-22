-- 002: Rama 2 — proveedor de Nube (Claude, Anthropic) y umbrales del estimador (05-escalado-y-estimador.md)
UPDATE models
   SET etiqueta = 'claude-opus-5-5', thinking = 1, notas = 'Claude (Anthropic) — tareas enormes; requiere clave'
 WHERE alias = 'nube-frontera';

INSERT OR IGNORE INTO settings (key, value) VALUES
  ('nube.proveedor',           'anthropic'),
  ('nube.modelo',              'claude-opus-5-5'),
  ('umbral.complejidad_nube',  '70'),
  ('umbral.complejidad_justo', '45'),
  ('umbral.factor_salida',     '2'),
  ('ui.aviso_escalado',        'modal-nube+banner-justo');
