"""Doc 04 rev. 10 — Modo Seguridad con las variantes Qwen3 4B 2507 (no híbridas) + tope de razonamiento (TST-032b).

Seguridad + bajo  → modelo de código, 768.
Seguridad + medio → pequeno-general = qwen3 INSTRUCT-2507 (sin razonamiento), 1536.
Seguridad + extra → pequeno-razonador = qwen3 THINKING-2507, 3072 + tope; la respuesta forzada la da el instruct.
Red de seguridad (B): con el thinking apagado, un "…</think>" en el contenido es razonamiento, no respuesta.
qwen3 híbrido (8b) con thinking apagado → /no_think en el prompt y num_predict ≥ 768.
"""
import asyncio

import pytest

from backend import estimator
from backend.chat import MotorChat
from backend.ollama_client import FiltroThink, quitar_razonamiento, sin_thinking
from backend.router import resolver

from .conftest import INSTRUCT, RAZONADOR, eventos
from .test_router import REGISTRO as REGISTRO_BASE
from .test_seguridad import autorizado

FFUF = "Dame el comando de ffuf para fuzzear el parámetro q de https://www.acme.com/buscar?q=FUZZ"

# El registro por defecto de la migración 009 (pequeño) + el grande de siempre (qwen3:8b híbrido).
REGISTRO = {
    **REGISTRO_BASE,
    "pequeno-general": {"alias": "pequeno-general", "tier": "pequeno", "etiqueta": INSTRUCT, "thinking": 0},
    "pequeno-razonador": {"alias": "pequeno-razonador", "tier": "pequeno", "etiqueta": RAZONADOR, "thinking": 1},
}


def test_registro_por_defecto_de_la_migracion_009(client):
    filas = {f["alias"]: f for f in client.app.state.db.query("SELECT * FROM models")}
    assert filas["pequeno-general"]["etiqueta"] == INSTRUCT and filas["pequeno-general"]["thinking"] == 0
    assert filas["pequeno-razonador"]["etiqueta"] == RAZONADOR and filas["pequeno-razonador"]["thinking"] == 1
    assert filas["pequeno-razonador"]["tier"] == "pequeno"


@pytest.mark.parametrize("tier,alias,etiqueta", [("pequeno", "pequeno-codigo", "qwen2.5-coder:3b"),
                                                 ("grande", "grande-codigo", "qwen2.5-coder:7b")])
def test_seguridad_bajo_usa_el_modelo_de_codigo(tier, alias, etiqueta):
    plan = resolver("seguridad", tier, "bajo", 0, REGISTRO)
    assert plan.alias == alias and plan.etiqueta_ollama == etiqueta
    assert not plan.thinking_nativo and "enable_thinking" not in plan.params
    assert plan.params["num_predict"] == 768
    assert "Modo Seguridad" in plan.system_prompt          # el perfil sigue siendo el de Seguridad


def test_seguridad_medio_instruct_y_extra_razonador_en_pequeno():
    medio = resolver("seguridad", "pequeno", "medio", 0, REGISTRO)
    assert medio.alias == "pequeno-general" and medio.etiqueta_ollama == INSTRUCT
    assert not medio.thinking_nativo and medio.params["num_predict"] == 1536
    extra = resolver("seguridad", "pequeno", "extra", 0, REGISTRO)
    assert extra.alias == "pequeno-razonador" and extra.etiqueta_ollama == RAZONADOR and extra.thinking_nativo
    assert extra.params["enable_thinking"] is True and extra.params["reasoning_effort"] == "high"
    assert extra.params["num_predict"] == 3072
    assert extra.etiqueta_respuesta == INSTRUCT                      # la respuesta forzada la da el instruct
    # El razonador es solo para Seguridad extra: Tareas extra usa el general (instruct) del tier.
    assert resolver("tareas", "pequeno", "extra", 0, REGISTRO).etiqueta_ollama == INSTRUCT


