"""API local: salud, modelos, chat SSE y persistencia (TST-001/003/004/005/020/060/063)."""
import sqlite3

from backend.db import DB
from tests.conftest import TOKEN, eventos


def chat(client, texto="hazme un script", **kw):
    cuerpo = {"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo", "texto": texto, **kw}
    r = client.post("/chat", json=cuerpo)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    return eventos(r.text)


# --- Rama 0 -----------------------------------------------------------------------
def test_bbdd_creada_con_todas_las_tablas(client):
    db = client.app.state.db
    tablas = {r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"settings", "conversations", "messages", "projects", "task_lists", "tasks", "engagements",
            "findings", "models", "audit_log", "schema_version"} <= tablas
    assert {"learning_paths", "learning_modules", "learning_sections", "learning_progress", "tool_catalog"} <= tablas
    assert db.schema_version() == 9
    assert db.get_setting("ui.tema") == "oscuro"


def test_token_obligatorio(client):
    assert client.get("/salud", headers={"X-Forja-Token": "otro"}).status_code == 401
    r = client.get("/salud", headers={"X-Forja-Token": ""})
    assert r.status_code == 401 and r.json()["error"]["codigo"] == "NO_AUTORIZADO"


def test_index_inyecta_token_y_ui_publica(client):
    r = client.get("/", headers={"X-Forja-Token": ""})
    assert r.status_code == 200 and TOKEN in r.text
    assert client.get("/ui/app.js", headers={"X-Forja-Token": ""}).status_code == 200


def test_tst001_salud_ok(client, fake):
    s = client.get("/salud").json()
    assert s["ollama"] == "ok"
    assert "qwen2.5-coder:3b" in s["modelos_instalados"]
    assert s["faltan_necesarios"] is False
    assert s["nube_activada"] is False
    assert s["disco_libre_mb"] > 0


def test_salud_caido_sin_crashear(client, fake):
    fake.up = False
    s = client.get("/salud").json()
    assert s["ollama"] == "caido" and s["modelos_instalados"] == []


def test_salud_detecta_necesario_faltante(client, fake):
    fake.instalados = {"qwen3:4b"}
    assert client.get("/salud").json()["faltan_necesarios"] is True


# --- Rama 1: modelos ---------------------------------------------------------------
def test_tst003_cargar_descarga_el_anterior(client, fake):
    fake.instalados |= {"qwen2.5-coder:7b"}
    fake.cargados = ["qwen2.5-coder:3b"]
    r = client.post("/modelos/cargar", json={"alias": "grande-codigo"})
    assert r.status_code == 200
    assert fake.cargados == ["qwen2.5-coder:7b"]
    assert "qwen2.5-coder:3b" in fake.descargados_de_ram


def test_cambio_de_tier_en_chat_deja_un_solo_modelo(client, fake):
    fake.instalados |= {"qwen2.5-coder:7b"}
    chat(client, tier="pequeno")
    assert fake.cargados == ["qwen2.5-coder:3b"]
    evs = chat(client, tier="grande")
    assert evs[0][1]["requiere_carga"] is True
    assert fake.cargados == ["qwen2.5-coder:7b"]


def test_tst004_descarga_con_progreso_y_auditoria(client, fake):
    r = client.post("/modelos/descargar", json={"alias": "grande-general"})
    evs = eventos(r.text)
    porcentajes = [d["porcentaje"] for e, d in evs if e == "progreso" and d["porcentaje"] is not None]
    assert porcentajes == [25.0, 100.0]
    assert evs[-1][0] == "fin"
    assert "qwen3:8b" in fake.instalados
    aud = client.get("/auditoria").json()["auditoria"]
    assert aud[0]["tipo"] == "descarga_modelo" and aud[0]["detalle"]["alias"] == "grande-general"


def test_cargar_alias_nube_o_inexistente(client):
    assert client.post("/modelos/cargar", json={"alias": "nube-frontera"}).status_code == 400
    assert client.post("/modelos/cargar", json={"alias": "no-existe"}).status_code == 404


