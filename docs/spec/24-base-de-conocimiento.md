# 24 — Base de Conocimiento (RAG local) — MOD-120

Da al modelo **información de referencia** (p. ej. programar para Flipper Zero) para que escriba mucho mejor
código específico, **sin cambiar de modelo**. Es un **RAG local**: tus documentos se trocean, se convierten
en vectores con un modelo de embeddings pequeño, se guardan en SQLite, y al preguntar se recuperan los
fragmentos relevantes y se le **inyectan al modelo en el contexto**, con las **fuentes citadas**.

> Clave para tu hardware: un modelo de 3–4B **con los docs correctos delante** supera a uno más grande
> **sin contexto**, y corre holgado. El RAG es mejor palanca que subir de modelo en 8 GB de RAM.

## Piezas (pensadas para CPU / 8 GB)
- **Modelo de embeddings:** `nomic-embed-text` (274 MB, 768 dim, 8192 ctx, corre en CPU y **convive** con el
  modelo de chat). Se añade al registro como alias `embeddings`. Instalar: `ollama pull nomic-embed-text`.
- **Almacén:** SQLite (ya en uso). Los vectores se guardan como BLOB; la similitud (coseno) se calcula en
  Python con numpy. Para un corpus modesto (miles de fragmentos) va de sobra en CPU.
- **Troceo:** ~512 tokens por fragmento, solape ~64. Prefijos de nomic: `search_document:` al indexar,
  `search_query:` al buscar. (Ollama ≥0.30 pasa a minúsculas la entrada de nomic; subir `num_ctx` a 8192
  para fragmentos largos, su defecto es 2048.)

## Flujo
1. **Crear base** (p. ej. "Flipper Zero") y **añadir documentos**: pegar texto o importar archivos
   (`.md/.txt/.pdf`) o una carpeta.
2. **Indexar:** trocea → embebe cada fragmento con `nomic-embed-text` → guarda vector + texto + origen.
3. **Usar en el chat:** con la base activa (toggle en el compositor), al enviar: se embebe la pregunta, se
   recuperan los top-k fragmentos por coseno, y se **anteponen al contexto** del modelo con una nota de
   origen. La respuesta muestra **qué fuentes usó**.
4. Un solo modelo de chat cargado a la vez sigue vigente; el de embeddings es pequeño y puede quedar
   residente (keep_alive) para no pagar arranque en frío.

## UI
- **SCR-050 Bases de conocimiento:** lista de bases, añadir/importar documentos, estado de indexado,
  reindexar.
- **Compositor (SCR-001):** toggle **"Usar base: <nombre>"** (BTN-106) para activar/desactivar el RAG en la
  consulta actual; y **"Ver fuentes citadas"** (BTN-107) tras la respuesta.

## Semilla recomendada para Flipper Zero (qué importar)
FORJA no inventa los docs: tú importas los **oficiales** (son abiertos, GPLv3 — uso local personal, sin
problema). Fuentes recomendadas:
- **Developer Docs oficiales** — `developer.flipper.net` (API Doxygen) y `docs.flipper.net/development`.
- **Manifiestos y empaquetado** — FAM (Flipper App Manifest) y FAP (Flipper App Package).
- **Build tools** — FBT y **uFBT** (micro build tool para apps de usuario).
- **SDK de JavaScript oficial** — `@flipperdevices/fz-sdk` (apps en JS) y la sección JS de los Developer Docs.
- **Ejemplos** — apps de ejemplo de los Developer Docs y tutoriales de la comunidad (p. ej. repos de
  jamisonderek, plantillas de Momentum/Xtreme).
- **BadUSB / Ducky Script** — la referencia de scripts BadUSB del Flipper.
> La calidad del RAG depende de los docs que metas: alimenta los oficiales y buenos ejemplos. Basura dentro,
> basura fuera.

## Contrato (API)
- **API-070** `GET/POST /kb` — listar/crear bases.
- **API-071** `POST /kb/{id}/documentos` `{origen, contenido|ruta}` — añadir documento.
- **API-072** `POST /kb/{id}/indexar` — trocea+embebe (progreso por SSE).
- **API-073** `POST /kb/{id}/buscar` `{query, k}` → fragmentos top-k con origen y score.
- El chat, con base activa, llama internamente a buscar y antepone los fragmentos (con citas) al contexto.

## Datos (ver DB-012 en `06-...md`)
`knowledge_bases`, `kb_documents`, `kb_chunks (texto, embedding BLOB, doc_id, origen)`.

## Requisitos y pruebas
- **FR-082** Crear/gestionar bases de conocimiento; añadir documentos (pegar/importar archivos/carpeta).
- **FR-083** Indexar: trocear + embeber con `nomic-embed-text`, vectores en SQLite.
- **FR-084** Recuperar top-k por coseno e **inyectar en el contexto con fuentes citadas**; toggle en el
  compositor para activar la base por consulta.
- **FR-085** Importar un **paquete semilla de Flipper Zero** (los docs oficiales de arriba).
- Pruebas: **TST-083** (indexar crea fragmentos con embeddings), **TST-084** (buscar devuelve fragmentos
  relevantes por coseno), **TST-085** (el chat con base activa inyecta contexto y cita fuentes).

## Orden de construcción
**Rama 9 (post-v1 / v1.1).** Primero el embebido + almacén + búsqueda (backend), luego la pantalla y el
toggle, y por último el importador del paquete Flipper. No toca los guardarraíles de Seguridad.
