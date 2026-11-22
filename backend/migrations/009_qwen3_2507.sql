-- 009: doc 04 rev. 10 — las variantes Qwen3 4B 2507 NO son híbridas.
-- El "qwen3:4b" de Ollama es Thinking-2507 (solo razona; /no_think y think:false no lo apagan).
-- Para responder sin razonar se usa OTRO modelo, el instruct; el que razona queda para Seguridad extra.
-- (Las etiquetas son las que existen en el registro de Ollama: llevan el sufijo de cuantización.)

-- pequeno-general → instruct (sin thinking). Solo si el usuario no la había cambiado en Ajustes.
UPDATE models SET etiqueta = 'qwen3:4b-instruct-2507-q4_K_M', thinking = 0, instalado = 0,
                  notas = 'chat, Tareas, Seguridad medio (instruct, sin razonamiento)'
 WHERE alias = 'pequeno-general' AND etiqueta = 'qwen3:4b';

-- pequeno-razonador → thinking-2507 (mismo contenido que el antiguo qwen3:4b), solo Seguridad extra.
INSERT OR IGNORE INTO models (alias, tier, etiqueta, tamano_disco_mb, thinking, notas) VALUES
  ('pequeno-razonador', 'pequeno', 'qwen3:4b-thinking-2507-q4_K_M', 2500, 1,
   'Seguridad extra: fase de razonar (solo razona)');
