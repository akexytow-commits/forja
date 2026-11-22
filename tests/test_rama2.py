"""Rama 2: estimador, escalado a Nube y troceo (TST-010/011/012/023/044/061)."""
import pytest

from backend import estimator
from tests.conftest import eventos

FIRMWARE = "Hazme el firmware completo de Flipper Zero con todas las funciones de radio sub-ghz"


def chat(client, texto, **kw):
    cuerpo = {"modo": "scripts", "tier": "pequeno", "esfuerzo": "medio", "texto": texto, **kw}
    return eventos(client.post("/chat", json=cuerpo).text)


def activar_nube(client):
    assert client.put("/ajustes", json={"nube.backend": "api", "nube.api_key": "sk-ant-prueba",
                                          "nube.activada": "1"}).status_code == 200


# --- estimador puro ------------------------------------------------------------------
def test_peticion_corta_cabe_en_local():
    est = estimator.estimar("scripts", "pequeno", "medio", "explícame qué hace este bucle for")
    assert est["veredicto"] == "CABE_LOCAL" and est["salida_prevista"] == 300


def test_tst010_contexto_que_no_cabe():
    texto = "palabra " * 7000  # ~9100 tokens > tope 8192 del tier grande
    est = estimator.estimar("scripts", "grande", "medio", texto)
    assert est["veredicto"] == "RECOMENDADO_NUBE" and est["motivo_codigo"] == "contexto"


def test_tst023_firmware_completo_recomienda_nube():
    est = estimator.estimar("scripts", "pequeno", "medio", FIRMWARE)
    assert est["veredicto"] == "RECOMENDADO_NUBE"
    assert est["motivo_codigo"] == "salida"


def test_veredicto_justo_por_complejidad():
    est = estimator.estimar("scripts", "pequeno", "medio", "Escribe un driver con DMA e interrupciones para el bus SPI")
    assert est["veredicto"] == "JUSTO" and 45 <= est["complejidad"] < 70


def test_umbrales_configurables():
    texto = "Escribe un driver con DMA e interrupciones para el bus SPI"
    est = estimator.estimar("scripts", "pequeno", "medio", texto, umbrales={"complejidad_justo": 90, "complejidad_nube": 95})
    assert est["veredicto"] == "CABE_LOCAL"


@pytest.mark.parametrize("datos,n", [
    ({"pasos": [{"texto": "a"}, {"texto": "b", "estimacion_min": "x"}]}, 2),
    (["uno", "dos", "tres"], 3),
    ({"pasos": [{"texto": "solo uno"}]}, 0),
    ("basura", 0),
])
def test_sanear_pasos(datos, n):
    pasos = estimator.sanear_pasos(datos)
    assert len(pasos) == n
    assert all(5 <= p["estimacion_min"] <= 600 for p in pasos)


def test_troceo_heuristico_respeta_lista_del_usuario():
    pasos = estimator.troceo_heuristico("Haz esto:\n1. leer el sensor\n2. guardar en SD\n3. mostrar en pantalla")
    assert [p["texto"] for p in pasos] == ["leer el sensor", "guardar en SD", "mostrar en pantalla"]


# --- flujo en /chat ------------------------------------------------------------------
def test_tst011_sin_nube_sugiere_y_no_envia_nada(client, fake, nube):
    evs = chat(client, FIRMWARE)
    assert len(evs) == 1 and evs[0][0] == "sugerencia_escalado"
    sug = evs[0][1]
    assert sug["veredicto"] == "RECOMENDADO_NUBE" and sug["nube_activada"] is False
    assert fake.chats == [] and nube.envios == []
    assert client.get("/conversaciones").json()["conversaciones"] == []  # nada guardado aún


def test_forzar_genera_en_local_pese_al_aviso(client, fake):
    evs = chat(client, FIRMWARE, forzar=True)
    assert evs[0][0] == "inicio" and evs[-1][0] == "fin"
    assert len(fake.chats) == 1


def test_nube_rechazada_sin_clave(client, nube):
    evs = chat(client, FIRMWARE, tier="nube", forzar=True)
    assert evs[0][1]["codigo"] == "NUBE_NO_ACTIVADA" and nube.envios == []


