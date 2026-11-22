-- 012: Rama 8 — Estudio de Apariencia (MOD-100, doc 20). Claves nuevas con su DEFAULT; no cambia tu tema.
INSERT OR IGNORE INTO settings (key, value) VALUES
  ('ui.base',            ''),                 -- colores base propios {bg, surface, texto}; '' = los del tema
  ('ui.fondo',           '{"tipo":"liso"}'),  -- liso | degradado | imagen (+archivo, opacidad)
  ('ui.acento_por_modo', '{}'),               -- opcional: {seguridad: "#d9483b", …}
  ('ui.animacion',       '1'),                -- la única animación (aparecer los mensajes); 0 = sin ella
  ('ui.preset',          '');                 -- último preset aplicado (informativo)
