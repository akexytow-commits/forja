-- 013: Rama 9 — Base de Conocimiento / RAG local (MOD-120, doc 24, DB-012).

-- DB-012 knowledge_bases
CREATE TABLE knowledge_bases (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre       TEXT NOT NULL UNIQUE COLLATE NOCASE,
  descripcion  TEXT NOT NULL DEFAULT '',
  embed_modelo TEXT NOT NULL DEFAULT 'nomic-embed-text',  -- el modelo con el que se indexó (vectores compatibles)
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
  updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

-- DB-012b kb_documents. `contenido` (texto ya extraído) no está en el doc 06: hace falta para Reindexar
-- (BTN-105) sin volver a leer el archivo. indexado_at NULL = pendiente de indexar.
CREATE TABLE kb_documents (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  kb_id       INTEGER NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
  origen      TEXT NOT NULL,             -- ruta del archivo, o "pegado"
  titulo      TEXT NOT NULL,
  contenido   TEXT NOT NULL,
  num_chunks  INTEGER NOT NULL DEFAULT 0,
  indexado_at TEXT,
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);
CREATE INDEX idx_kb_documents_kb ON kb_documents(kb_id);

-- DB-012c kb_chunks: el fragmento, su origen (para citar) y el vector float32 (768-dim, normalizado).
CREATE TABLE kb_chunks (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  kb_id     INTEGER NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
  doc_id    INTEGER NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
  texto     TEXT NOT NULL,
  origen    TEXT NOT NULL,
  embedding BLOB NOT NULL,
  orden     INTEGER NOT NULL
);
CREATE INDEX idx_kb_chunks_kb ON kb_chunks(kb_id);
CREATE INDEX idx_kb_chunks_doc ON kb_chunks(doc_id);

-- Fuentes que se le pasaron al modelo en cada respuesta (BTN-107 «Ver fuentes citadas»), en JSON.
ALTER TABLE messages ADD COLUMN fuentes TEXT;

-- Doc 04: alias `embeddings` = nomic-embed-text (n/a de tier; la tabla solo admite pequeno/grande/nube, va
-- como pequeno). No es un modelo de chat: convive en RAM con el del chat.
INSERT OR IGNORE INTO models (alias, tier, etiqueta, tamano_disco_mb, thinking, notas) VALUES
  ('embeddings', 'pequeno', 'nomic-embed-text', 274, 0, 'base de conocimiento / RAG (convive con el chat)');

-- Base activa en el compositor (BTN-106); '' = sin base.
INSERT OR IGNORE INTO settings (key, value) VALUES ('estado.kb', '');
