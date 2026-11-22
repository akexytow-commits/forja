"""Rama 3 — Modo Tareas: TST-040..048 (11-modo-tareas-organizador.md, 17-patrones-planificador.md)."""
import json
from datetime import date, timedelta

import pytest

from backend.modes import lenguaje
from backend.modes import tareas as tareas_mod
from backend.modes.tareas import parsear_json_tolerante

from .conftest import INSTRUCT

HOY = date(2026, 11, 21)  # sábado
D = lambda k: (HOY + timedelta(days=k)).isoformat()  # noqa: E731


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(tareas_mod, "hoy", lambda: HOY)


def lista_general(client):
    return client.get("/listas").json()["listas"][0]["id"]


def anadir(client, texto, lista=None, **kw):
    r = client.post("/tareas", json={"lista_id": lista or lista_general(client), "texto": texto, **kw})
    assert r.status_code == 201, r.text
    return r.json()["creadas"]


def vista(client, lista=None):
    return client.get(f"/tareas?lista={lista or lista_general(client)}").json()


# --- TST-040 añadir ---------------------------------------------------------------------------
def test_tst040_anadir_desde_texto_libre(client):
    assert client.get("/listas").json()["listas"][0]["nombre"] == "General"
    creadas = anadir(client, "- comprar pan\n* revisar PR\n\n1) llamar a Ana")
    assert [t["texto"] for t in creadas] == ["comprar pan", "revisar PR", "llamar a Ana"]
    assert all(t["origen"] == "usuario" and t["dia_asignado"] is None for t in creadas)
    nueva = client.post("/listas", json={"nombre": "Bug bounty"}).json()
    anadir(client, "leer scope; montar proxy", lista=nueva["id"])
    assert [t["texto"] for t in vista(client, nueva["id"])["tareas"]] == ["leer scope", "montar proxy"]
    assert client.post("/tareas", json={"lista_id": 999, "texto": "x"}).json()["error"]["codigo"] == "LISTA_INVALIDA"


# --- TST-045 lenguaje natural (P1) --------------------------------------------------------------
@pytest.mark.parametrize("texto, esperado", [
    ("pagar factura mañana 17:00 !!", {"texto": "pagar factura", "dia_asignado": D(1), "hora": "17:00", "prioridad": 2}),
    ("comprar pan hoy !!!", {"texto": "comprar pan", "dia_asignado": D(0), "prioridad": 1}),
    ("revisar PR 30min", {"texto": "revisar PR", "estimacion_min": 30, "dia_asignado": None}),
    ("llamar a Ana el lunes a las 5 de la tarde", {"texto": "llamar a Ana", "dia_asignado": D(2), "hora": "17:00"}),
    ("preparar charla en 3 días 2 horas", {"texto": "preparar charla", "dia_asignado": D(3), "estimacion_min": 120}),
    ("cita médico 25 de diciembre 9:30", {"texto": "cita médico", "dia_asignado": "2026-12-25", "hora": "09:30"}),
    ("informe 1h30 p1", {"texto": "informe", "estimacion_min": 90, "prioridad": 1}),
    ("reunión 17h viernes", {"texto": "reunión", "hora": "17:00", "dia_asignado": D(6), "estimacion_min": None}),
    ("¡urgente! llamar al banco", {"texto": "llamar al banco", "prioridad": 1}),
    ("configurar router 192.168.1.1", {"texto": "configurar router 192.168.1.1", "dia_asignado": None}),
])
def test_tst045_lenguaje_natural(texto, esperado):
    r = lenguaje.interpretar(texto, HOY)
    for k, v in esperado.items():
        assert r[k] == v, (k, r)


def test_tst045_al_anadir_queda_colocada_y_fijada(client):
    t = anadir(client, "pagar factura mañana 17:00 !!")[0]
    assert (t["dia_asignado"], t["hora"], t["prioridad"], t["fijada"]) == (D(1), "17:00", 2, 1)
    assert set(t["detectado"]) >= {"fecha", "hora", "prioridad"}
    prev = client.post("/tareas/interpretar", json={"texto": "gym 1h hoy"}).json()["lineas"][0]
    assert prev["estimacion_min"] == 60 and prev["dia_asignado"] == D(0)


