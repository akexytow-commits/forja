"""Rama 9 — Base de Conocimiento / RAG local (MOD-120, doc 24): TST-083, TST-084, TST-085."""
from __future__ import annotations

import json
import sqlite3

import numpy as np
import pytest

from backend.conocimiento import (CHARS_POR_TOKEN, PREFIJO_DOC, PREFIJO_QUERY, TOKENS_FRAGMENTO, bloque_contexto,
                                  citadas, trocear)
from tests.conftest import DIM_EMBED, EMBED, eventos

SUBGHZ = ("El módulo SubGHz del Flipper Zero transmite y recibe en las bandas de 315, 433 y 868 MHz. "
          "La frecuencia se elige en los ajustes de SubGHz y el archivo .sub guarda la captura.")
FAM = ("El manifiesto application.fam declara la app: appid, name, apptype EXTERNAL, entry_point, "
       "requires y fap_category. uFBT compila el manifiesto en un FAP.")
GUI = ("La GUI usa ViewDispatcher y SceneManager. Cada vista dibuja con canvas_draw_str y recibe "
       "eventos de entrada de los botones.")


def crear_base(client, nombre="Flipper Zero") -> int:
    r = client.post("/kb", json={"nombre": nombre})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def pegar(client, kb, texto, titulo=None):
    r = client.post(f"/kb/{kb}/documentos", json={"contenido": texto, "titulo": titulo})
    assert r.status_code == 201, r.text
    return r.json()


def indexar(client, kb, todo=False):
    r = client.post(f"/kb/{kb}/indexar", json={"todo": todo})
    assert r.status_code == 200
    return eventos(r.text)


def chunks(tmp_path, kb=None):
    c = sqlite3.connect(tmp_path / "forja.db")
    c.row_factory = sqlite3.Row
    filas = c.execute("SELECT * FROM kb_chunks" + (" WHERE kb_id = ?" if kb else "") + " ORDER BY id",
                      (kb,) if kb else ()).fetchall()
    c.close()
    return filas


def pdf_minimo(texto: str) -> bytes:
    """Un PDF de una página con `texto` (Helvetica), con su tabla xref correcta."""
    flujo = f"BT /F1 12 Tf 72 712 Td ({texto}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(flujo)).encode() + b" >>\nstream\n" + flujo + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


# ---------------------------------------------------------------- troceo
def test_trocear_tamano_y_solape():
    texto = " ".join(f"palabra{i}" for i in range(2000))
    trozos = trocear(texto)
    assert len(trozos) > 3
    assert all(len(t) <= TOKENS_FRAGMENTO * CHARS_POR_TOKEN for t in trozos)
    for a, b in zip(trozos, trozos[1:]):          # ~64 tokens repetidos entre uno y el siguiente
        assert b.split()[0] in a.split()
    assert trocear("") == [] and trocear("corto") == ["corto"]


def test_trocear_corta_en_parrafos():
    parrafos = ["Párrafo %d. " % i + "x" * 600 for i in range(6)]
    for t in trocear("\n\n".join(parrafos)):
        assert t.startswith("Párrafo") or t.startswith("x"), t[:30]


def test_migracion_registra_el_alias_embeddings(client):
    m = {x["alias"]: x for x in client.get("/modelos").json()["modelos"]}
    assert m["embeddings"]["etiqueta"] == "nomic-embed-text"


