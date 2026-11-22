"""Rama 6b — Verificador de código (MOD-110, 23-verificador-codigo.md). TST-080/081/082 + degradación e instalación."""
from __future__ import annotations

import shutil

import pytest

from backend import verificador

from .conftest import eventos

HAY_BASH = verificador._bash_cmd() is not None
HAY_NODE = verificador._node_exe() is not None
HAY_PS = verificador._powershell_exe() is not None


def verificar(client, lenguaje, codigo):
    r = client.post("/scripts/verificar", json={"lenguaje": lenguaje, "codigo": codigo})
    assert r.status_code == 200, r.text
    return r.json()


# --- TST-080 detecta un error de sintaxis Python con su línea -------------------------------------------
def test_tst080_python_error_de_sintaxis_con_su_linea(client):
    codigo = "import os\n\ndef lista(ruta):\n    for f in os.listdir(ruta)\n        print(f)\n"
    r = verificar(client, "python", codigo)
    assert r["ok"] is False and r["disponible"] is True and r["herramienta"].startswith("py_compile")
    assert r["errores"][0]["linea"] == 4 and r["errores"][0]["severidad"] == "error"
    assert r["errores"][0]["mensaje"]
    bien = verificar(client, "py", "def lista(ruta):\n    return sorted(ruta)\n")
    assert bien == {"ok": True, "disponible": True, "herramienta": bien["herramienta"], "errores": [],
                    "lenguaje": "python", "soportado": True}


def test_tst080_python_indentacion(client):
    r = verificar(client, "python", "if True:\nprint('x')\n")
    assert not r["ok"] and r["errores"][0]["linea"] == 2


@pytest.mark.skipif(not HAY_PS, reason="sin PowerShell")
def test_powershell_error_con_su_linea(client):
    r = verificar(client, "ps1", "Write-Host 'a'\nfunction Hola {\n  Write-Host 'hola'\n")
    assert not r["ok"] and r["herramienta"].startswith("parser de PowerShell")
    assert r["errores"][0]["linea"] in (2, 3) and r["errores"][0]["mensaje"]
    assert verificar(client, "powershell", "Get-ChildItem | Where-Object { $_.Length -gt 1 }\n")["ok"]


@pytest.mark.skipif(not HAY_BASH, reason="sin Git-Bash ni WSL")
def test_bash_error_con_su_linea(client):
    r = verificar(client, "bash", "echo uno\nif [ -f x ]; then\n  echo dos\n")
    assert not r["ok"] and r["herramienta"].startswith("bash -n") and r["errores"][0]["linea"]
    assert verificar(client, "sh", "echo hola\n")["ok"]


@pytest.mark.skipif(not HAY_NODE, reason="sin Node")
def test_javascript_error_con_su_linea(client):
    r = verificar(client, "js", "const a = 1;\nfunction f() {\n  return a;\n}}\n")
    assert not r["ok"] and r["herramienta"] == "node --check" and r["errores"][0]["linea"] == 4
    assert verificar(client, "javascript", "import fs from 'fs';\nconsole.log(fs.existsSync('.'));\n")["ok"]


# --- TST-081 NO ejecuta el código -----------------------------------------------------------------------
def _ruta(tmp_path, nombre):
    return (tmp_path / nombre).as_posix()


def test_tst081_python_no_ejecuta(client, tmp_path, capsys):
    marca = tmp_path / "py.txt"
    codigo = (f"import os\nprint('EFECTO-PY')\nopen({str(marca)!r}, 'w').write('ejecutado')\n"
              f"os.makedirs({str(tmp_path / 'dir-py')!r})\n")
    r = verificar(client, "python", codigo)
    assert r["ok"] is True
    assert not marca.exists() and not (tmp_path / "dir-py").exists()
    assert "EFECTO-PY" not in capsys.readouterr().out


@pytest.mark.skipif(not HAY_PS, reason="sin PowerShell")
def test_tst081_powershell_no_ejecuta(client, tmp_path):
    marca = tmp_path / "ps.txt"
    r = verificar(client, "powershell", f"Set-Content -Path '{marca}' -Value 'ejecutado'\nWrite-Output 'EFECTO'\n")
    assert r["ok"] is True and not marca.exists()


@pytest.mark.skipif(not HAY_BASH, reason="sin Git-Bash ni WSL")
def test_tst081_bash_no_ejecuta(client, tmp_path):
    if verificador._bash_cmd()[0] == "WSL":
        pytest.skip("rutas de Windows en WSL")
    marca = _ruta(tmp_path, "sh.txt")
    r = verificar(client, "bash", f"echo ejecutado > '{marca}'\ntouch '{marca}.2'\n")
    assert r["ok"] is True and not (tmp_path / "sh.txt").exists() and not (tmp_path / "sh.txt.2").exists()


@pytest.mark.skipif(not HAY_NODE, reason="sin Node")
def test_tst081_javascript_no_ejecuta(client, tmp_path):
    marca = _ruta(tmp_path, "js.txt")
    r = verificar(client, "js", f"require('fs').writeFileSync({marca!r}, 'ejecutado');\n")
    assert r["ok"] is True and not (tmp_path / "js.txt").exists()


