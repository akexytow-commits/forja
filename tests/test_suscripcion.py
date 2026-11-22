"""Nube vía suscripción Claude (CLI de Claude Code), con un CLI falso."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

from backend import cloud_client
from backend.cloud_client import ClienteClaudeCode, NubeError, componer_prompt

FALSO = Path(__file__).parent / "fixtures" / "claude_falso.py"


@pytest.fixture
def cli_falso(monkeypatch, tmp_path):
    registro = tmp_path / "registro.json"
    monkeypatch.setenv("FAKE_CC_REGISTRO", str(registro))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-no-debe-pasar")
    original = ClienteClaudeCode._comando

    def comando(self, modelo, system, esfuerzo):
        args = original(self, modelo, system, esfuerzo)
        return [sys.executable, str(FALSO), *args[1:]]

    monkeypatch.setattr(ClienteClaudeCode, "_bin", lambda self: "claude")
    monkeypatch.setattr(ClienteClaudeCode, "_comando", comando)
    return registro


async def recoger(gen):
    return [ev async for ev in gen]


def test_stream_por_suscripcion(cli_falso):
    mensajes = [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "qué tal"},
                {"role": "user", "content": "escribe el driver"}]
    evs = asyncio.run(recoger(ClienteClaudeCode().stream("claude-opus-5-5", "SYS", mensajes, "extra")))
    assert evs[0] == {"tipo": "thinking", "texto": "Pienso."}
    assert "".join(e["texto"] for e in evs if e["tipo"] == "token") == "Hola desde la suscripción"
    fin = evs[-1]
    assert fin["tipo"] == "fin" and fin["tokens_in"] == 13 and fin["tokens_out"] == 7
    assert fin["modelo"] == "claude-opus-5-5"

    reg = json.loads(cli_falso.read_text(encoding="utf-8"))
    a = reg["args"]
    assert a[a.index("--effort") + 1] == "high" and a[a.index("--tools") + 1] == ""
    assert a[a.index("--system-prompt") + 1] == "SYS" and "--no-session-persistence" in a
    assert reg["api_key"] is None  # nunca factura por API sin querer
    assert reg["prompt"].endswith("escribe el driver") and "<asistente>\nqué tal" in reg["prompt"]


def test_sin_sesion_da_error_claro(cli_falso, monkeypatch):
    monkeypatch.setenv("FAKE_CC_MODO", "login")
    with pytest.raises(NubeError) as e:
        asyncio.run(recoger(ClienteClaudeCode().stream("claude-opus-5-5", "S", [{"role": "user", "content": "x"}],
                                                       "bajo")))
    assert e.value.codigo == "NUBE_SIN_SESION"


def test_componer_prompt_sin_historial():
    assert componer_prompt([{"role": "user", "content": "solo esto"}]) == "solo esto"


def test_activar_suscripcion_requiere_cli(client, monkeypatch, tmp_path):
    r = client.put("/ajustes", json={"nube.backend": "claude_code", "nube.activada": "1"})
    assert r.json()["error"]["codigo"] == "NUBE_SIN_CLI"
    falso = tmp_path / "claude.exe"
    falso.write_text("")
    monkeypatch.setenv("FORJA_CLAUDE_BIN", str(falso))
    aj = client.put("/ajustes", json={"nube.backend": "claude_code", "nube.activada": "1"}).json()["ajustes"]
    assert aj["nube.activada"] == "1" and aj["nube.tiene_cli"] == "1" and aj["nube.backend"] == "claude_code"
    assert cloud_client.activada(client.app.state.db)
    assert client.put("/ajustes", json={"nube.backend": "openai"}).status_code == 400


def test_chat_nube_pasa_el_proveedor(client, nube, monkeypatch, tmp_path):
    falso = tmp_path / "claude.exe"
    falso.write_text("")
    monkeypatch.setenv("FORJA_CLAUDE_BIN", str(falso))
    client.put("/ajustes", json={"nube.activada": "1"})
    with client.stream("POST", "/chat", json={"modo": "scripts", "tier": "nube", "esfuerzo": "medio",
                                               "texto": "hola"}) as r:
        r.read()
    assert nube.envios[-1]["backend"] == "claude_code"
    aud = client.get("/auditoria").json()["auditoria"][0]
    assert aud["detalle"]["backend"] == "claude_code"
    est = client.post("/estimar", json={"modo": "scripts", "tier": "pequeno", "esfuerzo": "medio",
                                        "texto": "hola"}).json()
    assert "suscripción" in est["resumen_envio"]["texto"]


def test_sin_sesion_deshabilita_la_nube(client, monkeypatch, tmp_path):
    """ADR-0006: con Claude Code sin sesión, el tier Nube queda deshabilitado y /salud lo dice."""
    falso = tmp_path / "claude.exe"
    falso.write_text("")
    monkeypatch.setenv("FORJA_CLAUDE_BIN", str(falso))
    client.put("/ajustes", json={"nube.activada": "1"})
    monkeypatch.setattr(cloud_client, "comprobar_sesion",
                        lambda forzar=False: cloud_client._SESION.update(estado="sin_sesion") or "sin_sesion")
    s = client.get("/salud").json()
    assert s["nube_estado"] == "sin_sesion" and s["nube_activada"] is False
    evs = client.post("/chat", json={"modo": "scripts", "tier": "nube", "esfuerzo": "medio", "texto": "x"}).text
    assert "NUBE_NO_ACTIVADA" in evs


def test_ruta_claude_bin_configurable(client, monkeypatch, tmp_path):
    monkeypatch.delenv("FORJA_CLAUDE_BIN")
    r = client.put("/ajustes", json={"nube.claude_bin": str(tmp_path / "no-hay.exe")})
    assert r.status_code == 400 and r.json()["error"]["codigo"] == "NUBE_SIN_CLI"
    mio = tmp_path / "mi-claude.exe"
    mio.write_text("")
    aj = client.put("/ajustes", json={"nube.claude_bin": f'"{mio}"'}).json()["ajustes"]
    assert aj["nube.claude_bin"] == str(mio) and cloud_client.ejecutable_claude() == str(mio)


def test_migracion_renombra_proveedor(tmp_path):
    """Una BBDD de la Rama 2 con nube.proveedor=anthropic pasa a nube.backend=api."""
    from backend.db import DB, MIGRATIONS_DIR
    import sqlite3
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)")
    for f in sorted(MIGRATIONS_DIR.glob("*.sql"))[:3]:
        con.executescript(f.read_text(encoding="utf-8"))
        con.execute("INSERT INTO schema_version VALUES (?, 'x')", (int(f.name[:3]),))
    con.execute("UPDATE settings SET value = 'anthropic' WHERE key = 'nube.proveedor'")
    con.commit(); con.close()
    db = DB(ruta)
    assert db.get_setting("nube.backend") == "api" and db.get_setting("nube.proveedor") is None