# --- Rama 1: chat -------------------------------------------------------------------
def test_tst020_chat_streaming_y_persistencia(client, fake):
    evs = chat(client, "script python que diga hola")
    tipos = [e for e, _ in evs]
    assert tipos[0] == "inicio" and tipos[-1] == "fin"
    assert tipos.count("token") == len(fake.respuesta)
    assert "".join(d["texto"] for e, d in evs if e == "token") == "".join(fake.respuesta)
    inicio, fin = evs[0][1], evs[-1][1]
    assert inicio["modelo"] == "qwen2.5-coder:3b" and inicio["num_ctx"] == 8192
    assert fin["tokens_out"] == 17 and fin["tokens_por_segundo"] == 8.5

    cuerpo_ollama = fake.chats[-1]
    assert cuerpo_ollama["options"]["num_gpu"] == 0  # CPU-only
    assert "think" not in cuerpo_ollama  # coder: sin thinking nativo
    assert cuerpo_ollama["messages"][0]["role"] == "system"

    msgs = client.get(f"/conversaciones/{inicio['sesion_id']}/mensajes").json()["mensajes"]
    assert [m["rol"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["modelo"] == "qwen2.5-coder:3b" and msgs[1]["tokens_in"] == 42


def test_historial_se_envia_en_el_mismo_hilo(client, fake):
    sid = chat(client, "primera")[0][1]["sesion_id"]
    chat(client, "segunda", sesion_id=sid)
    roles = [m["role"] for m in fake.chats[-1]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    convs = client.get("/conversaciones?modo=scripts").json()["conversaciones"]
    assert len(convs) == 1 and convs[0]["titulo"] == "primera" and convs[0]["n_mensajes"] == 4


def test_thinking_se_emite_y_guarda(client, fake):
    # Forzamos un modelo con thinking en Scripts para probar el canal de razonamiento.
    client.app.state.db.execute("UPDATE models SET etiqueta='qwen3:4b-thinking-2507-q4_K_M', thinking=1 WHERE alias='pequeno-codigo'")
    evs = chat(client, esfuerzo="extra")
    assert fake.chats[-1]["think"] is True
    assert "".join(d["texto_parcial"] for e, d in evs if e == "thinking") == "".join(fake.pensamiento)
    sid = evs[0][1]["sesion_id"]
    msgs = client.get(f"/conversaciones/{sid}/mensajes").json()["mensajes"]
    assert msgs[1]["thinking"] == "".join(fake.pensamiento)


def test_tst005_ollama_caido_emite_error(client, fake):
    fake.up = False
    evs = chat(client)
    assert evs == [("error", {"codigo": "OLLAMA_CAIDO", "mensaje": "Ollama no responde en localhost:11434."})]
    assert client.get("/conversaciones").json()["conversaciones"][0]["n_mensajes"] == 0


def test_modelo_faltante(client, fake):
    fake.instalados = set()
    evs = chat(client)
    assert evs[-1][0] == "error" and evs[-1][1]["codigo"] == "MODELO_FALTANTE"


def test_seguridad_bloqueada_en_backend(client, fake):
    evs = chat(client, modo="seguridad")
    assert evs[0][1]["codigo"] == "MODO_BLOQUEADO"
    assert fake.chats == []


def test_nube_rechazada_sin_activar(client, fake):
    evs = chat(client, tier="nube")
    assert evs[0][1]["codigo"] == "NUBE_NO_ACTIVADA"
    assert fake.chats == []


def test_validacion_uniforme(client):
    r = client.post("/chat", json={"modo": "scripts", "tier": "gigante", "esfuerzo": "bajo", "texto": "x"})
    assert r.status_code == 422 and r.json()["error"]["codigo"] == "PETICION_INVALIDA"


# --- conversaciones / ajustes ---------------------------------------------------------
def test_conversaciones_crud(client):
    c = client.post("/conversaciones", json={"modo": "scripts"}).json()
    r = client.patch(f"/conversaciones/{c['id']}", json={"titulo": "Mi hilo", "archivada": True}).json()
    assert r["titulo"] == "Mi hilo" and r["archivada"] == 1
    assert client.get("/conversaciones?archivadas=true").json()["conversaciones"][0]["id"] == c["id"]
    assert client.delete(f"/conversaciones/{c['id']}").status_code == 204
    assert client.get(f"/conversaciones/{c['id']}/mensajes").status_code == 404


def test_ajustes_solo_claves_permitidas(client):
    assert client.put("/ajustes", json={"ui.tema": "claro", "estado.tier": "grande"}).status_code == 200
    assert client.get("/ajustes").json()["ajustes"]["ui.tema"] == "claro"
    r = client.put("/ajustes", json={"otra.cosa": "1"})
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "AJUSTE_NO_EDITABLE"
    r = client.put("/ajustes", json={"nube.activada": "1"})
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "NUBE_SIN_CLI"
    r = client.put("/ajustes", json={"nube.backend": "api", "nube.activada": "1"})
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "NUBE_SIN_CLAVE"


# --- TST-060 / TST-063 persistencia -------------------------------------------------
def test_tst060_mensajes_sobreviven_al_reinicio(make_client):
    c1 = make_client()
    sid = chat(c1, "recuérdame")[0][1]["sesion_id"]
    c1.put("/ajustes", json={"estado.esfuerzo": "extra"})
    c2 = make_client()  # nueva app sobre el mismo fichero
    msgs = c2.get(f"/conversaciones/{sid}/mensajes").json()["mensajes"]
    assert msgs[0]["contenido"] == "recuérdame"
    assert c2.get("/ajustes").json()["ajustes"]["estado.esfuerzo"] == "extra"


def test_tst063_migracion_con_copia_previa(tmp_path, monkeypatch):
    import backend.db as dbmod

    mig = tmp_path / "migs"
    mig.mkdir()
    (mig / "001_init.sql").write_text((dbmod.MIGRATIONS_DIR / "001_init.sql").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(dbmod, "MIGRATIONS_DIR", mig)
    ruta = tmp_path / "forja.db"
    db = DB(ruta)
    db.execute("INSERT INTO conversations(modo, titulo) VALUES ('scripts', 'dato del usuario')")

    (mig / "002_extra.sql").write_text("ALTER TABLE projects ADD COLUMN color TEXT;", encoding="utf-8")
    db2 = DB(ruta)
    assert db2.schema_version() == 2
    assert db2.one("SELECT titulo FROM conversations")["titulo"] == "dato del usuario"
    copias = list(tmp_path.glob("forja.db.bak-v1-*"))
    assert len(copias) == 1
    with sqlite3.connect(copias[0]) as c:
        assert c.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 1
    assert DB(ruta).migrate() == []  # idempotente
