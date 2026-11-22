-- 010: Rama 6 — Personalización de interfaces (13-protocolo-personalizacion.md).
-- Claves ui.* que faltaban + las respuestas del usuario al Protocolo (2026-11-22). Solo se cambia una clave
-- si sigue con el DEFAULT anterior: lo que ya se hubiera retocado en Ajustes se respeta.

-- Claves nuevas (DEFAULT del doc 13).
INSERT OR IGNORE INTO settings (key, value) VALUES
  ('ui.informe_plantilla',  'hackerone'),   -- SG3: hackerone | bugcrowd | breve | personalizada
  ('ui.informe_estructura', ''),            -- SG3 "editable": la estructura propia (si personalizada)
  ('ui.tareas_carga',       '1'),           -- ST2: minutos y carga del día
  ('ui.pestanas',           'icono+texto'),
  ('ui.esfuerzo_control',   'segmentos'),
  ('ui.mostrar_modelo',     'tier+tooltip'),
  ('ui.codigo_tema',        'acorde'),
  ('ui.gate',               'pantalla_completa'),
  ('ui.hallazgos',          'tabla'),
  ('ui.tareas_vista',       'tablero'),
  ('ui.aviso_escalado',     'modal-nube+banner-justo'),
  ('ui.proyectos',          'desplegable'),
  ('ui.ajustes',            'pestanas');

-- Respuestas del Protocolo: G2 claro · G3 violeta · G4 compacta · G5 monoespaciada · SC2 alto contraste ·
-- SG1 asistente por pasos. El resto (G1, S1–S3, SC1, SG2, SG3, ST1, ST2, SE1, SA1) = DEFAULT.
UPDATE settings SET value = 'claro'          WHERE key = 'ui.tema'        AND value = 'oscuro';
UPDATE settings SET value = 'violeta'        WHERE key = 'ui.acento'      AND value = 'naranja-forja';
UPDATE settings SET value = 'compacta'       WHERE key = 'ui.densidad'    AND value = 'comoda';
UPDATE settings SET value = 'mono'           WHERE key = 'ui.tipografia'  AND value = 'sistema';
UPDATE settings SET value = 'alto-contraste' WHERE key = 'ui.codigo_tema' AND value = 'acorde';
UPDATE settings SET value = 'asistente'      WHERE key = 'ui.gate'        AND value = 'pantalla_completa';
-- Marca de cuándo se respondió el Protocolo (para re-pulir sin volver a preguntar).
INSERT OR REPLACE INTO settings (key, value) VALUES ('ui.protocolo_respondido', '2026-11-22');