# ---------------------------------------------------------------- TST-083
def test_tst083_indexar_crea_fragmentos_con_embedding(client, fake, tmp_path):
    kb = crear_base(client)
    largo = "\n\n".join(f"Sección {i}: " + SUBGHZ * 3 for i in range(8))
    pegar(client, kb, largo, "Guía SubGHz")
    base = client.get("/kb").json()["bases"][0]
    assert base["documentos"] == 1 and base["pendientes"] == 1 and base["fragmentos"] == 0

    evs = indexar(client, kb)
    tipos = [e for e, _ in evs]
    assert tipos[0] == "inicio" and tipos[-1] == "fin" and "progreso" in tipos and "documento" in tipos
    total = evs[0][1]["fragmentos"]
    assert total > 1
    prog = [d for e, d in evs if e == "progreso"]
    assert prog[-1]["hechos"] == prog[-1]["total"] == total

    filas = chunks(tmp_path, kb)
    assert len(filas) == total
    for i, f in enumerate(filas):
        v = np.frombuffer(f["embedding"], dtype=np.float32)
        assert v.shape == (DIM_EMBED,) and abs(float(np.linalg.norm(v)) - 1) < 1e-4   # float32 768, normalizado
        assert f["origen"] == "pegado" and f["orden"] == i and f["texto"]
    # nomic: prefijo search_document: y num_ctx 8192
    assert fake.embeds and all(t.startswith(PREFIJO_DOC) for b in fake.embeds for t in b["input"])
    assert all(b["options"]["num_ctx"] == 8192 and b["model"] == EMBED for b in fake.embeds)
    fin = evs[-1][1]["base"]
    assert fin["pendientes"] == 0 and fin["fragmentos"] == total

    # Solo pendientes: no re-embebe lo ya indexado. Reindexar (BTN-105) rehace sin duplicar.
    n = len(fake.embeds)
    assert indexar(client, kb)[0][1]["documentos"] == 0 and len(fake.embeds) == n
    evs = indexar(client, kb, todo=True)
    assert evs[0][1]["documentos"] == 1 and len(chunks(tmp_path, kb)) == total


def test_tst083_importa_carpeta_md_txt_pdf(client, tmp_path):
    carpeta = tmp_path / "docs"
    (carpeta / "sub").mkdir(parents=True)
    (carpeta / "fam.md").write_text("# Manifiesto\n" + FAM, encoding="utf-8")
    (carpeta / "sub" / "gui.txt").write_text(GUI, encoding="utf-8")
    (carpeta / "subghz.pdf").write_bytes(pdf_minimo("SubGHz transmite en 433 MHz"))
    (carpeta / "ignorar.exe").write_bytes(b"MZ")
    (carpeta / ".git").mkdir()
    (carpeta / ".git" / "x.md").write_text("no", encoding="utf-8")
    kb = crear_base(client)
    r = client.post(f"/kb/{kb}/documentos", json={"ruta": str(carpeta)})
    assert r.status_code == 201, r.text
    docs = {d["titulo"]: d for d in r.json()["documentos"]}
    assert set(docs) == {"fam.md", "sub/gui.txt", "subghz.pdf"}
    det = client.get(f"/kb/{kb}").json()["lista"]
    assert any(d["origen"].endswith("subghz.pdf") and d["caracteres"] > 10 for d in det)   # PDF con texto
    indexar(client, kb)
    assert {f["origen"] for f in chunks(tmp_path, kb)} == {str(carpeta / "fam.md"), str(carpeta / "sub" / "gui.txt"),
                                                           str(carpeta / "subghz.pdf")}
    # Reimportar la misma carpeta actualiza (no duplica) y deja pendientes
    r = client.post(f"/kb/{kb}/documentos", json={"ruta": str(carpeta)})
    assert all(not d["nuevo"] for d in r.json()["documentos"])
    assert r.json()["base"]["documentos"] == 3 and r.json()["base"]["pendientes"] == 3


def test_tst083_subir_archivo_y_validaciones(client):
    import base64
    kb = crear_base(client)
    r = client.post(f"/kb/{kb}/documentos", json={"nombre": "notas.md",
                                                  "contenido_b64": base64.b64encode(FAM.encode()).decode()})
    assert r.status_code == 201 and r.json()["documentos"][0]["titulo"] == "notas.md"
    r = client.post(f"/kb/{kb}/documentos", json={"nombre": "x.exe", "contenido_b64": "TVo="})
    assert r.json()["error"]["codigo"] == "TIPO_NO_ADMITIDO"
    assert client.post(f"/kb/{kb}/documentos", json={"contenido": "   "}).json()["error"]["codigo"] == "DOCUMENTO_VACIO"
    assert client.post(f"/kb/{kb}/documentos", json={"ruta": "relativa/x"}).json()["error"]["codigo"] == "RUTA_INVALIDA"
    assert client.post("/kb", json={"nombre": "flipper zero"}).json()["error"]["codigo"] == "KB_DUPLICADA"
    assert client.post("/kb/999/documentos", json={"contenido": "x"}).status_code == 404


