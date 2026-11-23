"""Pasada de optimización y robustez (2026-11-23): precarga con el mismo num_ctx y el prompt de sistema,
num_thread único, nomic-embed-text precalentado, Ollama que se corta a media respuesta, mensajes claros."""
import json
import time

import httpx
from fastapi.testclient import TestClient

from backend.config import NUM_CTX_DEFECTO, NUM_THREAD
from backend.main import create_app
from tests.conftest import TOKEN, eventos


def _app(tmp_path, fake, **kw):
    app = create_app(db_path=tmp_path / "forja.db", ollama_transport=fake.transport(), token=TOKEN, **kw)
    return app


def _esperar(cond, segundos=5.0):
    fin = time.time() + segundos
    while time.time() < fin and not cond():
        time.sleep(0.05)
    return cond()


def test_precarga_usa_num_ctx_del_chat_y_cachea_el_prompt_de_sistema(tmp_path, fake):
    """Antes se cargaba sin num_ctx y el primer mensaje recargaba el modelo (~6 s medidos)."""
    app = _app(tmp_path, fake, precargar=True)
    with TestClient(app) as c:
        c.headers.update({"X-Forja-Token": TOKEN})
        assert _esperar(lambda: fake.chats)
        pre = fake.chats[0]
        assert pre["model"] == "qwen2.5-coder:3b"
        assert pre["options"]["num_ctx"] == NUM_CTX_DEFECTO and pre["options"]["num_predict"] == 1
        assert pre["messages"][0]["role"] == "system" and "FORJA" in pre["messages"][0]["content"]
        # El primer mensaje lleva EXACTAMENTE el mismo prompt de sistema (prefijo en caché) y las mismas opciones
        # de carga: num_ctx y num_thread iguales → Ollama no recarga.
        esfuerzo = app.state.db.get_setting("estado.esfuerzo", "bajo")     # el último que usaste
        eventos(c.post("/chat", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": esfuerzo, "texto": "hola"}).text)
        chat = fake.chats[-1]
        assert chat["messages"][0]["content"] == pre["messages"][0]["content"]
        assert chat["options"]["num_ctx"] == pre["options"]["num_ctx"]
        assert chat["options"]["num_thread"] == pre["options"]["num_thread"] == NUM_THREAD


def test_num_thread_igual_en_todas_las_peticiones(client, fake):
    """Si num_thread (o num_ctx) cambia entre peticiones, Ollama recarga el modelo."""
    eventos(client.post("/chat", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo", "texto": "hola"}).text)
    fake.json_respuestas.append(json.dumps({"texto_limpio": "estudiar", "dia_asignado": None, "prioridad": 3}))
    lista = client.get("/listas").json()["listas"][0]["id"]
    r = client.post("/tareas", json={"lista_id": lista, "texto": "estudiar a final de mes"})
    assert r.status_code in (200, 201), r.text
    assert len({ch["model"] for ch in fake.chats}) == 2      # coder (chat) + instruct (tareas)
    assert fake.chats and all(ch["options"].get("num_thread") == NUM_THREAD for ch in fake.chats)
    assert all(ch["options"]["num_ctx"] >= NUM_CTX_DEFECTO for ch in fake.chats)


def test_precarga_calienta_embeddings_si_hay_base_activa(tmp_path, fake):
    app = _app(tmp_path, fake, precargar=False)
    with TestClient(app) as c:
        c.headers.update({"X-Forja-Token": TOKEN})
        kid = c.post("/kb", json={"nombre": "Flipper"}).json()["id"]
        c.post(f"/kb/{kid}/documentos", json={"titulo": "fam", "contenido": "application.fam define la app."})
        eventos(c.post(f"/kb/{kid}/indexar", json={}).text)
        c.put("/ajustes", json={"estado.kb": str(kid)})
    fake.embeds.clear()
    with TestClient(_app(tmp_path, fake, precargar=True)):
        assert _esperar(lambda: fake.embeds)
    e = fake.embeds[0]
    assert e["keep_alive"] == "4h" and e["input"][0].startswith("search_query: ")
    assert e["options"]["num_thread"] == NUM_THREAD


def test_sin_base_activa_no_carga_embeddings(tmp_path, fake):
    with TestClient(_app(tmp_path, fake, precargar=True)):
        assert _esperar(lambda: fake.chats)
    assert fake.embeds == []


class _Corte(httpx.AsyncByteStream):
    """Respuesta que manda un trozo y luego se corta (Ollama cerrado a media generación)."""

    async def __aiter__(self):
        yield b'{"message": {"role": "assistant", "content": "Primera parte"}, "done": false}\n'
        raise httpx.RemoteProtocolError("peer closed connection without sending complete message body")


def test_ollama_se_corta_a_media_respuesta(tmp_path, fake):
    def handle(req):
        if req.url.path == "/api/chat":
            return httpx.Response(200, stream=_Corte())
        return fake.handle(req)

    app = create_app(db_path=tmp_path / "forja.db", ollama_transport=httpx.MockTransport(handle), token=TOKEN,
                     precargar=False)
    with TestClient(app) as client:
        client.headers.update({"X-Forja-Token": TOKEN})
        evs = eventos(client.post("/chat", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo",
                                                 "texto": "hazme un script"}).text)
        err = [d for e, d in evs if e == "error"]
        assert err and err[0]["codigo"] == "OLLAMA_CAIDO" and "media respuesta" in err[0]["mensaje"]
        # Lo generado no se pierde: se guarda marcado como interrumpido.
        sid = next(d for e, d in evs if e == "inicio")["sesion_id"]
        msgs = client.get(f"/conversaciones/{sid}/mensajes").json()["mensajes"]
        assert msgs[-1]["rol"] == "assistant" and msgs[-1]["contenido"].startswith("Primera parte")


def test_ollama_apagado_mensaje_claro(client, fake):
    fake.up = False
    evs = eventos(client.post("/chat", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo", "texto": "x"}).text)
    err = [d for e, d in evs if e == "error"][0]
    assert err["codigo"] == "OLLAMA_CAIDO" and "localhost:11434" in err["mensaje"]


# --- Academia: lo que salió en la prueba con el modelo real (qwen3 4B instruct) -------------------------
def test_pista_que_suelta_la_respuesta_se_reintenta_y_sin_cabecera(tmp_path, fake):
    from tests.test_academia import SIN_WSL, declarar
    app = create_app(db_path=tmp_path / "forja.db", ollama_transport=fake.transport(), precargar=False,
                     token=TOKEN, lab_detector=SIN_WSL)
    with TestClient(app) as c:
        c.headers.update({"X-Forja-Token": TOKEN})
        c.post("/academia/enrolar", json={"path_id": 4})
        declarar(c)
        fake.respuesta = ["Pista de nivel 1 (empujón):\n", "El protocolo se llama Kerberos."]
        antes = len(fake.chats)
        p = c.post("/academia/pista", json={"seccion_id": 17}).json()
        assert len(fake.chats) - antes == 2                           # borrador con la respuesta → reintento
        assert "IMPORTANTE" in fake.chats[-1]["messages"][-1]["content"]
        assert "kerberos" not in p["texto"].lower() and not p["texto"].lower().startswith("pista de nivel")
        fake.respuesta = ["Piensa en quién emite los tickets."]
        antes = len(fake.chats)
        c.post("/academia/pista", json={"seccion_id": 17})
        assert len(fake.chats) - antes == 1                           # sin fuga, una sola llamada


def test_attackbox_sin_url_explica_que_hacer():
    from backend.modes.laboratorio import LabError, Laboratorio
    try:
        Laboratorio._validar_url("")
    except LabError as e:
        assert e.codigo == "ATTACKBOX_SIN_URL" and "TryHackMe" in e.mensaje
    else:
        raise AssertionError("una URL vacía debe dar ATTACKBOX_SIN_URL")


def test_descarga_que_no_avanza_explica_que_hacer():
    from backend.main import mensaje_descarga
    m = mensaje_descarga("Get \"https://x.r2.cloudflarestorage.com/...\": net/http: TLS handshake timeout", "nomic-embed-text")
    assert "otra red" in m and "ollama create" in m and "nomic-embed-text" in m
    assert "Ajustes › Modelos" in mensaje_descarga("pull model manifest: file does not exist", "qwen9:1b")
    assert mensaje_descarga("algo raro", "x").startswith("Ollama no pudo descargar x")
