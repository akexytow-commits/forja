"""Rama 6 — Personalización de interfaces (13-protocolo-personalizacion.md).

- Cada pregunta PREGUNTAR tiene su clave ui.* en settings, con las respuestas del Protocolo (migración 010).
- Las preferencias persisten tras reiniciar la app y se pueden re-pulir sin perder lo demás.
- Se aplican: el backend (plantilla de informe SG3) y la UI (Edge headless: data-* en <html> y DOM, en vivo).
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from backend.config import ROOT_DIR
from backend.db import DB
from backend.main import CLAVES_CERRADAS, create_app

from .conftest import TOKEN, eventos
from .test_seguridad import autorizado

UI = ROOT_DIR / "ui"

# Respuestas del Protocolo (2026-11-22). Lo no listado = DEFAULT del doc 13.
RESPUESTAS = {
    "ui.nombre_app": "FORJA", "ui.tema": "claro", "ui.acento": "violeta", "ui.densidad": "compacta",
    "ui.tipografia": "mono", "ui.pestanas": "icono+texto", "ui.esfuerzo_control": "segmentos",
    "ui.mostrar_modelo": "tier+tooltip", "ui.proyectos": "desplegable", "ui.codigo_tema": "alto-contraste",
    "ui.gate": "asistente", "ui.hallazgos": "tabla", "ui.informe_plantilla": "hackerone",
    "ui.tareas_vista": "tablero", "ui.tareas_carga": "1", "ui.aviso_escalado": "modal-nube+banner-justo",
    "ui.ajustes": "pestanas",
}
# Pregunta del doc 13 → clave (G1–G5, S1–S3, SC1–SC2, SG1–SG3, ST1–ST2, SE1, SA1).
PREGUNTAS = {"G1": "ui.nombre_app", "G2": "ui.tema", "G3": "ui.acento", "G4": "ui.densidad", "G5": "ui.tipografia",
             "S1": "ui.pestanas", "S2": "ui.esfuerzo_control", "S3": "ui.mostrar_modelo", "SC1": "ui.proyectos",
             "SC2": "ui.codigo_tema", "SG1": "ui.gate", "SG2": "ui.hallazgos", "SG3": "ui.informe_plantilla",
             "ST1": "ui.tareas_vista", "ST2": "ui.tareas_carga", "SE1": "ui.aviso_escalado", "SA1": "ui.ajustes"}


def test_cada_pregunta_del_protocolo_tiene_su_clave_con_mi_respuesta(client):
    doc = (ROOT_DIR / "docs/spec/13-protocolo-personalizacion.md").read_text(encoding="utf-8")
    assert set(re.findall(r"PREGUNTAR (\w+)", doc)) == set(PREGUNTAS)
    ajustes = client.get("/ajustes").json()["ajustes"]
    for preg, clave in PREGUNTAS.items():
        assert ajustes[clave] == RESPUESTAS[clave], preg
        if clave in CLAVES_CERRADAS:
            assert ajustes[clave] in CLAVES_CERRADAS[clave]
    assert ajustes["ui.protocolo_respondido"] == "2026-11-22"


def test_todas_las_opciones_se_aceptan_y_las_malas_no(client):
    for clave in PREGUNTAS.values():
        for v in CLAVES_CERRADAS.get(clave, ()):
            assert client.put("/ajustes", json={clave: v}).status_code == 200, (clave, v)
        if clave in CLAVES_CERRADAS:
            r = client.put("/ajustes", json={clave: "inventado"})
            assert r.status_code == 400 and r.json()["error"]["codigo"] == "AJUSTE_INVALIDO"
    r = client.put("/ajustes", json={"ui.informe_estructura": "x" * 4001})
    assert r.status_code == 400


def test_preferencias_persisten_tras_reiniciar_y_se_repulen_sin_perder_nada(make_client):
    c1 = make_client()
    nuevas = {"ui.pestanas": "icono", "ui.esfuerzo_control": "deslizador", "ui.hallazgos": "tarjetas",
              "ui.tareas_vista": "lista", "ui.tareas_carga": "0", "ui.tema": "sistema",
              "ui.informe_plantilla": "personalizada", "ui.informe_estructura": "## Qué\n## Cómo\n## Arreglo"}
    assert c1.put("/ajustes", json=nuevas).status_code == 200

    c2 = make_client()                       # = reiniciar la app (nuevo proceso sobre la misma BBDD)
    a2 = c2.get("/ajustes").json()["ajustes"]
    assert {k: a2[k] for k in nuevas} == nuevas
    assert a2["ui.acento"] == "violeta" and a2["ui.gate"] == "asistente"       # lo demás sigue

    # Re-pulir: cambiar solo una pantalla no toca las otras.
    assert c2.put("/ajustes", json={"ui.gate": "pantalla_completa"}).status_code == 200
    a3 = make_client().get("/ajustes").json()["ajustes"]
    assert a3["ui.gate"] == "pantalla_completa"
    assert {k: a3[k] for k in nuevas} == nuevas and a3["ui.codigo_tema"] == "alto-contraste"


def test_migracion_010_respeta_lo_ya_retocado(tmp_path, monkeypatch):
    import backend.db as dbmod
    reales = dbmod.MIGRATIONS_DIR
    hasta9 = tmp_path / "m9"
    hasta9.mkdir()
    for f in sorted(reales.glob("*.sql")):
        if int(f.name.split("_")[0]) <= 9:
            shutil.copy(f, hasta9 / f.name)
    monkeypatch.setattr(dbmod, "MIGRATIONS_DIR", hasta9)
    ruta = tmp_path / "forja.db"
    db = DB(ruta)
    db.set_setting("ui.acento", "azul")                 # el usuario ya lo había cambiado en Ajustes
    db.set_setting("ui.hallazgos", "tarjetas")
    monkeypatch.setattr(dbmod, "MIGRATIONS_DIR", reales)
    db2 = DB(ruta)
    assert db2.schema_version() == 10
    assert db2.get_setting("ui.acento") == "azul" and db2.get_setting("ui.hallazgos") == "tarjetas"
    assert db2.get_setting("ui.densidad") == "compacta"          # estaba en el DEFAULT → respuesta
    assert db2.get_setting("ui.informe_plantilla") == "hackerone"


# --- SG3: la plantilla de informe elegida llega al redactor --------------------------------------------
def _validado(client):
    e = autorizado(client)
    f = client.post(f"/engagements/{e['id']}/findings", json={"titulo": "IDOR", "clase": "IDOR"}).json()
    return client.post(f"/findings/{f['id']}", json={"estado": "validado_por_usuario",
                                                     "evidencia_usuario": "A ve el pedido de B"}).json()


@pytest.mark.parametrize("plantilla,estructura,esperado,no", [
    ("hackerone", "", "## Mitigación recomendada", "## Clasificación VRT"),
    ("bugcrowd", "", "## Clasificación VRT", "## Mitigación recomendada"),
    ("breve", "", "(breve)", "## Evidencia"),
    ("personalizada", "## Qué pasa\n## Arreglo", "## Qué pasa\n## Arreglo", "## Clasificación VRT"),
    ("personalizada", "", "## Mitigación recomendada", "## Clasificación VRT"),   # vacía → HackerOne
])
def test_sg3_el_informe_sigue_la_plantilla_elegida(client, fake, plantilla, estructura, esperado, no):
    client.put("/ajustes", json={"ui.informe_plantilla": plantilla, "ui.informe_estructura": estructura})
    f = _validado(client)
    evs = eventos(client.post(f"/findings/{f['id']}/informe", json={}).text)
    assert evs[-1][0] == "fin"
    pedido = fake.chats[-1]["messages"][1]["content"]
    assert esperado in pedido and no not in pedido


def test_api055_plantillas_de_informe_incluye_la_propia(client):
    client.put("/ajustes", json={"ui.informe_plantilla": "bugcrowd"})
    r = client.get("/seguridad/plantillas-informe").json()
    assert set(r["plantillas"]) == {"hackerone", "bugcrowd", "breve", "personalizada"}
    assert r["plantillas"]["personalizada"] == {"nombre": "propia", "estructura": ""}      # aún sin escribir
    assert r["activa"]["id"] == "bugcrowd" and "## Clasificación VRT" in r["activa"]["estructura"]
    client.put("/ajustes", json={"ui.informe_plantilla": "personalizada", "ui.informe_estructura": "## A\n## B"})
    r = client.get("/seguridad/plantillas-informe").json()
    assert r["plantillas"]["personalizada"]["estructura"] == "## A\n## B"
    assert r["activa"] == {"id": "personalizada", "nombre": "personalizada", "estructura": "## A\n## B"}


def test_api055_el_redactor_ofrece_las_plantillas():
    html = (UI / "index.html").read_text(encoding="utf-8")
    js = (UI / "seguridad.js").read_text(encoding="utf-8")
    assert 'id="sg-inf-plantilla"' in html
    assert "/seguridad/plantillas-informe" in js and '"ui.informe_plantilla": id' in js


# --- La UI tiene una forma para cada opción ------------------------------------------------------------
def _pantallas_js() -> list[tuple[str, str, str, list[str]]]:
    js = (UI / "interfaz.js").read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r'\{ k: "(ui\.[\w_]+)", attr: "(\w+)", def: "([^"]+)", ops: \[([^\]]+)\] \}', js):
        out.append((m[1], m[2], m[3], re.findall(r'"([^"]+)"', m[4])))
    return out


def test_ui_cubre_cada_opcion_con_su_texto_y_su_forma():
    pantallas = _pantallas_js()
    claves = {k for k, *_ in pantallas}
    assert claves == {c for c in PREGUNTAS.values() if c not in ("ui.nombre_app", "ui.tema", "ui.acento",
                                                                   "ui.densidad", "ui.tipografia")}
    textos = json.loads((UI / "strings.es.json").read_text(encoding="utf-8"))
    css = (UI / "rama6.css").read_text(encoding="utf-8")
    js = "".join((UI / f).read_text(encoding="utf-8") for f in ("app.js", "seguridad.js", "proyectos.js"))
    en_js = {"ui.esfuerzo_control", "ui.mostrar_modelo", "ui.aviso_escalado", "ui.informe_plantilla", "ui.gate"}
    for k, attr, defecto, ops in pantallas:
        assert set(ops) == set(CLAVES_CERRADAS[k]) and defecto in ops, k
        nombre = k[3:]
        assert f"if.{nombre}" in textos
        for o in ops:
            assert f"if.{nombre}.{o}" in textos and f"if.{nombre}.{o}.ayuda" in textos, (k, o)
            if o == defecto:
                continue
            kebab = re.sub(r"([A-Z])", lambda x: "-" + x[1].lower(), attr)
            # Cada opción no-DEFAULT cambia algo: una regla CSS o código que la lee.
            if k == "ui.informe_plantilla":            # SG3 se aplica en el backend (el redactor)
                from backend.modes.seguridad import PLANTILLAS_INFORME
                assert o in PLANTILLAS_INFORME or o == "personalizada"
                continue
            assert f'data-{kebab}="{o}"' in css or (k in en_js and (o in js or k in js)), (k, o)
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert "/ui/interfaz.js" in html and "/ui/rama6.css" in html and 'data-tab="interfaz"' in html


# --- Edge headless: se aplican tras reiniciar y se repintan al momento ----------------------------------
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def _puerto() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Servidor:
    def __init__(self, app):
        import uvicorn
        self.puerto = _puerto()
        self.srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.puerto, log_level="error"))
        self.hilo = threading.Thread(target=self.srv.run, daemon=True)

    def __enter__(self):
        self.hilo.start()
        for _ in range(100):
            if self.srv.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("uvicorn no arrancó")

    def __exit__(self, *a):
        self.srv.should_exit = True
        self.hilo.join(10)


async def _cdp(url_pagina: str, perfil: Path, pasos):
    import websockets
    puerto = _puerto()
    proc = subprocess.Popen([str(EDGE), "--headless=new", f"--remote-debugging-port={puerto}",
                             f"--user-data-dir={perfil}", "--window-size=1280,860", "--no-first-run",
                             "--disable-gpu", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                pags = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json/list").read())
                pag = next(p for p in pags if p["type"] == "page")
                break
            except Exception:
                await asyncio.sleep(0.1)
        async with websockets.connect(pag["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
            n = 0

            async def cmd(metodo, **params):
                nonlocal n
                n += 1
                await ws.send(json.dumps({"id": n, "method": metodo, "params": params}))
                while True:
                    r = json.loads(await ws.recv())
                    if r.get("id") == n:
                        return r.get("result", {})

            async def ev(expr):
                r = await cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
                if "exceptionDetails" in r:
                    raise AssertionError(f"JS: {r['exceptionDetails']}")
                return r["result"].get("value")

            async def esperar(expr, s=15):
                for _ in range(int(s * 10)):
                    if await ev(expr):
                        return
                    await asyncio.sleep(0.1)
                raise AssertionError(f"timeout: {expr}")

            await cmd("Page.navigate", url=url_pagina)
            await esperar("!!(window.ForjaApp && document.documentElement.dataset.pestanas && document.querySelector('#seg-esfuerzo').children.length)")
            return await pasos(ev, esperar)
    finally:
        proc.kill()


@pytest.mark.skipif(not EDGE.exists(), reason="Edge no instalado")
def test_ui_aplica_las_preferencias_tras_reiniciar_y_en_vivo(tmp_path, fake):
    ruta = tmp_path / "forja.db"
    prefs = {"ui.pestanas": "icono", "ui.esfuerzo_control": "deslizador", "ui.mostrar_modelo": "tier+modelo",
             "ui.proyectos": "fijo", "ui.tareas_vista": "lista", "ui.tareas_carga": "0", "ui.ajustes": "pagina",
             "estado.modo": "scripts"}
    cab = {"X-Forja-Token": TOKEN, "Content-Type": "application/json"}
    with _Servidor(create_app(db_path=ruta, ollama_transport=fake.transport(), precargar=False, token=TOKEN)) as s1:
        req = urllib.request.Request(f"http://127.0.0.1:{s1.puerto}/ajustes", data=json.dumps(prefs).encode(),
                                     headers=cab, method="PUT")
        assert urllib.request.urlopen(req).status == 200

    # Reinicio: otro proceso de servidor (app nueva) sobre la misma BBDD.
    with _Servidor(create_app(db_path=ruta, ollama_transport=fake.transport(), precargar=False, token=TOKEN)) as s2:
        async def pasos(ev, esperar):
            out = {"ds": await ev("({...document.documentElement.dataset})")}
            out["span_pestana"] = await ev("getComputedStyle(document.querySelector('.modo > span')).display")
            out["rango"] = await ev("!!document.querySelector('#seg-esfuerzo input[type=range]')")
            await esperar("!!document.querySelector('#seg-tier .tier-modelo')")
            out["tier_modelo"] = await ev("document.querySelector('#seg-tier .tier-modelo').textContent")
            out["proy_fijo"] = await ev("!!document.querySelector('.vista[data-vista=scripts] > #proy-fijo #pop-proyectos:not([hidden])')")
            # En vivo, sin recargar: abrir Ajustes › Interfaces, elegir "Solo texto" y guardar.
            await ev("window.ForjaApp.abrirAjustes('interfaz')")
            await esperar("!!document.querySelector('#aj-if-pestanas [data-v=texto]')")
            out["pagina_todo"] = await ev("[...document.querySelectorAll('#scr-007 .aj-panel')].every((p) => !p.hidden)")
            await ev("document.querySelector('#aj-if-pestanas [data-v=texto]').click()")
            out["previa"] = await ev("document.documentElement.dataset.pestanas")
            out["svg_pestana"] = await ev("getComputedStyle(document.querySelector('.modo > svg')).display")
            await ev("document.querySelector('#aj-if-proyectos [data-v=desplegable]').click()")
            out["proy_despl"] = await ev("!document.querySelector('#proy-fijo') && !!document.querySelector('.pop-ancla > #pop-proyectos[hidden]')")
            await ev("document.querySelector('#aj-guardar').click()")
            await esperar("document.querySelector('#aj-msg').className.includes('ok')")
            out["recargas"] = await ev("performance.getEntriesByType('navigation').length")
            return out

        r = asyncio.run(_cdp(f"http://127.0.0.1:{s2.puerto}/", tmp_path / "edge", pasos))
        ds = r["ds"]
        assert ds["pestanas"] == "icono" and ds["esfuerzo"] == "deslizador" and ds["modelo"] == "tier+modelo"
        assert ds["tareasVista"] == "lista" and ds["tareasCarga"] == "0" and ds["ajustes"] == "pagina"
        assert ds["theme"] == "claro" and ds["acento"] == "violeta" and ds["densidad"] == "compacta"
        assert ds["fuente"] == "mono" and ds["codigo"] == "alto-contraste" and ds["gate"] == "asistente"
        assert r["span_pestana"] == "none" and r["rango"] and r["tier_modelo"] and r["proy_fijo"]
        assert r["pagina_todo"]
        assert r["previa"] == "texto" and r["svg_pestana"] == "none" and r["proy_despl"]
        assert r["recargas"] == 1                          # nada de recargar la página
        req = urllib.request.Request(f"http://127.0.0.1:{s2.puerto}/ajustes", headers=cab)
        guardado = json.loads(urllib.request.urlopen(req).read())["ajustes"]
        assert guardado["ui.pestanas"] == "texto" and guardado["ui.proyectos"] == "desplegable"
        assert guardado["ui.esfuerzo_control"] == "deslizador"             # lo demás, intacto
