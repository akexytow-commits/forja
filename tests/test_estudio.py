"""Rama 8 — Estudio de Apariencia (MOD-100, 20-estudio-apariencia.md). TST-073: aplicar un tema con vista previa
en vivo, validar contraste y persistir en ui.* tras reiniciar."""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import urllib.request

import pytest

from backend import apariencia as ap
from backend.config import ROOT_DIR
from backend.db import DB
from backend.main import create_app

from .conftest import TOKEN

UI = ROOT_DIR / "ui"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82")


def test_contraste_wcag():
    assert ap.contraste("#000000", "#ffffff") == 21.0 and ap.contraste("#777777", "#777777") == 1.0
    assert 4.4 < ap.contraste("#767676", "#ffffff") < 4.6          # el gris AA de referencia


def test_todos_los_presets_y_acentos_se_leen():
    for p in ap.PRESETS:
        assert ap.paleta(p["ajustes"])["problemas"] == [], p["id"]
    for tema in ("oscuro", "claro"):
        for nombre in ap.ACENTOS:
            assert ap.paleta({"ui.tema": tema, "ui.acento": nombre})["problemas"] == [], (tema, nombre)
    assert {"oscuro", "claro", "alto-contraste"} <= {p["id"].replace("forja-", "") for p in ap.PRESETS}
    assert len(ap.PRESETS) >= 5                                    # + un par con personalidad


def test_el_css_coincide_con_las_bases_del_backend():
    css = (UI / "styles.css").read_text(encoding="utf-8") + (UI / "estudio.css").read_text(encoding="utf-8")
    r5 = (UI / "rama5.css").read_text(encoding="utf-8")
    for tema, sel in (("oscuro", ':root[data-theme="oscuro"]'), ("claro", ':root[data-theme="claro"]'),
                      ("contraste", ':root[data-theme="contraste"]')):
        bloque = css[css.index(sel):][:900]
        assert re.search(r"--bg:\s*" + ap.BASES[tema]["bg"], bloque, re.I), tema
        assert re.search(r"--text-strong:\s*" + ap.BASES[tema]["texto"], bloque, re.I), tema
    for nombre, v in ap.ACENTOS.items():
        if nombre == "naranja-forja":
            continue
        assert re.search(rf'data-acento="{nombre}"\]\s*{{\s*--accent:\s*{v["oscuro"]}', r5, re.I), nombre


def test_catalogo_y_previa_sin_guardar(client):
    cat = client.get("/apariencia").json()
    assert [p["id"] for p in cat["presets"]] == [p["id"] for p in ap.PRESETS]
    assert set(cat["fuentes"]) == set(ap.FUENTES) and "contraste" in cat["temas"]
    antes = client.get("/ajustes").json()["ajustes"]
    r = client.post("/apariencia/previa", json={"estado": {"ui.tema": "oscuro", "ui.acento": "#38bdf8",
                                                           "ui.base": {"bg": "#0a0f1d", "surface": "#111a2e", "texto": "#e6ecf8"}}}).json()
    assert r["variables"]["--bg"] == "#0a0f1d" and r["variables"]["--accent"] == "#38bdf8"
    assert r["familia"] == "oscuro" and r["problemas"] == [] and len(r["contrastes"]) == 4
    assert client.get("/ajustes").json()["ajustes"] == antes                 # la vista previa no guarda nada


# --- TST-073 ---------------------------------------------------------------------------------------------
def test_tst073_aplicar_preset_persiste_tras_reiniciar(make_client):
    c1 = make_client()
    fragua = next(p for p in ap.PRESETS if p["id"] == "fragua")["ajustes"]
    cuerpo = {k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in fragua.items()}
    cuerpo.update({"ui.preset": "fragua", "ui.tipografia": "redondeada", "ui.animacion": "0",
                   "ui.acento_por_modo": json.dumps({"seguridad": "#d9483b"})})
    assert c1.put("/ajustes", json=cuerpo).status_code == 200
    a = make_client().get("/ajustes").json()["ajustes"]                       # reinicio
    assert a["ui.preset"] == "fragua" and a["ui.acento"] == "#ff7a1a" and a["ui.tipografia"] == "redondeada"
    assert json.loads(a["ui.base"]) == fragua["ui.base"] and json.loads(a["ui.fondo"]) == {"tipo": "degradado"}
    assert json.loads(a["ui.acento_por_modo"]) == {"seguridad": "#d9483b"} and a["ui.animacion"] == "0"


@pytest.mark.parametrize("cuerpo,par", [
    ({"ui.tema": "claro", "ui.acento": "#e0e0e0"}, "acento/fondo"),
    ({"ui.base": json.dumps({"bg": "#777777", "surface": "#777777", "texto": "#888888"})}, "texto/fondo"),
    ({"ui.acento_por_modo": json.dumps({"tareas": "#0e0e0f"}), "ui.tema": "oscuro"}, "acento/fondo"),
    ({"ui.tema": "sistema", "ui.acento": "#f0f0f0"}, "acento/fondo"),          # ilegible en la variante clara
])
def test_tst073_contraste_ilegible_se_rechaza(client, cuerpo, par):
    antes = client.get("/ajustes").json()["ajustes"]
    r = client.put("/ajustes", json=cuerpo)
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "CONTRASTE_INSUFICIENTE"
    assert r.json()["error"]["problemas"][0]["par"] == par
    assert client.get("/ajustes").json()["ajustes"] == antes                  # nada a medias


def test_formatos_invalidos(client):
    for malo in ({"ui.acento": "rosa"}, {"ui.acento": "#12345"}, {"ui.base": '{"bg": "#000000"}'},
                 {"ui.fondo": '{"tipo": "video"}'}, {"ui.acento_por_modo": '{"academia": "#ffffff"}'},
                 {"ui.tipografia": "comic"}, {"ui.tema": "rosa"}, {"ui.preset": "nope"}, {"ui.animacion": "2"}):
        assert client.put("/ajustes", json=malo).status_code == 400, malo