def test_tst083_semilla_flipper_desde_el_firmware(client, tmp_path):
    fw = tmp_path / "firmware"
    (fw / "documentation" / "js").mkdir(parents=True)
    (fw / "applications" / "examples" / "example_thermo").mkdir(parents=True)
    (fw / "ReadMe.md").write_text("# Firmware\nLéeme.", encoding="utf-8")
    (fw / "documentation" / "AppManifests.md").write_text(FAM, encoding="utf-8")
    (fw / "documentation" / "js" / "js_gui.md").write_text(GUI, encoding="utf-8")
    (fw / "applications" / "examples" / "example_thermo" / "application.fam").write_text(
        'App(appid="example_thermo", apptype=FlipperAppType.EXTERNAL)', encoding="utf-8")
    (fw / "applications" / "examples" / "example_thermo" / "thermo.c").write_text(
        "int32_t example_thermo_main(void* p) { return 0; }", encoding="utf-8")
    kb = crear_base(client)
    r = client.post(f"/kb/{kb}/documentos", json={"ruta": str(fw), "semilla": True})
    assert r.status_code == 201, r.text
    titulos = {d["titulo"] for d in r.json()["documentos"]}
    assert titulos == {"ReadMe.md", "documentation/AppManifests.md", "documentation/js/js_gui.md",
                       "applications/examples/example_thermo/application.fam",
                       "applications/examples/example_thermo/thermo.c"}
    det = client.get(f"/kb/{kb}").json()["lista"]
    assert det[0]["titulo"] == "ReadMe.md"
    otra = tmp_path / "otra"
    otra.mkdir()
    r = client.post(f"/kb/{kb}/documentos", json={"ruta": str(otra), "semilla": True})
    assert r.json()["error"]["codigo"] == "SEMILLA_NO_ENCONTRADA"


def test_tst083_sin_modelo_de_embeddings(client, fake):
    fake.instalados.discard(EMBED)
    kb = crear_base(client)
    pegar(client, kb, SUBGHZ)
    evs = indexar(client, kb)
    err = [d for e, d in evs if e == "error"]
    assert err and err[0]["codigo"] == "MODELO_FALTANTE" and err[0]["alias"] == "embeddings"
    assert client.get("/kb").json()["bases"][0]["pendientes"] == 1     # queda pendiente, nada a medias


# ---------------------------------------------------------------- TST-084
def base_tres_temas(client) -> int:
    kb = crear_base(client)
    for titulo, texto in (("SubGHz", SUBGHZ), ("Manifiestos", FAM), ("GUI", GUI)):
        client.post(f"/kb/{kb}/documentos", json={"contenido": texto, "titulo": titulo, "origen": f"docs/{titulo}.md"})
    indexar(client, kb)
    return kb


def test_tst084_buscar_por_coseno_con_origen(client, fake):
    kb = base_tres_temas(client)
    fake.embeds.clear()
    r = client.post(f"/kb/{kb}/buscar", json={"query": "¿En qué frecuencia MHz transmite SubGHz?", "k": 3})
    assert r.status_code == 200, r.text
    frs = r.json()["fragmentos"]
    assert [f["n"] for f in frs] == [1, 2, 3]
    assert frs[0]["titulo"] == "SubGHz" and frs[0]["origen"] == "docs/SubGHz.md" and "433" in frs[0]["texto"]
    scores = [f["score"] for f in frs]
    assert scores == sorted(scores, reverse=True) and scores[0] > scores[1]
    assert fake.embeds[0]["input"][0].startswith(PREFIJO_QUERY)

    r = client.post(f"/kb/{kb}/buscar", json={"query": "manifiesto application.fam appid uFBT", "k": 1})
    assert [f["titulo"] for f in r.json()["fragmentos"]] == ["Manifiestos"]


