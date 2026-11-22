-- 003: la Nube puede ir por la suscripción Claude (CLI de Claude Code) en lugar de la API de pago.
-- Pasa a ser el proveedor por defecto; quien ya tenga clave puede volver a "anthropic" en Ajustes.
UPDATE settings SET value = 'suscripcion' WHERE key = 'nube.proveedor' AND value = 'anthropic';
UPDATE models SET notas = 'Claude (Anthropic) — tareas enormes; vía suscripción (Claude Code) o clave API'
 WHERE alias = 'nube-frontera';