def test_tst045_capa2_modelo_para_lo_ambiguo(client, fake):
    fake.json_respuestas.append(json.dumps({"texto_limpio": "estudiar", "dia_asignado": "2026-11-30", "prioridad": 3}))
    t = anadir(client, "estudiar a final de mes")[0]
    assert t["dia_asignado"] == "2026-11-30" and t["texto"] == "estudiar"
    assert fake.chats[-1]["model"] == INSTRUCT and fake.chats[-1]["think"] is False


# --- TST-041 organizar ---------------------------------------------------------------------------
def test_tst041_organizar_con_ia_produce_plan_por_dias(client, fake):
    a, b, c = (t["id"] for t in anadir(client, "escribir driver SPI\nprobar en placa\ndocumentar"))
    fake.json_respuestas.append(json.dumps({"plan": [
        {"id": a, "dia_asignado": D(0), "orden": 1, "prioridad": 1, "estimacion_min": 120},
        {"id": b, "dia_asignado": D(1), "orden": 1, "prioridad": 2, "estimacion_min": 60},
        {"id": c, "dia_asignado": D(2), "orden": 1, "prioridad": 4},
    ], "resumen": "Hoy el driver; mañana pruebas."}))
    r = client.post("/tareas/organizar", json={"lista_id": lista_general(client), "esfuerzo": "medio"}).json()
    assert r["origen"] == "ia" and r["resumen"] == "Hoy el driver; mañana pruebas."
    por_id = {t["id"]: t for t in r["tareas"]}
    assert [por_id[x]["dia_asignado"] for x in (a, b, c)] == [D(0), D(1), D(2)]
    assert por_id[a]["estimacion_min"] == 120 and por_id[c]["estimacion_min"] == 30  # sin estimación → 30
    assert fake.chats[-1]["model"] == INSTRUCT
    assert fake.chats[-1]["format"]["required"] == ["plan", "resumen"]  # salida estructurada con esquema
    assert fake.chats[-1]["think"] is False
    # La BBDD lo conserva (FR-043) y la lista guarda el resumen.
    assert vista(client)["lista"]["resumen"] == "Hoy el driver; mañana pruebas."


def test_organizar_extra_razona_con_thinking(client, fake):
    anadir(client, "a\nb")
    fake.json_respuestas += ['{"plan": []}', '{"plan": []}']
    client.post("/tareas/organizar", json={"lista_id": lista_general(client), "esfuerzo": "extra"})
    assert fake.chats[-2]["think"] is True and fake.chats[-1]["think"] is False  # plan + reformateo


def test_eco_de_la_entrada_no_cuenta_como_plan(client, fake):
    """qwen3:4b real devolvió a veces el JSON de entrada: eso no es un plan de la IA."""
    (a,) = (t["id"] for t in anadir(client, "x"))
    eco = json.dumps({"hoy": D(0), "tareas": [{"id": a, "texto": "x", "prioridad": 3}]})
    fake.json_respuestas += [eco, eco]
    r = client.post("/tareas/organizar", json={"lista_id": lista_general(client)}).json()
    assert r["origen"] == "reglas" and r["avisos"]


def test_organizar_bajo_es_por_prioridad_sin_ia(client, fake):
    anadir(client, "baja p5\nalta !!!\nmedia")
    r = client.post("/tareas/organizar", json={"lista_id": lista_general(client), "esfuerzo": "bajo"}).json()
    assert r["origen"] == "reglas" and fake.chats == []
    hoy = sorted((t for t in r["tareas"] if t["dia_asignado"] == D(0)), key=lambda t: t["orden"])
    assert [t["texto"] for t in hoy] == ["alta", "media", "baja"]


