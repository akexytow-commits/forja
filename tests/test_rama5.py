"""Rama 5 — proyectos, plantillas, export, ajustes completos, telemetría de generación y no funcionales.

TST-021/022 (proyectos/plantillas), TST-061/062/063 (ajustes/export/migración), TST-077/078/079 (telemetría,
doc 22) y TST-100/101/102 (RAM, latencia + streaming, sin red).
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
import shutil
import socket
import sqlite3
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import telemetria as tel_mod
from backend.config import ROOT_DIR, UI_DIR
from backend.db import DB
from backend.main import create_app
from backend.telemetria import Telemetria, con_ticks, objetivo_tokens

from .conftest import TOKEN, eventos


def chat(client, texto="hazme un script", **kw):
    cuerpo = {"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo", "texto": texto, "forzar": True, **kw}
    r = client.post("/chat", json=cuerpo)
    assert r.status_code == 200
    return eventos(r.text)


def proyecto(client, tmp_path, nombre="Mi script", sub="proy"):
    r = client.post("/proyectos", json={"nombre": nombre, "carpeta": str(tmp_path / sub)})
    assert r.status_code == 201, r.text
    return r.json()


# ======================================================================= TST-021 proyectos + guardar archivo
def test_tst021_crear_proyecto_crea_la_carpeta(client, tmp_path):
    p = proyecto(client, tmp_path)
    assert Path(p["carpeta"]).is_dir() and p["existe"] and p["n_hilos"] == 0
    assert [x["id"] for x in client.get("/proyectos").json()["proyectos"]] == [p["id"]]
    # Misma carpeta dos veces → no.
    r = client.post("/proyectos", json={"nombre": "otro", "carpeta": str(tmp_path / "proy")})
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "CARPETA_EN_USO"
    # Sin carpeta → se sugiere una bajo proyectos.dir.
    client.put("/ajustes", json={"proyectos.dir": str(tmp_path / "base")})
    sug = client.get("/proyectos/sugerencia", params={"nombre": "Lector NFC"}).json()["carpeta"]
    assert sug == str(tmp_path / "base" / "Lector_NFC")
    p2 = client.post("/proyectos", json={"nombre": "Lector NFC"}).json()
    assert p2["carpeta"] == str((tmp_path / "base" / "Lector_NFC").resolve())


@pytest.mark.parametrize("carpeta,codigo", [
    ("relativa\\carpeta", "CARPETA_INVALIDA"),
    ("C:\\", "CARPETA_INVALIDA"),
    (str(ROOT_DIR), "CARPETA_PROHIBIDA"),
    (str(ROOT_DIR / "backend"), "CARPETA_PROHIBIDA"),
    (str(ROOT_DIR.parent), "CARPETA_PROHIBIDA"),      # contiene la propia FORJA
])
def test_tst021_carpetas_no_validas(client, carpeta, codigo):
    r = client.post("/proyectos", json={"nombre": "x", "carpeta": carpeta})
    assert r.status_code == 400 and r.json()["error"]["codigo"] == codigo


def test_tst021_guardar_pide_confirmacion_y_escribe_solo_en_el_proyecto(client, tmp_path):
    p = proyecto(client, tmp_path)
    url = f"/proyectos/{p['id']}/guardar-archivo"
    base = Path(p["carpeta"])

    # ST-040 propuesta: sin confirmar no se escribe nada y se devuelve lo que se haría.
    r = client.post(url, json={"nombre": "src/hola.py", "contenido": "print('hola')\n"})
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "CONFIRMACION_REQUERIDA"
    assert r.json()["error"]["propuesta"]["relativa"] == "src/hola.py" and not (base / "src").exists()

    # confirmada → ejecutada (y auditada).
    r = client.post(url, json={"nombre": "src/hola.py", "contenido": "print('hola')\n", "confirmado": True})
    assert r.status_code == 200 and r.json()["guardado"] and not r.json()["sobrescrito"]
    assert (base / "src" / "hola.py").read_text(encoding="utf-8") == "print('hola')\n"
    aud = client.get("/auditoria").json()["auditoria"][0]
    assert aud["tipo"] == "guardar_archivo" and aud["detalle"]["ruta"] == "src/hola.py"

    # Sobrescribir exige una segunda confirmación explícita.
    r = client.post(url, json={"nombre": "src\\hola.py", "contenido": "v2", "confirmado": True})
    assert r.status_code == 409 and r.json()["error"]["codigo"] == "SOBRESCRIBIR"
    assert (base / "src" / "hola.py").read_text(encoding="utf-8") == "print('hola')\n"
    r = client.post(url, json={"nombre": "src/hola.py", "contenido": "v2", "confirmado": True, "sobrescribir": True})
    assert r.json()["sobrescrito"] and (base / "src" / "hola.py").read_text(encoding="utf-8") == "v2"

    # Nada fuera de la carpeta del proyecto, ni con trucos de ruta ni con nombres raros de Windows.
    antes = set(tmp_path.rglob("*"))
    for malo in ["../fuera.txt", "src/../../fuera.txt", "..\\fuera.txt", "C:/Windows/fuera.txt", "/fuera.txt",
                 "C:fuera.txt", "a:b.txt", "CON.txt", "nul", "src//x.py", "./x.py", "x.py."]:
        r = client.post(url, json={"nombre": malo, "contenido": "x", "confirmado": True, "sobrescribir": True})
        assert r.status_code == 400, malo
    assert set(tmp_path.rglob("*")) == antes


def test_tst021_enlace_que_sale_del_proyecto_se_rechaza(client, tmp_path):
    p = proyecto(client, tmp_path)
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    enlace = Path(p["carpeta"]) / "enlace"
    try:
        os.symlink(fuera, enlace, target_is_directory=True)
    except (OSError, NotImplementedError):
        # Sin privilegio de symlink en Windows: una unión de directorio (mklink /J) sirve igual.
        if os.name != "nt" or subprocess.run(["cmd", "/c", "mklink", "/J", str(enlace), str(fuera)],
                                             capture_output=True).returncode != 0:
            pytest.skip("no se pudo crear un enlace")
    r = client.post(f"/proyectos/{p['id']}/guardar-archivo",
                    json={"nombre": "enlace/x.txt", "contenido": "x", "confirmado": True})
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "FUERA_DEL_PROYECTO"
    assert not (fuera / "x.txt").exists()


def test_tst021_abrir_carpeta_y_asociar_hilo(tmp_path, fake, nube):
    abiertas: list[str] = []
    app = create_app(db_path=tmp_path / "f.db", ollama_transport=fake.transport(), precargar=False, token=TOKEN,
                     nube=nube, abrir_carpeta=abiertas.append)
    with TestClient(app) as c:
        c.headers.update({"X-Forja-Token": TOKEN})
        p = proyecto(c, tmp_path, nombre="Lector NFC")
        assert c.post(f"/proyectos/{p['id']}/abrir").json()["carpeta"] == p["carpeta"]   # BTN-035
        assert abiertas == [p["carpeta"]]

        sid = chat(c, "hola")[0][1]["sesion_id"]
        # BTN-036: asociar el hilo actual al proyecto.
        assert c.patch(f"/conversaciones/{sid}", json={"project_id": 999}).status_code == 404
        assert c.patch(f"/conversaciones/{sid}", json={"project_id": p["id"]}).json()["project_id"] == p["id"]
        assert [h["id"] for h in c.get("/conversaciones", params={"modo": "scripts", "proyecto": p["id"]}).json()["conversaciones"]] == [sid]
        assert c.get("/proyectos").json()["proyectos"][0]["n_hilos"] == 1

        # El modelo sabe del proyecto (nombre y archivos) en los hilos asociados.
        (Path(p["carpeta"]) / "main.c").write_text("int main(){}", encoding="utf-8")
        chat(c, "sigue", sesion_id=sid)
        system = fake.chats[-1]["messages"][0]["content"]
        assert "Lector NFC" in system and "main.c" in system
        assert c.get(f"/proyectos/{p['id']}").json()["archivos"] == [{"ruta": "main.c", "bytes": 12}]

        # Borrar el proyecto no borra la carpeta y desasocia el hilo.
        assert c.delete(f"/proyectos/{p['id']}").status_code == 204
        assert Path(p["carpeta"], "main.c").exists()
        assert c.get("/conversaciones").json()["conversaciones"][0]["project_id"] is None


def test_tst021_selector_nativo_solo_con_ventana(client, tmp_path):
    r = client.post("/sistema/elegir-carpeta", json={})
    assert r.status_code == 501 and r.json()["error"]["codigo"] == "SIN_SELECTOR"
    client.app.state.elegir_carpeta = lambda inicial: str(tmp_path)
    assert client.post("/sistema/elegir-carpeta", json={}).json()["carpeta"] == str(tmp_path)


# ======================================================================= TST-022 plantillas
def _bloques(md: str) -> list[tuple[str, str]]:
    return re.findall(r"```([\w+#.-]*)\n([\s\S]*?)```", md)


def test_tst022_plantillas_de_serie_con_andamiaje_correcto(client):
    pl = {p["id"]: p for p in client.get("/plantillas").json()["plantillas"]}
    assert list(pl) == ["python", "bash", "powershell", "firmware"]          # orden del menú (09-...md)
    assert [pl[k]["nombre"] for k in pl] == ["Script Python", "Script Bash", "Script PowerShell", "Firmware base"]
    for p in pl.values():
        assert "<describe aquí" in p["contenido"] and p["origen"] == "serie"

    (lang, py), = _bloques(pl["python"]["contenido"])
    assert lang == "python"
    compile(py, "plantilla.py", "exec")                                       # Python válido
    assert "argparse" in py and 'if __name__ == "__main__":' in py

    (lang, sh), = _bloques(pl["bash"]["contenido"])
    assert lang == "bash" and sh.startswith("#!/usr/bin/env bash") and "set -Eeuo pipefail" in sh
    if shutil.which("bash"):
        r = subprocess.run(["bash", "-n"], input=sh.encode(), capture_output=True)
        assert r.returncode == 0, r.stderr

    (lang, ps), = _bloques(pl["powershell"]["contenido"])
    assert lang == "powershell" and "[CmdletBinding(SupportsShouldProcess = $true)]" in ps

    (l1, fam), (l2, c) = _bloques(pl["firmware"]["contenido"])
    assert 'entry_point="mi_app_main"' in fam and "int32_t mi_app_main(void* p)" in c
    assert c.count("{") == c.count("}") and "furi_record_close(RECORD_GUI)" in c


def test_tst022_plantillas_propias_mandan(client, tmp_path):
    carpeta = Path(client.get("/plantillas").json()["dir_usuario"])
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "python.md").write_text("nombre: Mi Python\norden: 5\n---\n```python\nprint(1)\n```\n", encoding="utf-8")
    (carpeta / "rust.md").write_text("Sin cabecera, solo texto\n", encoding="utf-8")
    (carpeta / "mal nombre!.md").write_text("x", encoding="utf-8")
    pl = client.get("/plantillas").json()["plantillas"]
    assert pl[0]["id"] == "python" and pl[0]["nombre"] == "Mi Python" and pl[0]["origen"] == "usuario"
    assert {p["id"] for p in pl} == {"python", "bash", "powershell", "firmware", "rust"}
    assert client.get("/plantillas/rust").json()["contenido"] == "Sin cabecera, solo texto\n"
    assert client.get("/plantillas/nada").status_code == 404


# ======================================================================= TST-061 ajustes completos (SCR-007)
def test_tst061_ajustes_completos_valida_y_persiste(client, tmp_path, keyring_memoria):
    a = client.get("/ajustes").json()["ajustes"]
    for k in ("ui.tema", "ui.acento", "ui.densidad", "ui.tipografia", "ui.proyectos", "ui.ajustes",
              "ui.razonamiento", "ui.telemetria", "lab.distro", "lab.backend", "lab.working_dir", "lab.attackbox_url",
              "modelos.precargar", "proyectos.dir", "plantillas.dir", "export.dir"):
        assert k in a, k
    assert a["ui.proyectos"] == "desplegable" and a["ui.ajustes"] == "pestanas"      # SC1 / SA1 por defecto

    ok = {"ui.tema": "claro", "ui.acento": "azul", "ui.densidad": "compacta", "ui.tipografia": "mono",
          "ui.razonamiento": "mostrar", "ui.telemetria": "0", "modelos.precargar": "0",
          "proyectos.dir": str(tmp_path / "p"), "export.dir": str(tmp_path / "e"), "plantillas.dir": "",
          "lab.backend": "attackbox", "lab.distro": "Ubuntu", "lab.working_dir": str(tmp_path / "lab"),
          "umbral.complejidad_nube": "80"}
    assert client.put("/ajustes", json=ok).status_code == 200
    a = client.get("/ajustes").json()["ajustes"]
    assert all(a[k] == v for k, v in ok.items())

    for malo in ({"ui.tema": "rosa"}, {"ui.densidad": "enorme"}, {"ui.acento": "#fff;}body{"},
                 {"modelos.precargar": "si"}, {"proyectos.dir": "relativa"}, {"export.dir": "x\\y"},
                 {"proyectos.dir": str(ROOT_DIR)}, {"lab.backend": "docker"}, {"umbral.complejidad_nube": "mucho"},
                 {"seguro.que.no": "1"}):
        r = client.put("/ajustes", json=malo)
        assert r.status_code == 400, malo


def test_tst061_clave_de_la_nube_en_keyring_no_en_bbdd(client, keyring_memoria):
    assert client.put("/ajustes", json={"nube.backend": "api", "nube.api_key": "sk-ant-secreta",
                                        "nube.activada": "1"}).status_code == 200
    assert "sk-ant-secreta" in keyring_memoria.datos.values()
    with sqlite3.connect(client.app.state.db.path) as c:
        volcado = "\n".join(c.iterdump())
    assert "sk-ant-secreta" not in volcado and "sk-ant-secreta" not in client.get("/ajustes").text


# ======================================================================= TST-062 export a Markdown
def test_tst062_export_de_conversacion(client, tmp_path):
    client.app.state.db.set_setting("export.dir", str(tmp_path / "export"))
    sid = chat(client, "escríbeme un hola mundo")[0][1]["sesion_id"]
    chat(client, "ahora en C", sesion_id=sid, esfuerzo="medio")
    client.app.state.db.execute("UPDATE messages SET thinking = 'pienso en C' WHERE rol = 'assistant'")

    r = client.post("/export", json={"tipo": "conversacion", "id": sid}).json()
    ruta = Path(r["ruta"])
    assert ruta.parent == tmp_path / "export" / "conversaciones" and ruta.suffix == ".md"
    md = ruta.read_text(encoding="utf-8")
    assert md == r["markdown"]
    assert md.startswith("# escríbeme un hola mundo\n")
    assert md.count("## Tú · ") == 2 and md.count("## FORJA · qwen2.5-coder:3b") == 2
    assert "```python\nprint('hola')\n```" in md
    assert "<details><summary>Razonamiento</summary>" in md and "pienso en C" in md
    aud = client.get("/auditoria").json()["auditoria"][0]
    assert aud["tipo"] == "export" and aud["detalle"]["tipo"] == "conversacion"

    sin = client.post("/export", json={"tipo": "conversacion", "id": sid, "incluir_razonamiento": False}).json()
    assert "pienso en C" not in sin["markdown"]
    vacia = client.post("/conversaciones", json={"modo": "scripts"}).json()["id"]
    assert client.post("/export", json={"tipo": "conversacion", "id": vacia}).status_code == 400
    assert client.post("/export", json={"tipo": "conversacion", "id": 999}).status_code == 404


# ======================================================================= TST-063 migración 008 sin perder datos
def test_tst063_migracion_008_conserva_datos(tmp_path, monkeypatch):
    import backend.db as dbmod

    reales = dbmod.MIGRATIONS_DIR
    hasta7 = tmp_path / "m7"
    hasta7.mkdir()
    for f in sorted(reales.glob("*.sql")):
        if int(f.name.split("_")[0]) <= 7:
            shutil.copy(f, hasta7 / f.name)
    monkeypatch.setattr(dbmod, "MIGRATIONS_DIR", hasta7)
    ruta = tmp_path / "forja.db"
    db = DB(ruta)
    assert db.schema_version() == 7
    cid = db.execute("INSERT INTO conversations(modo, titulo) VALUES ('scripts', 'hilo viejo')")
    db.execute("INSERT INTO messages(conversation_id, rol, contenido, tokens_out) VALUES (?, 'assistant', 'resp', 99)", (cid,))
    db.execute("INSERT INTO projects(nombre, carpeta) VALUES ('viejo', 'C:\\\\p')")
    db.execute("INSERT INTO audit_log(tipo, detalle) VALUES ('lab_accion', '{\"a\":1}')")
    db.set_setting("ui.tema", "claro")

    monkeypatch.setattr(dbmod, "MIGRATIONS_DIR", reales)
    db2 = DB(ruta)
    assert db2.schema_version() == 8
    assert db2.one("SELECT tokens_out, gen_ms FROM messages") == {"tokens_out": 99, "gen_ms": None}
    assert db2.one("SELECT nombre FROM projects")["nombre"] == "viejo"
    assert db2.one("SELECT tipo FROM audit_log")["tipo"] == "lab_accion"
    assert db2.get_setting("ui.tema") == "claro" and db2.get_setting("ui.proyectos") == "desplegable"
    db2.execute("INSERT INTO audit_log(tipo) VALUES ('guardar_archivo')")
    copias = list(tmp_path.glob("forja.db.bak-v7-*"))
    assert len(copias) == 1


# ======================================================================= TST-077/078/079 telemetría (doc 22)
class Reloj:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def test_tst077_tokens_tiempo_y_media_movil():
    r = Reloj()
    tel = Telemetria(500, 1024, "qwen3:4b", "pequeno", reloj=r)
    e = tel.evento()
    assert e["fase"] == "esperando" and e["tokens_out"] == 0 and e["tok_s"] is None and e["eta_ms"] is None
    r.t += 3                                     # carga / prompt eval: corre el tiempo sin tokens
    assert tel.evento()["elapsed_ms"] == 3000
    for _ in range(40):                          # 10 tok/s
        r.t += 0.1
        tel.token()
    e = tel.evento()
    assert e["tokens_out"] == 40 and e["elapsed_ms"] == 7000 and 9 <= e["tok_s"] <= 11
    for _ in range(60):                          # el equipo se carga: 4 tok/s → la media (~2 s) reacciona
        r.t += 0.25
        tel.token()
    assert 3.5 <= tel.tok_s() <= 4.5


def test_tst078_eta_aproximada_nunca_negativa_y_se_afina():
    r = Reloj()
    tel = Telemetria(100, 1024, "m", "pequeno", reloj=r)
    for _ in range(5):
        r.t += 0.1
        tel.token()
    assert tel.eta_ms() is None                  # pocos tokens: "estimando…"
    for _ in range(15):
        r.t += 0.1
        tel.token()
    eta = tel.eta_ms()
    assert eta is not None and 7000 <= eta <= 9000   # 80 tokens a ~10 tok/s
    for _ in range(100):                         # se pasa de lo previsto: el objetivo crece, la ETA no baja de 0
        r.t += 0.1
        tel.token()
        assert tel.eta_ms() >= 0
    assert tel.objetivo > tel.tokens_out
    # Tope = num_predict: nunca promete más de lo que el modelo puede escribir.
    tel2 = Telemetria(5000, 300, "m", "pequeno", reloj=Reloj())
    assert tel2.objetivo == 300
    # Secuencias aleatorias: nunca negativa.
    rnd = random.Random(7)
    tel3 = Telemetria(rnd.randint(50, 800), 900, "m", "pequeno", reloj=(r3 := Reloj()))
    for _ in range(600):
        r3.t += rnd.choice([0.01, 0.05, 0.2, 0.8, 2.5])
        tel3.token(rnd.randint(0, 3)) if rnd.random() < 0.7 else tel3.thinking()
        v = tel3.eta_ms()
        assert v is None or v >= 0
    # La salida estimada mezcla el estimador con lo que tardaron respuestas anteriores.
    assert objetivo_tokens(800, "bajo", False) == 800
    assert objetivo_tokens(800, "extra", True) == 800 + tel_mod.THINKING_PREVISTO["extra"]
    assert objetivo_tokens(800, "bajo", False, [200, 200, 200]) == 500


def test_tst079_fases_y_tiempo_de_pensar():
    r = Reloj()
    tel = Telemetria(500, 1024, "qwen3:4b", "pequeno", reloj=r)
    r.t += 1
    tel.thinking()
    assert tel.fase == "pensando"
    r.t += 4
    tel.thinking()
    r.t += 1
    tel.token()
    assert tel.fase == "respondiendo" and tel.thinking_ms() == 5000
    r.t += 2
    tel.token()
    assert tel.thinking_ms() == 5000             # el tiempo de pensar no sigue corriendo al responder


class NubeLenta:
    """Como FakeNube, pero con pausas: deja ver ticks de telemetría en vivo y el cambio de fase."""

    def __init__(self):
        self.envios = []

    async def probar(self, modelo, backend="api"):
        return {"modelo": modelo}

    async def stream(self, modelo, system, mensajes, esfuerzo, backend="api"):
        self.envios.append(mensajes)
        await asyncio.sleep(0.7)
        for _ in range(4):
            yield {"tipo": "thinking", "texto": "razono un poco más sobre esto "}
            await asyncio.sleep(0.3)
        for _ in range(10):
            yield {"tipo": "token", "texto": "palabra palabra palabra "}
            await asyncio.sleep(0.15)
        yield {"tipo": "fin", "stop_reason": "end_turn", "categoria": None, "modelo": modelo,
               "tokens_in": 10, "tokens_out": 120}


def test_tst077_079_sse_telemetria_en_vivo(tmp_path, fake):
    app = create_app(db_path=tmp_path / "f.db", ollama_transport=fake.transport(), precargar=False, token=TOKEN,
                     nube=NubeLenta())
    with TestClient(app) as c:
        c.headers.update({"X-Forja-Token": TOKEN})
        c.put("/ajustes", json={"nube.backend": "api", "nube.api_key": "sk-ant-x", "nube.activada": "1"})
        evs = eventos(c.post("/chat", json={"modo": "scripts", "tier": "nube", "esfuerzo": "medio",
                                            "texto": "explícame algo", "forzar": True}).text)
    tele = [d for e, d in evs if e == "telemetria"]
    assert len(tele) >= 5                                         # ~cada 0,5 s durante ~3 s
    assert all(set(d) >= {"fase", "elapsed_ms", "tokens_out", "tok_s", "eta_ms", "modelo", "tier"} for d in tele)
    assert [d["elapsed_ms"] for d in tele] == sorted(d["elapsed_ms"] for d in tele)
    assert tele[0]["fase"] == "esperando" and tele[0]["tokens_out"] == 0
    assert any(d["fase"] == "esperando" and d["elapsed_ms"] >= 400 for d in tele)   # corre antes del 1.er token
    fases = [d["fase"] for d in tele]
    assert "pensando" in fases and "respondiendo" in fases
    assert fases.index("pensando") < fases.index("respondiendo")
    assert max(d["tokens_out"] for d in tele) > 0 and any(d["tok_s"] for d in tele)
    assert all(d["eta_ms"] is None or d["eta_ms"] >= 0 for d in tele)
    fin = next(d for e, d in evs if e == "fin")
    assert fin["gen_ms"] >= 2500 and 800 <= fin["thinking_ms"] <= 2000
    m = app.state.db.one("SELECT gen_ms, thinking_ms FROM messages WHERE rol = 'assistant'")
    assert m["gen_ms"] == fin["gen_ms"] and m["thinking_ms"] == fin["thinking_ms"]


def test_con_ticks_intercala_none_sin_perder_datos():
    async def origen():
        yield 1
        await asyncio.sleep(0.35)
        yield 2
        raise ValueError("fallo del origen")

    async def leer():
        out = []
        with pytest.raises(ValueError):
            async for x in con_ticks(origen(), intervalo=0.1):
                out.append(x)
        return out

    out = asyncio.run(leer())
    assert [x for x in out if x is not None] == [1, 2] and out.count(None) >= 2


# ======================================================================= no funcionales
def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_tst100_app_sin_modelo_menos_de_300_mb(tmp_path):
    from backend.sistema import ram_proceso_mb

    puerto = _puerto_libre()
    codigo = ("import sys, uvicorn; from pathlib import Path; from backend.main import create_app; "
              f"uvicorn.run(create_app(db_path=Path(sys.argv[1]), precargar=False, token='t'), host='127.0.0.1', "
              f"port={puerto}, log_level='error')")
    env = {**os.environ, "FORJA_OLLAMA_URL": "http://127.0.0.1:9", "FORJA_DATA_DIR": str(tmp_path)}
    proc = subprocess.Popen([sys.executable, "-c", codigo, str(tmp_path / "f.db")], cwd=ROOT_DIR, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        h = {"X-Forja-Token": "t"}
        for _ in range(100):
            try:
                if httpx.get(f"http://127.0.0.1:{puerto}/ajustes", headers=h, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            pytest.fail("el backend no arrancó")
        for ruta in ("/", "/salud", "/modelos", "/conversaciones", "/plantillas", "/proyectos", "/listas",
                     "/academia/rutas"):
            httpx.get(f"http://127.0.0.1:{puerto}{ruta}", headers=h, timeout=10)
        rss = ram_proceso_mb(proc.pid)
        assert rss is not None and rss < 300, f"{rss} MB"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_tst101_interacciones_locales_rapidas_y_streaming(client, tmp_path):
    proyecto(client, tmp_path)
    chat(client, "calentar")
    for ruta in ("/ajustes", "/conversaciones?modo=scripts", "/plantillas", "/proyectos", "/listas", "/modelos"):
        client.get(ruta)
        tiempos = []
        for _ in range(5):
            t0 = time.perf_counter()
            assert client.get(ruta).status_code == 200
            tiempos.append(time.perf_counter() - t0)
        assert statistics.median(tiempos) < 0.1, (ruta, tiempos)


def test_tst101_la_respuesta_llega_en_streaming(tmp_path, fake):
    """El primer trozo llega mucho antes de que termine la generación (no se espera a tenerlo todo)."""

    async def lento(req: httpx.Request):
        if req.url.path != "/api/chat":
            return fake.handle(req)
        fake.handle(req)                                       # registra la petición (y carga el modelo)

        async def cuerpo():
            for i in range(8):
                yield (json.dumps({"message": {"role": "assistant", "content": f"t{i} "}, "done": False}) + "\n").encode()
                await asyncio.sleep(0.2)
            yield (json.dumps({"message": {"content": ""}, "done": True, "eval_count": 8,
                               "eval_duration": 1_600_000_000}) + "\n").encode()
        return httpx.Response(200, content=cuerpo())

    app = create_app(db_path=tmp_path / "f.db", ollama_transport=httpx.MockTransport(lento), precargar=False,
                     token=TOKEN)
    with TestClient(app) as c:
        c.headers.update({"X-Forja-Token": TOKEN})
        t0 = time.perf_counter()
        llegadas = []
        with c.stream("POST", "/chat", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "bajo",
                                             "texto": "hola", "forzar": True}) as r:
            for linea in r.iter_lines():
                if linea.startswith("event: token"):
                    llegadas.append(time.perf_counter() - t0)
        total = time.perf_counter() - t0
    assert len(llegadas) == 8 and llegadas[0] < total - 1.0


def test_tst102_nucleo_sin_red(client, tmp_path, monkeypatch):
    intentos: list = []
    reales = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo)

    def local(direccion) -> bool:
        host = direccion[0] if isinstance(direccion, tuple) else direccion
        return host in ("127.0.0.1", "localhost", "::1", None)

    def connect(self, direccion):
        if not local(direccion):
            intentos.append(direccion)
            raise OSError("sin red (TST-102)")
        return reales[0](self, direccion)

    def connect_ex(self, direccion):
        if not local(direccion):
            intentos.append(direccion)
            return 10051
        return reales[1](self, direccion)

    def create_connection(direccion, *a, **kw):
        if not local(direccion):
            intentos.append(direccion)
            raise OSError("sin red (TST-102)")
        return reales[2](direccion, *a, **kw)

    def getaddrinfo(host, *a, **kw):
        if not local((host,)):
            intentos.append(host)
            raise socket.gaierror("sin red (TST-102)")
        return reales[3](host, *a, **kw)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)

    client.app.state.db.set_setting("export.dir", str(tmp_path / "export"))
    assert client.get("/salud").json()["ollama"] == "ok"
    sid = chat(client, "script offline")[0][1]["sesion_id"]
    p = proyecto(client, tmp_path)
    assert client.post(f"/proyectos/{p['id']}/guardar-archivo",
                       json={"nombre": "a.py", "contenido": "x", "confirmado": True}).status_code == 200
    assert client.get("/plantillas").status_code == 200
    assert client.post("/export", json={"tipo": "conversacion", "id": sid}).status_code == 200
    lid = client.post("/listas", json={"nombre": "offline"}).json()["id"]
    client.post("/tareas", json={"lista_id": lid, "texto": "revisar firmware mañana 30 min"})
    assert client.post("/tareas/organizar", json={"lista_id": lid, "esfuerzo": "bajo"}).status_code == 200
    assert client.get("/academia/rutas").status_code == 200
    assert intentos == []


def test_tst102_la_ui_no_carga_nada_de_internet():
    externos = []
    for f in UI_DIR.iterdir():
        if f.suffix not in (".html", ".css", ".js"):
            continue
        txt = f.read_text(encoding="utf-8")
        externos += [(f.name, m) for m in re.findall(r"""(?:src|href)\s*=\s*["'](https?://[^"']+)""", txt)]
        externos += [(f.name, m) for m in re.findall(r"""@import\s+(?:url\()?["']?(https?://[^"')]+)""", txt)]
        externos += [(f.name, m) for m in re.findall(r"""url\(\s*["']?(https?://[^"')]+)""", txt)]
        externos += [(f.name, m) for m in re.findall(r"""fetch\(\s*["'`](https?://[^"'`]+)""", txt)]
    assert externos == []