def test_tst084_base_vacia_y_errores(client):
    kb = crear_base(client)
    r = client.post(f"/kb/{kb}/buscar", json={"query": "hola"})
    assert r.json() == {"kb_id": kb, "nombre": "Flipper Zero", "fragmentos": [], "indexada": False}
    assert client.post("/kb/999/buscar", json={"query": "x"}).status_code == 404
    assert client.post(f"/kb/{kb}/buscar", json={"query": "  "}).json()["error"]["codigo"] == "CONSULTA_VACIA"


# ---------------------------------------------------------------- TST-085
def test_tst085_chat_con_base_activa_inyecta_contexto_y_cita(client, fake):
    kb = base_tres_temas(client)
    fake.respuesta = ["Transmite en 433 MHz ", "según la guía [1]."]
    pregunta = "¿En qué frecuencia MHz transmite SubGHz?"
    r = client.post("/chat", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo", "texto": pregunta,
                                   "kb_id": kb, "forzar": True})
    evs = eventos(r.text)
    fuentes = [d for e, d in evs if e == "fuentes"]
    assert fuentes and fuentes[0]["nombre"] == "Flipper Zero"
    assert fuentes[0]["fragmentos"][0]["origen"] == "docs/SubGHz.md"
    fin = [d for e, d in evs if e == "fin"][0]
    assert fin["fuentes_citadas"] == [1]

    # Lo que vio el modelo: fragmentos numerados con su origen, ANTES de la pregunta.
    ultimo = fake.chats[-1]["messages"][-1]
    assert ultimo["role"] == "user"
    c = ultimo["content"]
    assert "Base de conocimiento «Flipper Zero»" in c and "[1] Fuente: docs/SubGHz.md — SubGHz" in c
    assert "433" in c and c.index("[1] Fuente") < c.index(pregunta) < c.index("Fuentes: [n]")

    # Se guarda la pregunta original (sin fragmentos) y las fuentes con lo citado (BTN-107 tras recargar).
    msgs = client.get(f"/conversaciones/{fin['sesion_id']}/mensajes").json()["mensajes"]
    assert msgs[0]["contenido"] == pregunta
    guardadas = json.loads(msgs[1]["fuentes"])
    assert guardadas["citadas"] == [1] and guardadas["fragmentos"][0]["titulo"] == "SubGHz"

    # El modelo de embeddings convive con el del chat: no se descarga al cambiar de modelo.
    assert EMBED not in fake.descargados_de_ram


def test_tst085_sin_base_no_hay_fuentes(client, fake):
    kb = base_tres_temas(client)
    fake.embeds.clear()
    r = client.post("/chat", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo", "texto": "hola",
                                   "forzar": True})
    evs = eventos(r.text)
    assert not [e for e, _ in evs if e == "fuentes"] and not fake.embeds
    assert fake.chats[-1]["messages"][-1]["content"] == "hola"
    fin = [d for e, d in evs if e == "fin"][0]
    assert fin["fuentes_citadas"] is None
    msgs = client.get(f"/conversaciones/{fin['sesion_id']}/mensajes").json()["mensajes"]
    assert msgs[1]["fuentes"] is None and kb


def test_tst085_base_sin_indexar_avisa_y_responde(client, fake):
    kb = crear_base(client)
    pegar(client, kb, SUBGHZ)            # sin indexar
    r = client.post("/chat", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo", "texto": "hola",
                                   "kb_id": kb, "forzar": True})
    evs = eventos(r.text)
    f = [d for e, d in evs if e == "fuentes"][0]
    assert f["fragmentos"] == [] and "aviso" in f
    assert [e for e, _ in evs][-1] == "fin"
    r = client.post("/chat", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo", "texto": "hola",
                                   "kb_id": 999, "forzar": True})
    assert [d for e, d in eventos(r.text) if e == "error"][0]["codigo"] == "KB_NO_EXISTE"