# --- TST-043 JSON imperfecto ---------------------------------------------------------------------
@pytest.mark.parametrize("bruto", [
    '```json\n{"plan": [{"id": 1, "dia_asignado": "2026-11-21",}], }\n```',
    "Claro, aquí tienes: {'plan': [{'id': 1, 'dia_asignado': '2026-11-21'}]} ¡Suerte!",
    '<think>pienso…</think>{plan: [{id: 1, dia_asignado: "2026-11-21"}]}',
])
def test_tst043_parser_tolerante(bruto):
    assert parsear_json_tolerante(bruto)["plan"][0]["id"] == 1


def test_tst043_json_basura_no_rompe(client, fake):
    anadir(client, "una\ndos")
    fake.json_respuestas += ["esto no es json", "sigue sin serlo"]  # 1.º intento + reformateo
    r = client.post("/tareas/organizar", json={"lista_id": lista_general(client), "esfuerzo": "medio"})
    assert r.status_code == 200
    d = r.json()
    assert d["origen"] == "reglas" and d["avisos"]
    assert all(t["dia_asignado"] == D(0) for t in d["tareas"])


def test_tst043_ids_inventados_y_dias_raros_se_sanean(client, fake):
    (a,) = (t["id"] for t in anadir(client, "real"))
    fake.json_respuestas.append(json.dumps({"plan": [
        {"id": 9999, "dia_asignado": D(0)}, {"id": a, "dia_asignado": "el año que viene", "prioridad": 99}]}))
    r = client.post("/tareas/organizar", json={"lista_id": lista_general(client)}).json()
    t = r["tareas"][0]
    assert t["dia_asignado"] == D(0) and t["prioridad"] == 5 and len(r["tareas"]) == 1


def test_organizar_sin_ollama_reparte_por_reglas(client, fake):
    anadir(client, "x")
    fake.up = False
    r = client.post("/tareas/organizar", json={"lista_id": lista_general(client)}).json()
    assert r["origen"] == "reglas" and r["tareas"][0]["dia_asignado"] == D(0)


# --- TST-042 editar/mover/marcar persisten ---------------------------------------------------------
def test_tst042_editar_mover_marcar(client):
    a, b, c = (t["id"] for t in anadir(client, "a\nb\nc"))
    t = client.patch(f"/tareas/{a}", json={"dia_asignado": D(1)}).json()
    assert t["dia_asignado"] == D(1) and t["fijada"] == 1  # mover a mano = fijar (P2)
    client.patch(f"/tareas/{b}", json={"dia_asignado": D(1)})
    client.patch(f"/tareas/{c}", json={"dia_asignado": D(1), "orden": 0})  # c al principio del día
    dia = sorted((t for t in vista(client)["tareas"] if t["dia_asignado"] == D(1)), key=lambda t: t["orden"])
    assert [t["id"] for t in dia] == [c, a, b]
    t = client.patch(f"/tareas/{b}", json={"texto": "b editada", "prioridad": 1, "estimacion_min": 25,
                                            "hora": "09:15", "estado": "hecha"}).json()
    assert (t["texto"], t["prioridad"], t["estimacion_min"], t["hora"], t["estado"]) == \
        ("b editada", 1, 25, "09:15", "hecha")
    assert client.patch(f"/tareas/{b}", json={"hora": "25:00"}).status_code == 400
    assert client.patch(f"/tareas/{b}", json={"texto": " "}).status_code == 400
    t = client.patch(f"/tareas/{a}", json={"dia_asignado": None}).json()
    assert t["dia_asignado"] is None and t["fijada"] == 0
    assert client.delete(f"/tareas/{c}").status_code == 204
    assert c not in {t["id"] for t in vista(client)["tareas"]}