def test_seguridad_grande_sigue_con_qwen3_8b_hibrido():
    medio = resolver("seguridad", "grande", "medio", 0, REGISTRO)
    assert medio.etiqueta_ollama == "qwen3:8b" and medio.params["enable_thinking"] is False
    assert medio.params["reasoning_effort"] is None and medio.params["num_predict"] == 1536
    extra = resolver("seguridad", "grande", "extra", 0, REGISTRO)
    assert extra.etiqueta_ollama == "qwen3:8b" and extra.params["enable_thinking"] is True
    assert extra.etiqueta_respuesta is None                          # híbrido: el mismo con /no_think


def test_bbdd_antigua_sin_razonador_cae_al_general():
    sin = {k: v for k, v in REGISTRO_BASE.items()}                    # registro de antes de la 009
    extra = resolver("seguridad", "pequeno", "extra", 0, sin)
    assert extra.alias == "pequeno-general" and extra.etiqueta_ollama == "qwen3:4b"


def test_el_resto_no_cambia():
    assert resolver("seguridad", "nube", "bajo", 0, REGISTRO).alias == "nube-frontera"
    assert resolver("tareas", "pequeno", "bajo", 0, REGISTRO).alias == "pequeno-general"
    assert resolver("scripts", "pequeno", "bajo", 0, REGISTRO).params["num_predict"] == 512
    assert resolver("scripts", "pequeno", "extra", 0, REGISTRO).etiqueta_respuesta is None   # coder: sin thinking
    # El estimador conserva su límite de salida (la subida de num_predict es presupuesto de thinking).
    assert estimator.SALIDA_LOCAL_BASE == 2048
    est = estimator.estimar("scripts", "pequeno", "medio", "escríbeme el firmware completo de un dron con 6 módulos")
    assert est["veredicto"] == estimator.RECOMENDADO_NUBE


def test_no_think_solo_para_qwen3_que_razona():
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hola"}]
    opc = {"num_predict": 200, "temperature": 0.1}
    m2, o2 = sin_thinking("qwen3:8b", msgs, opc, False)
    assert m2[-1]["content"] == "hola\n\n/no_think" and m2[0]["content"] == "sys"
    assert o2["num_predict"] == 768 and o2["temperature"] == 0.1
    assert msgs[-1]["content"] == "hola" and opc["num_predict"] == 200        # no muta lo original
    assert sin_thinking("qwen3:8b", m2, o2, False)[0][-1]["content"].count("/no_think") == 1   # idempotente
    assert sin_thinking("qwen3:8b", msgs, {"num_predict": 2500}, False)[1]["num_predict"] == 2500
    for etiqueta, think in [("qwen3:8b", True), ("qwen3:8b", None), ("qwen2.5-coder:3b", False),
                            (INSTRUCT, False)]:                       # el instruct no razona: sin marca
        assert sin_thinking(etiqueta, msgs, opc, think) == (msgs, opc)


def test_chat_seguridad_bajo_y_medio_de_punta_a_punta(client, fake):
    e = autorizado(client)
    cuerpo = {"modo": "seguridad", "tier": "pequeno", "texto": FFUF, "engagement_id": e["id"], "forzar": True}
    evs = eventos(client.post("/chat", json={**cuerpo, "esfuerzo": "bajo"}).text)
    assert next(d for ev, d in evs if ev == "inicio")["modelo"] == "qwen2.5-coder:3b"
    enviado = fake.chats[-1]
    assert enviado["model"] == "qwen2.5-coder:3b" and "think" not in enviado
    assert enviado["options"]["num_predict"] == 768 and "/no_think" not in enviado["messages"][-1]["content"]
    assert any(ev == "fin" for ev, _ in evs)

    evs = eventos(client.post("/chat", json={**cuerpo, "esfuerzo": "medio"}).text)
    enviado = fake.chats[-1]
    assert enviado["model"] == INSTRUCT and "think" not in enviado          # otro modelo, no un flag
    assert enviado["options"]["num_predict"] == 1536 and "/no_think" not in enviado["messages"][-1]["content"]
    assert not any(ev == "thinking" for ev, _ in evs)
    sid = next(d for ev, d in evs if ev == "inicio")["sesion_id"]
    assert client.get(f"/conversaciones/{sid}/mensajes").json()["mensajes"][0]["contenido"] == FFUF