def test_tst085_nube_audita_la_base(client, nube, fake):
    kb = base_tres_temas(client)
    client.put("/ajustes", json={"nube.backend": "api", "nube.api_key": "sk-ant-prueba", "nube.activada": "1"})
    r = client.post("/chat", json={"modo": "scripts", "tier": "nube", "esfuerzo": "bajo",
                                   "texto": "¿Frecuencia de SubGHz en MHz?", "kb_id": kb})
    assert [e for e, _ in eventos(r.text)][-1] == "fin", r.text
    assert "[1] Fuente: docs/SubGHz.md" in nube.envios[-1]["mensajes"][-1]["content"]
    c = sqlite3.connect(client.app.state.db.path)
    det = json.loads(c.execute("SELECT detalle FROM audit_log WHERE tipo = 'escalado_nube' ORDER BY id DESC").fetchone()[0])
    c.close()
    assert det["kb"] == "Flipper Zero" and det["fragmentos_kb"] >= 1


def test_utilidades_de_citas():
    assert citadas("Ver [2] y [1], otra vez [2]; [9] no existe", 3) == [2, 1]
    b = bloque_contexto("KB", [{"n": 1, "origen": r"C:\fw\documentation\js\js_gui.md", "titulo": "GUI", "texto": "t"}], "¿q?")
    assert "[1] Fuente: documentation/js/js_gui.md — GUI" in b and b.index("¿q?") < b.index("Fuentes: [n]")


def test_borrar_base_y_documento(client, tmp_path):
    kb = base_tres_temas(client)
    client.put("/ajustes", json={"estado.kb": str(kb)})
    doc = client.get(f"/kb/{kb}").json()["lista"][0]["id"]
    assert client.delete(f"/kb/{kb}/documentos/{doc}").status_code == 204
    assert client.get(f"/kb/{kb}").json()["lista"].__len__() == 2
    assert client.delete(f"/kb/{kb}").status_code == 204
    assert client.get("/kb").json() == {**client.get("/kb").json(), "bases": [], "activa": ""}
    assert chunks(tmp_path) == []