def test_fondo_imagen_subir_servir_y_opacidad_acotada(client):
    r = client.post("/apariencia/fondo", content=PNG, headers={"Content-Type": "image/png"}).json()
    assert re.fullmatch(r"[0-9a-f]{16}\.png", r["archivo"])
    assert client.get(f"/apariencia/fondo/{r['archivo']}").content == PNG
    assert client.post("/apariencia/fondo", content=b"<script>no</script>").status_code == 400
    assert client.get("/apariencia/fondo/..%5C..%5Cforja.db").status_code == 404
    assert client.put("/ajustes", json={"ui.fondo": json.dumps({"tipo": "imagen", "archivo": r["archivo"],
                                                                 "opacidad": 0.9})}).status_code == 200
    f = json.loads(client.get("/ajustes").json()["ajustes"]["ui.fondo"])
    assert f == {"tipo": "imagen", "archivo": r["archivo"], "opacidad": ap.OPACIDAD_MAX}   # nunca resta legibilidad
    falso = {"tipo": "imagen", "archivo": "0123456789abcdef.png", "opacidad": 0.2}
    assert client.put("/ajustes", json={"ui.fondo": json.dumps(falso)}).status_code == 400


def test_migracion_012_no_cambia_tu_tema(tmp_path, monkeypatch):
    import backend.db as dbmod
    reales, hasta11 = dbmod.MIGRATIONS_DIR, tmp_path / "m11"
    hasta11.mkdir()
    for f in sorted(reales.glob("*.sql")):
        if int(f.name.split("_")[0]) <= 11:
            shutil.copy(f, hasta11 / f.name)
    monkeypatch.setattr(dbmod, "MIGRATIONS_DIR", hasta11)
    db = DB(tmp_path / "forja.db")
    db.set_setting("ui.acento", "azul")
    monkeypatch.setattr(dbmod, "MIGRATIONS_DIR", reales)
    db2 = DB(tmp_path / "forja.db")
    assert db2.schema_version() == 12 and db2.get_setting("ui.acento") == "azul"
    assert db2.get_setting("ui.fondo") == '{"tipo":"liso"}' and db2.get_setting("ui.animacion") == "1"


def test_ajustes_apariencia_es_acceso_directo_al_estudio():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'id="aj-abrir-estudio"' in html and 'id="btn-estudio"' in html and 'id="scr-040"' in html
    assert 'id="aj-tema"' not in html                    # tema/colores/fuente viven ahora en el Estudio
    assert "/ui/estudio.js" in html and "/ui/estudio.css" in html


# --- TST-073 en la interfaz real (Edge headless): vista previa en vivo, contraste y persistencia ------------
@pytest.mark.skipif(not __import__("tests.test_rama6", fromlist=["EDGE"]).EDGE.exists(), reason="Edge no instalado")
def test_tst073_ui_previa_en_vivo_contraste_y_persistencia(tmp_path, fake):
    from . import test_rama6 as t6
    ruta = tmp_path / "forja.db"
    with t6._Servidor(create_app(db_path=ruta, ollama_transport=fake.transport(), precargar=False, token=TOKEN)) as s1:
        async def pasos(ev, esperar):
            out = {}
            css = "getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()"
            out["bg_antes"] = await ev(css)
            await ev("document.querySelector('#btn-estudio').click()")
            await esperar("!document.querySelector('#scr-040').hidden && !!document.querySelector('[data-preset=medianoche]')")
            out["maqueta"] = await ev("[!!document.querySelector('#es-maqueta .mq-top'), document.querySelectorAll('#es-maqueta .mq-sel .seg').length]")
            await ev("document.querySelector('[data-preset=medianoche]').click()")
            await esperar(f"{css} === '#0a0f1d'")                       # en vivo, sin recargar
            await ev("(() => { const i = document.querySelector('#es-acento-hex'); i.value = '#14203a'; i.dispatchEvent(new Event('input')); })()")
            await esperar("document.querySelector('#es-aplicar').disabled")
            out["mal"] = await ev("document.querySelector('#es-contraste li.mal').textContent")
            await ev("document.querySelector('[data-preset=fragua]').click()")
            await esperar("!document.querySelector('#es-aplicar').disabled")
            await ev("document.querySelector('#es-aplicar').click()")
            await esperar("document.querySelector('#scr-040').hidden")
            out["recargas"] = await ev("performance.getEntriesByType('navigation').length")
            return out
        r = asyncio.run(t6._cdp(f"http://127.0.0.1:{s1.puerto}/", tmp_path / "edge1", pasos))
        assert r["maqueta"] == [True, 2] and "Acento" in r["mal"] and r["recargas"] == 1

    with t6._Servidor(create_app(db_path=ruta, ollama_transport=fake.transport(), precargar=False, token=TOKEN)) as s2:
        async def tras_reiniciar(ev, esperar):
            await esperar("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() === '#120c09'")
            return await ev("({fondo: document.documentElement.dataset.fondo, acc: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()})")
        r2 = asyncio.run(t6._cdp(f"http://127.0.0.1:{s2.puerto}/", tmp_path / "edge2", tras_reiniciar))
        assert r2 == {"fondo": "degradado", "acc": "#ff7a1a"}
        req = urllib.request.Request(f"http://127.0.0.1:{s2.puerto}/ajustes", headers={"X-Forja-Token": TOKEN})
        assert json.loads(urllib.request.urlopen(req).read())["ajustes"]["ui.preset"] == "fragua"