def test_tst081_el_entorno_no_carga_codigo_ajeno(monkeypatch):
    monkeypatch.setenv("BASH_ENV", "/tmp/malo.sh")
    monkeypatch.setenv("NODE_OPTIONS", "--require ./malo.js")
    env = verificador._entorno()
    assert "BASH_ENV" not in env and "NODE_OPTIONS" not in env


# --- Degradación: falta la herramienta / lenguaje sin verificador --------------------------------------
def test_sin_herramienta_avisa_y_ofrece_instalar(client, monkeypatch):
    monkeypatch.setattr(verificador, "_bash_cmd", lambda: None)
    r = verificar(client, "bash", "echo hola\n")
    assert r["ok"] is False and r["disponible"] is False and r["herramienta"] is None
    assert "requiere WSL o Git-Bash" in r["aviso"]
    assert r["instalar"]["id"] == "git" and r["instalar"]["comando"] == "winget install --id Git.Git -e"
    monkeypatch.setattr(verificador, "_node_exe", lambda: None)
    r = verificar(client, "js", "1;")
    assert r["disponible"] is False and r["instalar"]["id"] == "node"


def test_lenguaje_sin_verificador(client):
    r = verificar(client, "rust", "fn main() {}")
    assert r["ok"] is False and r["soportado"] is False and "Soportados" in r["aviso"] and "instalar" not in r


def test_instalar_solo_con_confirmacion_y_auditado(client, monkeypatch):
    lanzados = []
    monkeypatch.setattr(verificador, "lanzar", lambda *a, **k: lanzados.append(a[0]))
    monkeypatch.setattr(verificador.shutil, "which", lambda n: "C:/winget.exe" if n == "winget" else shutil.which(n))
    p = client.post("/scripts/verificar/instalar", json={"id": "git"}).json()
    assert p["estado"] == "esperando_usuario" and not lanzados
    r = client.post("/scripts/verificar/instalar", json={"id": "git", "confirmado": True}).json()
    assert r["estado"] == "ejecutando" and "Git.Git" in " ".join(lanzados[0])
    aud = client.app.state.db.query("SELECT tipo, detalle FROM audit_log WHERE tipo = 'verificador_instalar'")
    assert len(aud) == 1 and '"confirmado": true' in aud[0]["detalle"]
    assert client.post("/scripts/verificar/instalar", json={"id": "rm-rf", "confirmado": True}).status_code == 400


def test_herramientas_disponibles(client):
    h = client.get("/scripts/verificar/herramientas").json()
    assert h["python"]["disponible"] is True and set(h) == {"python", "powershell", "bash", "javascript"}


# --- TST-082 «Corregir con la IA» devuelve una versión nueva --------------------------------------------
def test_tst082_corregir_devuelve_version_nueva(client, fake):
    malo = "def lista(ruta):\n    for f in os.listdir(ruta)\n        print(f)\n"
    errores = verificar(client, "python", malo)["errores"]
    fake.respuesta = ["```python\nimport os\n\n", "def lista(ruta):\n    for f in os.listdir(ruta):\n",
                      "        print(f)\n```\n", "- Faltaban `:` y el `import os`."]
    evs = eventos(client.post("/scripts/corregir", json={"tier": "pequeno", "esfuerzo": "bajo", "lenguaje": "python",
                                                        "codigo": malo, "errores": errores}).text)
    assert next(d for ev, d in evs if ev == "inicio")["modelo"] == "qwen2.5-coder:3b"     # modo Scripts
    pedido = fake.chats[-1]["messages"][-1]["content"]
    assert "línea 2" in pedido and malo.strip() in pedido and "```python" in pedido
    respuesta = "".join(d["texto"] for ev, d in evs if ev == "token")
    nuevo = respuesta.split("```python\n", 1)[1].split("```", 1)[0]
    assert nuevo != malo and verificar(client, "python", nuevo)["ok"] is True          # versión nueva y válida
    fin = next(d for ev, d in evs if ev == "fin")
    msgs = client.get(f"/conversaciones/{fin['sesion_id']}/mensajes").json()["mensajes"]
    assert msgs[1]["contenido"] == respuesta                                             # queda en el hilo


def test_ui_tiene_comprobar_y_corregir():
    from backend.config import ROOT_DIR
    md = (ROOT_DIR / "ui/markdown.js").read_text(encoding="utf-8")
    js = (ROOT_DIR / "ui/verificador.js").read_text(encoding="utf-8")
    html = (ROOT_DIR / "ui/index.html").read_text(encoding="utf-8")
    assert "code-comprobar" in md and "/scripts/verificar" in js and "/scripts/corregir" in js
    assert "/ui/verificador.js" in html and "/ui/verificador.css" in html
    # Los alias del fence en la UI = los del backend (mismo conjunto de lenguajes verificables).
    import re
    ui = set(re.search(r"VERIFICABLES = new Set\(\[([^\]]+)\]", md)[1].replace("\n", "").replace('"', "").replace(" ", "").split(","))
    assert ui == {k for k, v in verificador.ALIAS.items() if v}