# ---------------------------------------------------------------- UI (Edge headless): SCR-050 + BTN-106/107
@pytest.mark.skipif(not __import__("tests.test_rama6", fromlist=["EDGE"]).EDGE.exists(), reason="Edge no instalado")
def test_ui_scr050_toggle_y_fuentes_citadas(tmp_path, fake):
    import asyncio
    from backend.main import create_app
    from tests import test_rama6 as t6
    from tests.conftest import TOKEN
    fake.respuesta = ["Usa 433 MHz ", "como dice la guía [1]."]
    app = create_app(db_path=tmp_path / "forja.db", ollama_transport=fake.transport(), precargar=False, token=TOKEN)
    with t6._Servidor(app) as s:
        async def pasos(ev, esperar):
            out = {}
            await ev("window.__errs = []; addEventListener('error', e => __errs.push(e.message));"
                     "addEventListener('unhandledrejection', e => __errs.push(String(e.reason)))")
            out["chip_inicial"] = await ev("document.querySelector('#btn-kb-txt').textContent")
            await ev("document.querySelector('#btn-kb').click()")                                  # SCR-050
            await esperar("!document.querySelector('#scr-050').hidden")
            await ev("document.querySelector('#kb-nueva-nombre').value = 'Flipper Zero';"
                     "document.querySelector('#btn-kb-nueva').click()")                            # BTN-103
            await esperar("!!document.querySelector('#kb-pegar-txt')")
            await ev(f"document.querySelector('#kb-pegar-titulo').value = 'Guía SubGHz';"
                     f"document.querySelector('#kb-pegar-txt').value = {json.dumps(SUBGHZ * 4)};"
                     "document.querySelector('#btn-kb-anadir').click()")                           # BTN-104
            await esperar("/Indexado: 1 documento/.test(document.querySelector('#kb-det .kb-msg')?.textContent || '')")
            out["doc"] = await ev("document.querySelector('.kb-docs .kb-doc-e').textContent")
            await ev("document.querySelector('#btn-kb-reindexar').click()")                        # BTN-105
            await esperar("/Indexado/.test(document.querySelector('#kb-det .kb-msg')?.textContent || '')"
                          " && !document.querySelector('.kb-prog')")
            await ev("document.querySelector('#kb-probar-q').value = 'frecuencia SubGHz';"
                     "document.querySelector('#kb-probar button').click()")
            await esperar("!!document.querySelector('.kb-res li')")
            await ev("document.querySelector('#kb-cerrar').click()")
            out["chip"] = await ev("[document.querySelector('#btn-kb-txt').textContent,"
                                   " document.querySelector('#btn-kb-usar').getAttribute('aria-pressed')]")  # BTN-106
            await ev("document.querySelector('#entrada').value = '¿Qué frecuencia usa SubGHz?';"
                     "document.querySelector('#btn-enviar').click()")
            await esperar("!!document.querySelector('.msg-ia .kb-ver')", 20)                       # BTN-107
            out["boton"] = await ev("document.querySelector('.msg-ia .kb-ver').textContent")
            await ev("document.querySelector('.msg-ia .kb-ver').click()")
            await esperar("!!document.querySelector('.kb-lista-f li.citada')")
            out["citada"] = await ev("document.querySelector('.kb-lista-f li.citada summary').textContent")
            # Toggle apagado: el siguiente mensaje no lleva kb_id
            await ev("document.querySelector('#btn-kb-usar').click()")
            out["apagado"] = await ev("document.querySelector('#btn-kb-usar').getAttribute('aria-pressed')")
            out["k"] = await ev("document.querySelector('#kb-k').value")
            out["errs"] = await ev("window.__errs")
            await asyncio.sleep(1)          # guardarEstado() va con 250 ms de retardo: que llegue antes de cerrar
            return out
        r = asyncio.run(t6._cdp(f"http://127.0.0.1:{s.puerto}/", tmp_path / "edge1", pasos))
        assert r["chip_inicial"] == "Sin base" and r["errs"] == []
        assert "fragmento" in r["doc"]
        assert r["chip"] == ["Usar base: Flipper Zero", "true"]
        assert r["boton"] == "Ver fuentes citadas (1)" and "[1]" in r["citada"] and "Guía SubGHz" in r["citada"]
        assert r["apagado"] == "false" and r["k"] == "6"
        assert any(c["messages"][-1]["content"].startswith("[Base de conocimiento") for c in fake.chats)

        async def tras_recargar(ev, esperar):        # las fuentes sobreviven: vienen de messages.fuentes
            await esperar("!!document.querySelector('.msg-ia .kb-ver')")
            return await ev("[document.querySelector('.msg-ia .kb-ver').textContent, document.querySelector('#btn-kb-usar').getAttribute('aria-pressed')]")
        r2 = asyncio.run(t6._cdp(f"http://127.0.0.1:{s.puerto}/", tmp_path / "edge2", tras_recargar))
        assert r2 == ["Ver fuentes citadas (1)", "false"]


def test_salud_no_toma_el_de_embeddings_por_el_modelo_cargado(client, fake):
    fake.cargados = [EMBED, "qwen2.5-coder:3b"]
    assert client.get("/salud").json()["modelo_cargado"] == "qwen2.5-coder:3b"
    fake.cargados = [EMBED]
    assert client.get("/salud").json()["modelo_cargado"] is None


def test_top_k_del_chat_por_defecto_6_y_ajustable(client, fake):
    """Doc 24 rev. 18: top-k recomendado 5–6; `kb.k` lo ajusta (1–10)."""
    kb = crear_base(client)
    for i in range(8):
        client.post(f"/kb/{kb}/documentos", json={"contenido": f"Documento {i}: " + SUBGHZ, "titulo": f"D{i}",
                                                  "origen": f"docs/d{i}.md"})
    indexar(client, kb)

    def n_fuentes():
        r = client.post("/chat", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo",
                                       "texto": "frecuencia SubGHz", "kb_id": kb, "forzar": True})
        return len([d for e, d in eventos(r.text) if e == "fuentes"][0]["fragmentos"])

    assert n_fuentes() == 6
    assert client.put("/ajustes", json={"kb.k": "2"}).status_code == 200
    assert n_fuentes() == 2
    assert client.put("/ajustes", json={"kb.k": "50"}).json()["error"]["codigo"] == "AJUSTE_INVALIDO"
