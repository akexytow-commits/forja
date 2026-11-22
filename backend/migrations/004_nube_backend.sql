-- 004: ADR-0006 — nombres de ajustes de la Nube según la spec:
--   nube.backend = 'claude_code' (suscripción vía Claude Code, por defecto) | 'api' (clave propia, pago por uso)
--   nube.claude_bin = ruta a claude.exe ('' = autodetectar)
INSERT OR REPLACE INTO settings (key, value)
  SELECT 'nube.backend', CASE value WHEN 'anthropic' THEN 'api' ELSE 'claude_code' END
    FROM settings WHERE key = 'nube.proveedor';
INSERT OR IGNORE INTO settings (key, value) VALUES ('nube.backend', 'claude_code'), ('nube.claude_bin', '');
DELETE FROM settings WHERE key = 'nube.proveedor';