def test_tst061_clave_en_keyring_no_en_bbdd(client, keyring_memoria):
    activar_nube(client)
    db = client.app.state.db
    assert keyring_memoria.datos[("FORJA", "anthropic_api_key")] == "sk-ant-prueba"
    volcado = " ".join(str(v) for r in db.query("SELECT * FROM settings") for v in r.values())
    assert "sk-ant-prueba" not in volcado
    aj = client.get("/ajustes").json()["ajustes"]
    assert aj["nube.tiene_clave"] == "1" and aj["nube.activada"] == "1"
    assert "sk-ant-prueba" not in client.get("/ajustes").text
    assert client.get("/salud").json()["nube_activada"] is True
    # Borrar la clave desactiva la Nube.
    client.put("/ajustes", json={"nube.api_key": ""})
    assert client.get("/ajustes").json()["ajustes"]["nube.activada"] == "0"


def test_tst012_escalado_aceptado_se_audita(client, fake, nube):
    activar_nube(client)
    sug = chat(client, FIRMWARE)[0][1]
    assert sug["nube_activada"] is True and "Anthropic" in sug["resumen_envio"]["texto"]

    evs = chat(client, FIRMWARE, tier="nube", forzar=True, esfuerzo="extra")
    assert evs[0][1]["modelo"] == "claude-opus-5-5"
    assert [e for e, _ in evs if e != "telemetria"] == ["inicio", "thinking", "token", "fin"]
    assert nube.envios[0]["esfuerzo"] == "extra" and fake.chats == []
    assert nube.envios[0]["mensajes"][-1] == {"role": "user", "content": FIRMWARE}

    aud = client.get("/auditoria").json()["auditoria"][0]
    assert aud["tipo"] == "escalado_nube"
    assert aud["detalle"]["modelo"] == "claude-opus-5-5" and aud["detalle"]["extracto"] == FIRMWARE[:200]

    sid = evs[0][1]["sesion_id"]
    msgs = client.get(f"/conversaciones/{sid}/mensajes").json()["mensajes"]
    assert msgs[1]["tier"] == "nube" and msgs[1]["thinking"] == "Plan del firmware."


def test_rechazo_de_la_nube(client, nube):
    activar_nube(client)
    nube.stop_reason = "refusal"
    evs = chat(client, "algo", tier="nube")
    assert evs[-1][0] == "error" and evs[-1][1]["codigo"] == "NUBE_RECHAZO"


def test_modelo_nube_configurable(client, nube):
    activar_nube(client)
    assert client.put("/ajustes", json={"nube.modelo": "gpt-loquesea"}).status_code == 400
    client.put("/ajustes", json={"nube.modelo": "claude-sonnet-5-5"})
    chat(client, "hola", tier="nube")
    assert nube.envios[-1]["modelo"] == "claude-sonnet-5-5"


def test_endpoint_estimar(client):
    r = client.post("/estimar", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "medio", "texto": FIRMWARE}).json()
    assert r["veredicto"] == "RECOMENDADO_NUBE" and r["resumen_envio"]["mensajes"] == 1


# --- TST-044 troceo → Organizador de Tareas ------------------------------------------
def test_tst044_troceo_crea_tareas_origen_troceo(client):
    r = client.post("/trocear", json={"texto": FIRMWARE}).json()
    assert r["origen"] == "ia" and len(r["pasos"]) == 3
    db = client.app.state.db
    padre = db.one("SELECT * FROM tasks WHERE id = ?", (r["padre_id"],))
    assert padre["texto"].startswith("Troceo:") and padre["origen"] == "troceo" and padre["list_id"] == r["lista_id"]
    hijas = db.query("SELECT texto, origen FROM tasks WHERE parent_id = ? ORDER BY orden", (r["padre_id"],))
    assert [t["origen"] for t in hijas] == ["troceo"] * 3  # P4: los pasos son subtareas del encargo
    assert hijas[0]["texto"] == "Crear el esqueleto de la app"


def test_troceo_sin_ollama_usa_heuristica(client, fake):
    fake.up = False
    r = client.post("/trocear", json={"texto": FIRMWARE}).json()
    assert r["origen"] == "heuristica" and len(r["pasos"]) == 6