# --- TST-046 reorganizar respeta lo fijado (P2) -------------------------------------------------------
def test_tst046_reorganizar_respeta_fijadas(client, fake):
    fija, movida, libre = (t["id"] for t in anadir(client, "fija\nmovida\nlibre"))
    client.patch(f"/tareas/{fija}", json={"dia_asignado": D(3), "fijada": 1})
    client.patch(f"/tareas/{movida}", json={"dia_asignado": D(2)})  # movida a mano
    fake.json_respuestas.append(json.dumps({"plan": [
        {"id": fija, "dia_asignado": D(0)}, {"id": movida, "dia_asignado": D(0)}, {"id": libre, "dia_asignado": D(1)}]}))
    r = client.post("/tareas/organizar", json={"lista_id": lista_general(client)}).json()
    por_id = {t["id"]: t for t in r["tareas"]}
    assert por_id[fija]["dia_asignado"] == D(3) and por_id[movida]["dia_asignado"] == D(2)
    assert por_id[libre]["dia_asignado"] == D(1) and r["respetadas"] == 2 and r["movidas"] == 1
    datos = fake.chats[-1]["messages"][1]["content"].split("Datos:\n", 1)[1]
    assert "/no_think" not in datos              # el instruct no razona: no lleva marca (doc 04 rev. 10)
    enviado = json.loads(datos)
    assert [t["id"] for t in enviado["tareas"]] == [libre]  # a la IA solo le llega lo libre
    assert {d["fecha"]: d["minutos_ya_ocupados"] for d in enviado["dias"]}[D(2)] == 30
    # Desfijar devuelve la tarea al reparto.
    assert client.patch(f"/tareas/{fija}", json={"fijada": 0}).json()["fijada"] == 0


# --- TST-047 carga del día (P3) -------------------------------------------------------------------------
def test_tst047_reparto_no_supera_la_capacidad(client):
    assert client.put("/ajustes", json={"plan.capacidad_dia_min": "120"}).status_code == 200
    anadir(client, "a 60min\nb 60min\nc 60min\nd 90min\ne 200min")
    r = client.post("/tareas/organizar", json={"lista_id": lista_general(client), "esfuerzo": "bajo"}).json()
    assert r["capacidad_dia_min"] == 120
    carga: dict[str, int] = {}
    for t in r["tareas"]:
        carga[t["dia_asignado"]] = carga.get(t["dia_asignado"], 0) + t["estimacion_min"]
    # Ningún día pasa de 120 salvo una tarea que sola ya no cabe en ninguno.
    assert carga == {D(0): 120, D(1): 60, D(2): 90, D(3): 200}


# --- TST-048 subtareas (P4) ---------------------------------------------------------------------------
def test_tst048_subtareas_por_sangria_y_por_api(client):
    creadas = anadir(client, "firmware\n  radio sub-ghz 2h\n  interfaz 1h\n    menú principal\notra cosa")
    fw, radio, ui, menu, otra = (t["id"] for t in creadas)
    assert [t["parent_id"] for t in creadas] == [None, fw, fw, ui, None]
    # Anidar / desanidar (BTN-059) y validaciones
    assert client.patch(f"/tareas/{otra}", json={"parent_id": radio}).json()["parent_id"] == radio
    assert client.patch(f"/tareas/{fw}", json={"parent_id": menu}).json()["error"]["codigo"] == "PADRE_INVALIDO"
    assert client.patch(f"/tareas/{otra}", json={"parent_id": menu}).json()["error"]["codigo"] == "DEMASIADO_PROFUNDO"
    assert client.patch(f"/tareas/{otra}", json={"parent_id": None}).json()["parent_id"] is None
    # Organizar planifica las hojas; el padre toma el primer día de sus hijas.
    r = client.post("/tareas/organizar", json={"lista_id": lista_general(client), "esfuerzo": "bajo"}).json()
    por_id = {t["id"]: t for t in r["tareas"]}
    assert por_id[fw]["dia_asignado"] == min(por_id[radio]["dia_asignado"], por_id[menu]["dia_asignado"])
    # Hechas todas las hijas → el padre queda hecho; borrar el padre borra sus hijas.
    for x in (radio, menu):
        client.patch(f"/tareas/{x}", json={"estado": "hecha"})
    assert {t["id"]: t["estado"] for t in vista(client)["tareas"]}[fw] == "hecha"
    client.delete(f"/tareas/{fw}")
    assert {t["id"] for t in vista(client)["tareas"]} == {otra}


def test_tst048_subtarea_directa(client):
    padre = anadir(client, "proyecto")[0]["id"]
    hija = anadir(client, "paso 1", parent_id=padre)[0]
    assert hija["parent_id"] == padre