def test_modelos_expone_el_override_para_la_ui(client):
    assert client.get("/modelos").json()["override"] == {
        "seguridad:bajo": {"pequeno": "pequeno-codigo", "grande": "grande-codigo"},
        "seguridad:extra": {"pequeno": "pequeno-razonador"}}


# --- TST-032b: bajo = comando (coder) · medio = instruct · extra = razonador con TOPE → respuesta del instruct --
def _chat_seg(client, eid, esfuerzo, texto=FFUF):
    return eventos(client.post("/chat", json={"modo": "seguridad", "tier": "pequeno", "esfuerzo": esfuerzo,
                                              "texto": texto, "engagement_id": eid, "forzar": True}).text)


def test_tst032b_extra_el_tope_corta_el_thinking_y_responde_el_instruct(client, fake):
    e = autorizado(client)
    fake.pensamiento = ["pienso. "] * 2500            # razonaría sin parar: más que todo el presupuesto (3072)
    evs = _chat_seg(client, e["id"], "extra", "Analiza a fondo este IDOR en www.acme.com/api/pedidos/1042")
    assert next(d for ev, d in evs if ev == "inicio")["modelo"] == RAZONADOR
    tope = next(d for ev, d in evs if ev == "tope_razonamiento")
    assert tope == {"tokens_thinking": 1843, "limite": 1843, "num_predict": 3072, "restante": 1229,
                    "modelo_respuesta": INSTRUCT}                       # 60 %
    assert sum(1 for ev, _ in evs if ev == "thinking") == 1843          # el thinking se cortó ahí

    primera, segunda = fake.chats[-2:]
    assert primera["model"] == RAZONADOR and primera["think"] is True and primera["options"]["num_predict"] == 3072
    assert segunda["model"] == INSTRUCT and "think" not in segunda      # la respuesta forzada: el instruct
    assert segunda["options"]["num_predict"] == 1229
    final = segunda["messages"][-1]["content"]
    assert "<razonamiento>" in final and "pienso." in final and "/no_think" not in final
    assert "acme.com/api/pedidos/1042" in final                         # la pregunta original va en el contexto
    assert RAZONADOR in fake.descargados_de_ram                         # un solo modelo en RAM

    respuesta = "".join(d["texto"] for ev, d in evs if ev == "token")
    assert respuesta == "".join(fake.respuesta)                         # siempre hay respuesta final
    fin = next(d for ev, d in evs if ev == "fin")
    assert fin["tokens_out"] == 17 + 1843 and fin["tokens_por_segundo"] is None
    msgs = client.get(f"/conversaciones/{fin['sesion_id']}/mensajes").json()["mensajes"]
    assert msgs[1]["contenido"] == respuesta and msgs[1]["thinking"].count("pienso.") == 1843
    assert msgs[0]["contenido"].startswith("Analiza a fondo")           # sin marcas en la BBDD


def test_tst032b_extra_sin_llegar_al_tope_es_una_sola_llamada(client, fake):
    e = autorizado(client)
    n = len(fake.chats)
    evs = _chat_seg(client, e["id"], "extra")
    assert not any(ev == "tope_razonamiento" for ev, _ in evs)
    assert len(fake.chats) == n + 1 and fake.chats[-1]["think"] is True and fake.chats[-1]["model"] == RAZONADOR
    assert any(ev == "thinking" for ev, _ in evs) and any(ev == "token" for ev, _ in evs)


