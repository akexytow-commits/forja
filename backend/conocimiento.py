"""MOD-120 Base de Conocimiento — RAG local (doc 24, DB-012, API-070…073).

Tus documentos se trocean (~512 tokens, solape 64), se embeben con `nomic-embed-text` vía Ollama
(prefijo `search_document:`), y el vector (float32, normalizado) se guarda en SQLite. Al buscar se embebe la
pregunta (`search_query:`) y se ordena por coseno con numpy. El chat, con una base activa, antepone los
fragmentos al contexto con una nota de origen y la respuesta cita las fuentes ([1], [2]…).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path
from typing import Any, AsyncIterator

import numpy as np

from .db import DB, ahora
from .ollama_client import OllamaClient
from .router import tokens_aprox

EMBED_ALIAS = "embeddings"
EMBED_DEFECTO = "nomic-embed-text"
NUM_CTX_EMBED = 8192          # el defecto de Ollama para nomic es 2048: se queda corto con fragmentos largos
PREFIJO_DOC = "search_document: "
PREFIJO_QUERY = "search_query: "
TOKENS_FRAGMENTO = 512
TOKENS_SOLAPE = 64
CHARS_POR_TOKEN = 3.5         # = router.tokens_aprox
LOTE_EMBED = 8                # fragmentos por llamada a /api/embed (y por evento de progreso)
K_DEFECTO = 4
K_MAX = 20

EXT_DOCS = {".md", ".markdown", ".txt", ".pdf"}                       # FR-082
EXT_SEMILLA = EXT_DOCS | {".c", ".h", ".fam", ".js", ".ts", ".txt"}   # FR-085: los ejemplos son código
MAX_BYTES_ARCHIVO = 5 * 1024 * 1024
MAX_ARCHIVOS = 2000
MAX_CONTENIDO = 2_000_000     # caracteres por documento (pegado o extraído)
CARPETAS_IGNORADAS = {".git", "node_modules", "__pycache__", ".venv", "venv", "build", "dist", "images", "doxygen"}

ORIGEN_PEGADO = "pegado"


class KBError(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje = status, codigo, mensaje


# ---------------------------------------------------------------- troceo
def trocear(texto: str, max_tokens: int = TOKENS_FRAGMENTO, solape: int = TOKENS_SOLAPE) -> list[str]:
    """Fragmentos de ~max_tokens con ~solape tokens repetidos entre uno y el siguiente.

    Corta preferentemente en un párrafo, luego en una línea, una frase o un espacio (en la 2.ª mitad de la
    ventana), para no partir bloques de código ni frases si se puede evitar.
    """
    texto = (texto or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not texto:
        return []
    maxc = max(1, int(max_tokens * CHARS_POR_TOKEN))
    solc = max(0, min(int(solape * CHARS_POR_TOKEN), maxc // 2))
    out: list[str] = []
    i, n = 0, len(texto)
    while i < n:
        fin = min(i + maxc, n)
        if fin < n:
            ventana = texto[i:fin]
            for sep in ("\n\n", "\n", ". ", " "):
                j = ventana.rfind(sep, maxc // 2)
                if j != -1:
                    fin = i + j + len(sep)
                    break
        trozo = texto[i:fin].strip()
        if trozo:
            out.append(trozo)
        if fin >= n:
            break
        nuevo = fin - solc
        k = texto.find(" ", nuevo, fin)              # que el solape empiece en una palabra entera
        if solc and k != -1:
            nuevo = k + 1
        i = max(nuevo, i + 1)
    return out


def vector_blob(v: list[float]) -> bytes:
    a = np.asarray(v, dtype=np.float32)
    norma = float(np.linalg.norm(a))
    if norma > 0:
        a = a / norma                                 # normalizado: coseno = producto escalar
    return a.astype(np.float32).tobytes()


def origen_corto(origen: str) -> str:
    """Para citar: las 3 últimas partes de una ruta (documentation/js/js_gui.md), o el origen tal cual."""
    if origen == ORIGEN_PEGADO or ("/" not in origen and "\\" not in origen):
        return origen
    partes = Path(origen).parts
    return "/".join(partes[-3:])


def citadas(respuesta: str, n: int) -> list[int]:
    """Números [k] que la respuesta cita (1..n), en orden de aparición."""
    vistos: list[int] = []
    for m in re.finditer(r"\[(\d{1,2})\]", respuesta or ""):
        k = int(m.group(1))
        if 1 <= k <= n and k not in vistos:
            vistos.append(k)
    return vistos


def bloque_contexto(nombre: str, fragmentos: list[dict[str, Any]], pregunta: str) -> str:
    """El mensaje que ve el modelo: fragmentos numerados con su origen y, al final, la pregunta (doc 24 §Flujo 3)."""
    partes = [
        f"[Base de conocimiento «{nombre}»: fragmentos recuperados de los documentos del usuario. Úsalos si son "
        "relevantes para la pregunta y, cuando te apoyes en uno, cita su número entre corchetes, p. ej. [1]. "
        "Si no bastan para responder, dilo y responde con lo que sepas.]"
    ]
    for f in fragmentos:
        partes.append(f"[{f['n']}] Fuente: {origen_corto(f['origen'])} — {f['titulo']}\n{f['texto']}")
    partes.append(f"[Pregunta del usuario]\n{pregunta}")
    # Los modelos de 3–4B siguen mejor la última instrucción: la de citar va también DESPUÉS de la pregunta.
    partes.append("[Al terminar tu respuesta, añade una última línea «Fuentes: [n], [m]» con los números de los "
                  "fragmentos que hayas usado; si no usaste ninguno, «Fuentes: ninguna».]")
    return "\n\n".join(partes)


# ---------------------------------------------------------------- lectura de archivos
def leer_pdf(datos: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover — pypdf va en requirements.txt
        raise KBError(400, "PDF_NO_SOPORTADO", "Falta pypdf para leer PDF (pip install pypdf).") from e
    try:
        lector = PdfReader(io.BytesIO(datos))
        paginas = [(p.extract_text() or "").strip() for p in lector.pages]
    except Exception as e:
        raise KBError(400, "PDF_ILEGIBLE", f"No se pudo leer el PDF: {e}") from e
    return "\n\n".join(p for p in paginas if p)


def texto_de(nombre: str, datos: bytes) -> str:
    if Path(nombre).suffix.lower() == ".pdf":
        return leer_pdf(datos)
    for cod in ("utf-8-sig", "cp1252"):
        try:
            return datos.decode(cod)
        except UnicodeDecodeError:
            continue
    return datos.decode("utf-8", errors="replace")


def archivos_de(ruta: Path, extensiones: set[str]) -> list[Path]:
    if ruta.is_file():
        if ruta.suffix.lower() not in extensiones:
            raise KBError(400, "TIPO_NO_ADMITIDO", f"Solo se importan {', '.join(sorted(extensiones))}.")
        return [ruta]
    if not ruta.is_dir():
        raise KBError(404, "RUTA_NO_EXISTE", f"No existe: {ruta}")
    out: list[Path] = []
    for raiz, dirs, nombres in os.walk(ruta):
        dirs[:] = sorted(d for d in dirs if d.lower() not in CARPETAS_IGNORADAS and not d.startswith("."))
        for nombre in sorted(nombres):
            p = Path(raiz) / nombre
            if p.suffix.lower() in extensiones and not p.is_symlink():
                out.append(p)
                if len(out) > MAX_ARCHIVOS:
                    raise KBError(400, "DEMASIADOS_ARCHIVOS", f"La carpeta tiene más de {MAX_ARCHIVOS} archivos admitidos.")
    return out


def carpetas_semilla(raiz: Path) -> list[Path]:
    """FR-085: qué importar de una copia local del firmware (oficial, Momentum, Unleashed…)."""
    candidatas = [raiz / "documentation", raiz / "applications" / "examples"]
    return [c for c in candidatas if c.is_dir()]


# ---------------------------------------------------------------- servicio
class BaseConocimiento:
    def __init__(self, db: DB, ollama: OllamaClient):
        self.db, self.ollama = db, ollama
        self._indexando: set[int] = set()
        self._cache: dict[int, tuple[tuple, np.ndarray, list[int]]] = {}

    # --- bases (API-070) ------------------------------------------------------
    def _kb(self, kb_id: int) -> dict[str, Any]:
        kb = self.db.one("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,))
        if kb is None:
            raise KBError(404, "KB_NO_EXISTE", "Esa base de conocimiento no existe.")
        return kb

    def resumen(self, kb: dict[str, Any]) -> dict[str, Any]:
        c = self.db.one(
            "SELECT COUNT(*) AS documentos, COALESCE(SUM(num_chunks), 0) AS fragmentos, "
            "COALESCE(SUM(indexado_at IS NULL), 0) AS pendientes FROM kb_documents WHERE kb_id = ?", (kb["id"],))
        return {**kb, **c, "indexando": kb["id"] in self._indexando}

    def listar(self) -> list[dict[str, Any]]:
        return [self.resumen(k) for k in self.db.query("SELECT * FROM knowledge_bases ORDER BY nombre COLLATE NOCASE")]

    def obtener(self, kb_id: int) -> dict[str, Any]:
        return self.resumen(self._kb(kb_id))

    def crear(self, nombre: str, descripcion: str = "") -> dict[str, Any]:
        nombre = (nombre or "").strip()
        if not nombre or len(nombre) > 80:
            raise KBError(400, "NOMBRE_INVALIDO", "El nombre de la base debe tener entre 1 y 80 caracteres.")
        if self.db.one("SELECT 1 FROM knowledge_bases WHERE nombre = ?", (nombre,)):
            raise KBError(409, "KB_DUPLICADA", f"Ya existe una base llamada «{nombre}».")
        kid = self.db.execute("INSERT INTO knowledge_bases(nombre, descripcion, embed_modelo) VALUES (?, ?, ?)",
                              (nombre, (descripcion or "").strip()[:500], self.etiqueta_embed()))
        return self.obtener(kid)

    def borrar(self, kb_id: int) -> None:
        self._kb(kb_id)
        if kb_id in self._indexando:
            raise KBError(409, "KB_INDEXANDO", "Espera a que termine el indexado.")
        self.db.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))
        self._cache.pop(kb_id, None)
        if self.db.get_setting("estado.kb", "") == str(kb_id):
            self.db.set_setting("estado.kb", "")

    def etiqueta_embed(self) -> str:
        fila = self.db.one("SELECT etiqueta FROM models WHERE alias = ?", (EMBED_ALIAS,))
        return (fila or {}).get("etiqueta") or EMBED_DEFECTO

    # --- documentos (API-071) ------------------------------------------------
    def documentos(self, kb_id: int) -> list[dict[str, Any]]:
        self._kb(kb_id)
        return self.db.query(
            "SELECT id, kb_id, origen, titulo, num_chunks, indexado_at, created_at, LENGTH(contenido) AS caracteres "
            "FROM kb_documents WHERE kb_id = ? ORDER BY id", (kb_id,))

    def _guardar_doc(self, kb_id: int, origen: str, titulo: str, contenido: str) -> dict[str, Any]:
        contenido = (contenido or "").replace("\x00", "").strip()
        if not contenido:
            raise KBError(400, "DOCUMENTO_VACIO", f"«{titulo}» no tiene texto que indexar.")
        if len(contenido) > MAX_CONTENIDO:
            raise KBError(400, "DOCUMENTO_GRANDE", f"«{titulo}» supera {MAX_CONTENIDO:,} caracteres.".replace(",", "."))
        titulo = (titulo or "").strip()[:200] or "Sin título"
        previo = None if origen == ORIGEN_PEGADO else self.db.one(
            "SELECT id FROM kb_documents WHERE kb_id = ? AND origen = ?", (kb_id, origen))
        if previo:   # reimportar el mismo archivo lo actualiza (y queda pendiente de indexar)
            with self.db.tx() as c:
                c.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (previo["id"],))
                c.execute("UPDATE kb_documents SET titulo = ?, contenido = ?, num_chunks = 0, indexado_at = NULL "
                          "WHERE id = ?", (titulo, contenido, previo["id"]))
            did, nuevo = previo["id"], False
        else:
            did = self.db.execute("INSERT INTO kb_documents(kb_id, origen, titulo, contenido) VALUES (?, ?, ?, ?)",
                                  (kb_id, origen, titulo, contenido))
            nuevo = True
        self._cache.pop(kb_id, None)
        return {"id": did, "origen": origen, "titulo": titulo, "caracteres": len(contenido), "nuevo": nuevo}

    def anadir(self, kb_id: int, *, contenido: str | None = None, titulo: str | None = None,
               origen: str | None = None, ruta: str | None = None, nombre: str | None = None,
               contenido_b64: str | None = None, semilla: bool = False) -> dict[str, Any]:
        """Pegar texto (contenido), subir un archivo (nombre + contenido_b64) o importar una ruta de archivo o
        carpeta del equipo (ruta). `semilla` = paquete Flipper Zero desde una copia local del firmware."""
        self._kb(kb_id)
        if kb_id in self._indexando:
            raise KBError(409, "KB_INDEXANDO", "Espera a que termine el indexado.")
        añadidos: list[dict[str, Any]] = []
        omitidos: list[dict[str, str]] = []
        if ruta:
            raiz = Path(os.path.expandvars(ruta.strip().strip('"'))).expanduser()
            if not raiz.is_absolute():
                raise KBError(400, "RUTA_INVALIDA", "Indica una ruta completa (p. ej. C:\\docs\\flipper).")
            if semilla:
                carpetas = carpetas_semilla(raiz)
                if not carpetas:
                    raise KBError(400, "SEMILLA_NO_ENCONTRADA",
                                  "Esa carpeta no parece el firmware de Flipper: no tiene documentation/ ni "
                                  "applications/examples/.")
                archivos = [a for c in carpetas for a in archivos_de(c, EXT_SEMILLA)]
                leeme = raiz / "ReadMe.md"
                if leeme.is_file() and leeme not in archivos:
                    archivos.insert(0, leeme)
            else:
                archivos = archivos_de(raiz, EXT_DOCS)
            if not archivos:
                raise KBError(400, "SIN_ARCHIVOS", f"No hay archivos {', '.join(sorted(EXT_DOCS))} en {raiz}.")
            base = raiz if raiz.is_dir() else raiz.parent
            for a in dict.fromkeys(archivos):
                try:
                    if a.stat().st_size > MAX_BYTES_ARCHIVO:
                        omitidos.append({"origen": str(a), "motivo": "más de 5 MB"})
                        continue
                    texto = texto_de(a.name, a.read_bytes())
                    if a.suffix.lower() in {".c", ".h", ".fam", ".js", ".ts"}:
                        texto = f"Archivo {a.relative_to(base).as_posix()}:\n```\n{texto}\n```"
                    titulo_a = a.relative_to(base).as_posix() if a != base else a.name
                    añadidos.append(self._guardar_doc(kb_id, str(a), titulo_a, texto))
                except KBError as e:
                    omitidos.append({"origen": str(a), "motivo": e.mensaje})
                except OSError as e:
                    omitidos.append({"origen": str(a), "motivo": str(e)})
        elif contenido_b64 is not None:
            nombre = Path(nombre or "archivo.txt").name
            if Path(nombre).suffix.lower() not in EXT_DOCS:
                raise KBError(400, "TIPO_NO_ADMITIDO", f"Solo se importan {', '.join(sorted(EXT_DOCS))}.")
            try:
                datos = base64.b64decode(contenido_b64, validate=True)
            except ValueError as e:
                raise KBError(400, "ARCHIVO_INVALIDO", "El archivo no llegó bien (base64).") from e
            if len(datos) > MAX_BYTES_ARCHIVO:
                raise KBError(400, "ARCHIVO_GRANDE", "El archivo supera 5 MB.")
            añadidos.append(self._guardar_doc(kb_id, origen or nombre, titulo or nombre, texto_de(nombre, datos)))
        elif contenido is not None:
            primera = next((l.strip("# ").strip() for l in contenido.splitlines() if l.strip()), "")
            añadidos.append(self._guardar_doc(kb_id, (origen or ORIGEN_PEGADO).strip()[:500] or ORIGEN_PEGADO,
                                              titulo or primera[:80] or "Texto pegado", contenido))
        else:
            raise KBError(400, "SIN_CONTENIDO", "Pega un texto o indica un archivo o carpeta.")
        if not añadidos and omitidos:
            raise KBError(400, "NADA_IMPORTADO", f"No se pudo importar nada: {omitidos[0]['motivo']}")
        self.db.execute("UPDATE knowledge_bases SET updated_at = ? WHERE id = ?", (ahora(), kb_id))
        return {"documentos": añadidos, "omitidos": omitidos, "base": self.obtener(kb_id)}

    def borrar_documento(self, kb_id: int, doc_id: int) -> None:
        self._kb(kb_id)
        if kb_id in self._indexando:
            raise KBError(409, "KB_INDEXANDO", "Espera a que termine el indexado.")
        if not self.db.one("SELECT 1 FROM kb_documents WHERE id = ? AND kb_id = ?", (doc_id, kb_id)):
            raise KBError(404, "DOC_NO_EXISTE", "Ese documento no existe en esta base.")
        self.db.execute("DELETE FROM kb_documents WHERE id = ?", (doc_id,))
        self._cache.pop(kb_id, None)

    # --- indexar (API-072) ---------------------------------------------------
    async def indexar(self, kb_id: int, todo: bool = False) -> AsyncIterator[dict[str, Any]]:
        """Trocea y embebe. Eventos: inicio, progreso (por lote), documento (al guardar uno) y fin.

        Sin `todo` solo los pendientes; con `todo` (BTN-105 Reindexar) todos. Si el modelo de embeddings del
        registro no es el que indexó la base, se reindexa todo (vectores de modelos distintos no se comparan).
        """
        kb = self._kb(kb_id)
        if kb_id in self._indexando:
            raise KBError(409, "KB_INDEXANDO", "Ya se está indexando esta base.")
        etiqueta = self.etiqueta_embed()
        hay_vectores = self.db.one("SELECT 1 FROM kb_chunks WHERE kb_id = ? LIMIT 1", (kb_id,)) is not None
        if hay_vectores and kb["embed_modelo"] != etiqueta:
            todo = True
        filtro = "" if todo else " AND indexado_at IS NULL"
        docs = self.db.query(f"SELECT id, origen, titulo, contenido FROM kb_documents WHERE kb_id = ?{filtro} ORDER BY id",
                             (kb_id,))
        plan = [(d, trocear(d["contenido"])) for d in docs]
        total = sum(len(t) for _, t in plan)
        self._indexando.add(kb_id)
        try:
            yield {"tipo": "inicio", "kb_id": kb_id, "documentos": len(plan), "fragmentos": total,
                   "modelo": etiqueta, "todo": todo}
            if todo:
                self.db.execute("UPDATE knowledge_bases SET embed_modelo = ? WHERE id = ?", (etiqueta, kb_id))
            hechos = 0
            for d, trozos in plan:
                vectores: list[list[float]] = []
                for i in range(0, len(trozos), LOTE_EMBED):
                    lote = trozos[i:i + LOTE_EMBED]
                    vectores += await self.ollama.embed(
                        etiqueta, [f"{PREFIJO_DOC}{d['titulo']}\n{t}" for t in lote], NUM_CTX_EMBED)
                    hechos += len(lote)
                    yield {"tipo": "progreso", "hechos": hechos, "total": total, "documento": d["titulo"]}
                with self.db.tx() as c:
                    c.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (d["id"],))
                    c.executemany(
                        "INSERT INTO kb_chunks(kb_id, doc_id, texto, origen, embedding, orden) VALUES (?, ?, ?, ?, ?, ?)",
                        [(kb_id, d["id"], t, d["origen"], vector_blob(v), n) for n, (t, v) in enumerate(zip(trozos, vectores))])
                    c.execute("UPDATE kb_documents SET num_chunks = ?, indexado_at = ? WHERE id = ?",
                              (len(trozos), ahora(), d["id"]))
                self._cache.pop(kb_id, None)
                yield {"tipo": "documento", "doc_id": d["id"], "titulo": d["titulo"], "fragmentos": len(trozos)}
            if not todo and not hay_vectores and plan:
                self.db.execute("UPDATE knowledge_bases SET embed_modelo = ? WHERE id = ?", (etiqueta, kb_id))
            self.db.execute("UPDATE knowledge_bases SET updated_at = ? WHERE id = ?", (ahora(), kb_id))
            yield {"tipo": "fin", "documentos": len(plan), "fragmentos": total, "base": self.obtener(kb_id)}
        finally:
            self._indexando.discard(kb_id)
            self._cache.pop(kb_id, None)

    # --- buscar (API-073) ----------------------------------------------------
    def _matriz(self, kb_id: int) -> tuple[np.ndarray, list[int]]:
        firma = tuple(self.db.one("SELECT COUNT(*) AS n, COALESCE(MAX(id), 0) AS m FROM kb_chunks WHERE kb_id = ?",
                                  (kb_id,)).values())
        en_cache = self._cache.get(kb_id)
        if en_cache and en_cache[0] == firma:
            return en_cache[1], en_cache[2]
        filas = self.db.query("SELECT id, embedding FROM kb_chunks WHERE kb_id = ? ORDER BY id", (kb_id,))
        ids = [f["id"] for f in filas]
        if filas:
            dim = len(filas[0]["embedding"]) // 4
            matriz = np.vstack([np.frombuffer(f["embedding"], dtype=np.float32) for f in filas
                                if len(f["embedding"]) == dim * 4])
            ids = [f["id"] for f in filas if len(f["embedding"]) == dim * 4]
        else:
            matriz = np.zeros((0, 0), dtype=np.float32)
        self._cache[kb_id] = (firma, matriz, ids)
        return matriz, ids

    async def buscar(self, kb_id: int, query: str, k: int = K_DEFECTO) -> dict[str, Any]:
        kb = self._kb(kb_id)
        query = (query or "").strip()
        if not query:
            raise KBError(400, "CONSULTA_VACIA", "Escribe qué buscar.")
        k = max(1, min(int(k or K_DEFECTO), K_MAX))
        matriz, ids = self._matriz(kb_id)
        if not ids:
            return {"kb_id": kb_id, "nombre": kb["nombre"], "fragmentos": [], "indexada": False}
        [v] = await self.ollama.embed(kb["embed_modelo"], [f"{PREFIJO_QUERY}{query}"], NUM_CTX_EMBED)
        q = np.frombuffer(vector_blob(v), dtype=np.float32)
        if q.shape[0] != matriz.shape[1]:
            raise KBError(409, "REINDEXAR", "El modelo de embeddings cambió: reindexa la base (Reindexar).")
        scores = matriz @ q
        orden = np.argsort(-scores)[:k]
        elegidos = [ids[i] for i in orden]
        filas = {f["id"]: f for f in self.db.query(
            f"SELECT c.id, c.texto, c.origen, c.orden, c.doc_id, d.titulo FROM kb_chunks c "
            f"JOIN kb_documents d ON d.id = c.doc_id WHERE c.id IN ({','.join('?' * len(elegidos))})", tuple(elegidos))}
        fragmentos = []
        for n, (cid, i) in enumerate(zip(elegidos, orden), 1):
            f = filas[cid]
            fragmentos.append({"n": n, "id": cid, "doc_id": f["doc_id"], "titulo": f["titulo"], "origen": f["origen"],
                               "orden": f["orden"], "texto": f["texto"], "score": round(float(scores[i]), 4)})
        return {"kb_id": kb_id, "nombre": kb["nombre"], "fragmentos": fragmentos, "indexada": True}

    # --- para el chat --------------------------------------------------------
    @staticmethod
    def k_para(presupuesto_tokens: int) -> int:
        """Cuántos fragmentos caben: como mucho K_DEFECTO y sin pasar de ~la mitad del contexto libre."""
        por_fragmento = TOKENS_FRAGMENTO + 24
        return max(1, min(K_DEFECTO, (presupuesto_tokens // 2) // por_fragmento))

    @staticmethod
    def fuentes_json(nombre: str, kb_id: int, fragmentos: list[dict[str, Any]], respuesta: str) -> str:
        usados = citadas(respuesta, len(fragmentos))
        return json.dumps({"kb_id": kb_id, "nombre": nombre, "citadas": usados, "fragmentos": [
            {k: f[k] for k in ("n", "doc_id", "titulo", "origen", "score", "texto")} for f in fragmentos]},
            ensure_ascii=False)


__all__ = ["BaseConocimiento", "KBError", "trocear", "bloque_contexto", "citadas", "tokens_aprox"]
