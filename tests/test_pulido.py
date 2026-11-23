"""Pasada de optimización y robustez (2026-11-23): precarga con el mismo num_ctx y el prompt de sistema,
num_thread único, nomic-embed-text precalentado, Ollama que se corta a media respuesta, mensajes claros."""
import json
import time

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