def test_tst032b_bajo_y_medio(client, fake):
    e = autorizado(client)
    evs = _chat_seg(client, e["id"], "bajo")
    assert fake.chats[-1]["model"] == "qwen2.5-coder:3b" and any(ev == "token" for ev, _ in evs)
    evs = _chat_seg(client, e["id"], "medio")
    assert fake.chats[-1]["model"] == INSTRUCT
    assert any(ev == "token" for ev, _ in evs) and not any(ev == "tope_razonamiento" for ev, _ in evs)


def test_tst032b_red_de_seguridad_think_mezclado_no_se_muestra_como_respuesta(client, fake):
    """B: un modelo que razona con el thinking apagado mete el razonamiento en el contenido + "</think>"."""
    e = autorizado(client)
    fake.fuga_think = ["Okay, let's tackle ", "this IDOR.</th", "ink>\n\n"]
    evs = _chat_seg(client, e["id"], "medio")
    assert any(ev == "reclasificar" for ev, _ in evs)
    fin = next(d for ev, d in evs if ev == "fin")
    msgs = client.get(f"/conversaciones/{fin['sesion_id']}/mensajes").json()["mensajes"]
    assert msgs[1]["contenido"] == "".join(fake.respuesta)            # solo la respuesta
    assert msgs[1]["thinking"] == "Okay, let's tackle this IDOR."      # lo de antes del </think>
    assert "</think>" not in "".join(d["texto"] for ev, d in evs if ev == "token")


def test_filtro_think_trozos_y_respuesta_completa():
    def correr(trozos):
        f = FiltroThink()
        return [p for t in trozos for p in f.trozo(t)] + f.fin()
    assert correr(["<thi", "nk>razono</think>\nHola"]) == [("thinking", "razono"), ("content", "Hola")]
    assert correr(["pien", "so</thi", "nk>Hola"]) == [("content", "pien"), ("content", "so"), ("reclasificar", ""),
                                                      ("content", "Hola")]
    assert correr(["a <b>", "c</", "p>"]) == [("content", "a <b>"), ("content", "c"), ("content", "</p>")]
    assert quitar_razonamiento('Okay...</think>\n{"a": 1}') == '{"a": 1}'
    assert quitar_razonamiento('{"a": 1}') == '{"a": 1}'


def test_tope_es_reutilizable_para_cualquier_modelo_thinking(client, fake):
    """El mecanismo vive en el Motor de Chat y no depende del modo: aquí con num_predict y fracción propios."""
    motor = MotorChat(client.app.state.db, client.app.state.ollama)
    fake.pensamiento = ["a "] * 50
    fake.instalados.add("qwen3:8b")

    # Sin modelo de respuesta (híbrido): el mismo con thinking apagado, /no_think y el mínimo de 768.
    trozos = asyncio.run(_lista(motor._stream_con_tope("qwen3:8b", [{"role": "user", "content": "hola"}],
                                                       {"num_predict": 20}, True, fraccion=0.5)))
    assert next(t["tope"] for t in trozos if "tope" in t) == {"tokens_thinking": 10, "limite": 10, "num_predict": 20,
                                                                "restante": 10, "modelo_respuesta": "qwen3:8b"}
    assert fake.chats[-1]["model"] == "qwen3:8b" and fake.chats[-1]["think"] is False
    assert fake.chats[-1]["options"]["num_predict"] == 768 and fake.chats[-1]["messages"][-1]["content"].endswith("/no_think")
    # Con modelo de respuesta: lo da él.
    asyncio.run(_lista(motor._stream_con_tope(RAZONADOR, [{"role": "user", "content": "hola"}],
                                              {"num_predict": 20}, True, fraccion=0.5, etiqueta_respuesta=INSTRUCT)))
    assert fake.chats[-1]["model"] == INSTRUCT and fake.chats[-1]["options"]["num_predict"] == 10
    # Sin thinking pedido, el tope no interviene.
    sin = asyncio.run(_lista(motor._stream_con_tope(RAZONADOR, [{"role": "user", "content": "x"}],
                                                    {"num_predict": 20}, False)))
    assert not any("tope" in t for t in sin)


async def _lista(gen):
    return [t async for t in gen]
