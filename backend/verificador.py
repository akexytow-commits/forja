"""MOD-110 Verificador de código (23-verificador-codigo.md) — API-032.

Pasa el código generado por las herramientas REALES del lenguaje. Regla de seguridad: SOLO análisis estático /
de sintaxis; NUNCA se ejecuta el código:
- Python: compile() del propio intérprete (= py_compile: compila a bytecode, no lo ejecuta) + `ruff` si está.
  Se hace en el proceso, así funciona también empaquetado (.exe), donde no hay un python.exe aparte.
- PowerShell: el parser de PowerShell (Parser::ParseFile, solo construye el AST) + PSScriptAnalyzer si está.
- Bash: `bash -n` (noexec: solo lee y parsea) con Git-Bash o WSL + `shellcheck` si está.
- JavaScript: `node --check` (solo comprueba la sintaxis).
A los procesos se les quita del entorno lo que podría hacerles cargar código ajeno al arrancar (BASH_ENV, ENV,
NODE_OPTIONS…) y PowerShell va con -NoProfile.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

MAX_CODIGO = 200_000
TIMEOUT_S = 30
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

ALIAS = {
    "python": "python", "py": "python", "python3": "python", "py3": "python",
    "powershell": "powershell", "ps1": "powershell", "pwsh": "powershell", "ps": "powershell", "posh": "powershell",
    "bash": "bash", "sh": "bash", "shell": "bash", "zsh": "bash", "console": None,
    "javascript": "javascript", "js": "javascript", "node": "javascript", "mjs": "javascript", "cjs": "javascript",
    "jsx": None,
}
NOMBRE = {"python": "Python", "powershell": "PowerShell", "bash": "Bash", "javascript": "JavaScript"}

# Oferta de instalación (ST-040: solo con confirmación). Id → winget.
INSTALABLES = {
    "git": {"descripcion": "Git for Windows (incluye Git-Bash, que trae `bash -n`)", "winget": "Git.Git"},
    "node": {"descripcion": "Node.js LTS (trae `node --check`)", "winget": "OpenJS.NodeJS.LTS"},
    "shellcheck": {"descripcion": "ShellCheck (análisis estático de Bash)", "winget": "koalaman.shellcheck"},
    "ruff": {"descripcion": "Ruff (linter de Python)", "winget": "astral-sh.ruff"},
}

# Punto de enganche: las pruebas lo sustituyen (nunca se lanza un instalador real desde los tests).
lanzar = subprocess.Popen


class VerificadorError(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje = status, codigo, mensaje


def normalizar_lenguaje(lenguaje: str | None) -> str | None:
    """Etiqueta del fence (```python, ```ps1…) → lenguaje soportado, o None."""
    return ALIAS.get((lenguaje or "").strip().lower().lstrip("."))


def _entorno() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k.upper() not in {"BASH_ENV", "ENV", "NODE_OPTIONS", "NODE_PATH", "PYTHONSTARTUP", "SHELLOPTS",
                                "BASHOPTS", "PROMPT_COMMAND"}}
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _correr(args: list[str], entrada: str | None = None, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, input=entrada.encode("utf-8") if entrada is not None else None,
                          capture_output=True, timeout=TIMEOUT_S, env=_entorno(), cwd=cwd,
                          creationflags=SIN_VENTANA, stdin=None if entrada is not None else subprocess.DEVNULL)


def _txt(b: bytes) -> str:
    for enc in ("utf-8", "cp1252"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def _err(linea: int | None, mensaje: str, columna: int | None = None, severidad: str = "error") -> dict[str, Any]:
    e: dict[str, Any] = {"linea": linea, "mensaje": mensaje.strip(), "severidad": severidad}
    if columna:
        e["columna"] = columna
    return e


def _resultado(errores: list[dict[str, Any]], herramienta: str, **extra: Any) -> dict[str, Any]:
    errores.sort(key=lambda e: (e.get("linea") or 0, e.get("columna") or 0))
    return {"ok": not any(e["severidad"] == "error" for e in errores), "disponible": True,
            "herramienta": herramienta, "errores": errores, **extra}


def _no_disponible(lenguaje: str, aviso: str, instalar: str | None = None) -> dict[str, Any]:
    r: dict[str, Any] = {"ok": False, "disponible": False, "herramienta": None, "lenguaje": lenguaje,
                         "errores": [], "aviso": aviso}
    if instalar:
        r["instalar"] = {"id": instalar, **INSTALABLES[instalar],
                         "comando": f"winget install --id {INSTALABLES[instalar]['winget']} -e"}
    return r


# ---------------------------------------------------------------- Python
def _python(codigo: str) -> dict[str, Any]:
    errores: list[dict[str, Any]] = []
    try:
        # compile() = lo que hace py_compile: genera bytecode, NO lo ejecuta (no hay exec/eval aquí).
        compile(codigo, "<bloque>", "exec", dont_inherit=True)
    except SyntaxError as e:          # incluye IndentationError / TabError
        errores.append(_err(e.lineno, e.msg, e.offset))
    except ValueError as e:           # p. ej. bytes nulos
        errores.append(_err(1, str(e)))
    herramienta = "py_compile"
    ruff = shutil.which("ruff")
    if ruff:
        try:
            p = _correr([ruff, "check", "--isolated", "--no-cache", "--output-format", "json", "--stdin-filename",
                         "bloque.py", "-"], entrada=codigo)
            vistos = {(e["linea"], e.get("columna")) for e in errores}
            for d in json.loads(_txt(p.stdout) or "[]"):
                loc = d.get("location") or {}
                clave = (loc.get("row"), loc.get("column"))
                if clave in vistos and not d.get("code"):
                    continue
                cod = d.get("code") or ""
                grave = not cod or cod.startswith(("E9", "F63", "F7", "F82"))   # sintaxis / nombres sin definir
                errores.append(_err(loc.get("row"), f"{cod}: {d.get('message')}" if cod else d.get("message", ""),
                                    loc.get("column"), "error" if grave else "aviso"))
            herramienta = "py_compile + ruff"
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
    return _resultado(errores, herramienta)


# ---------------------------------------------------------------- PowerShell
_PS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ruta = $env:FORJA_VERIF_RUTA
$tokens = $null; $errs = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($ruta, [ref]$tokens, [ref]$errs)
$r = @()
foreach ($e in $errs) { $r += @{ linea = $e.Extent.StartLineNumber; columna = $e.Extent.StartColumnNumber; mensaje = $e.Message; severidad = 'error' } }
$pssa = $false
if ($errs.Count -eq 0 -and (Get-Module -ListAvailable -Name PSScriptAnalyzer)) {
  $pssa = $true
  foreach ($d in (Invoke-ScriptAnalyzer -Path $ruta)) {
    $sev = 'aviso'; if ("$($d.Severity)" -eq 'Error' -or "$($d.Severity)" -eq 'ParseError') { $sev = 'error' }
    $r += @{ linea = $d.Line; columna = $d.Column; mensaje = "$($d.RuleName): $($d.Message)"; severidad = $sev }
  }
}
ConvertTo-Json -InputObject @{ errores = $r; pssa = $pssa } -Depth 4 -Compress
"""


def _powershell_exe() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def _powershell(codigo: str) -> dict[str, Any]:
    exe = _powershell_exe()
    if not exe:
        return _no_disponible("powershell", "Verificador de PowerShell no disponible: no encuentro powershell.exe.")
    with tempfile.TemporaryDirectory(prefix="forja-verif-") as d:
        ruta = Path(d) / "bloque.ps1"
        ruta.write_text(codigo, encoding="utf-8-sig")     # con BOM: PowerShell 5.1 lee bien los acentos
        env_extra = {"FORJA_VERIF_RUTA": str(ruta)}
        cmd = [exe, "-NoProfile", "-NonInteractive", "-EncodedCommand",
               base64.b64encode(_PS.encode("utf-16-le")).decode()]
        p = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT_S + 30, env={**_entorno(), **env_extra},
                           creationflags=SIN_VENTANA, stdin=subprocess.DEVNULL)
    salida = _txt(p.stdout).strip()
    try:
        datos = json.loads(salida.splitlines()[-1]) if salida else {}
    except (ValueError, IndexError):
        raise VerificadorError(500, "VERIFICADOR_FALLO", f"PowerShell no devolvió un resultado legible: {_txt(p.stderr)[:300]}")
    lista = datos.get("errores") or []
    if isinstance(lista, dict):
        lista = [lista]
    errores = [_err(e.get("linea"), e.get("mensaje", ""), e.get("columna"), e.get("severidad", "error")) for e in lista]
    return _resultado(errores, "parser de PowerShell" + (" + PSScriptAnalyzer" if datos.get("pssa") else ""))


# ---------------------------------------------------------------- Bash
def _git_bash() -> str | None:
    cands = []
    for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        if os.environ.get(var):
            cands.append(Path(os.environ[var]) / "Git" / "bin" / "bash.exe")
    if os.environ.get("LOCALAPPDATA"):
        cands.append(Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Git" / "bin" / "bash.exe")
    git = shutil.which("git")
    if git:
        g = Path(git).resolve()
        cands += [g.parent.parent / "bin" / "bash.exe", g.parent / "bash.exe"]
    for c in cands:
        if c.is_file():
            return str(c)
    if os.name != "nt":
        return shutil.which("bash")
    return None


def _wsl_con_distro() -> bool:
    wsl = shutil.which("wsl")
    if not wsl:
        return False
    try:
        p = _correr([wsl, "-l", "-q"])
        return bool(p.stdout.replace(b"\x00", b"").strip()) and p.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _bash_cmd() -> tuple[str, list[str]] | None:
    gb = _git_bash()
    if gb:
        return ("Git-Bash" if os.name == "nt" else "bash"), [gb, "-n"]
    if _wsl_con_distro():
        return "WSL", [shutil.which("wsl"), "-e", "bash", "-n"]
    return None


_RE_BASH = re.compile(r"line (\d+): (.*)")


def _bash(codigo: str) -> dict[str, Any]:
    eleccion = _bash_cmd()
    if not eleccion:
        return _no_disponible("bash", "Verificador de Bash no disponible: requiere WSL o Git-Bash.", "git")
    donde, cmd = eleccion
    # `bash -n` (noexec): lee el script de la entrada estándar y solo lo parsea; nada se ejecuta.
    p = _correr(cmd, entrada=codigo.replace("\r\n", "\n"))
    errores = []
    for linea in _txt(p.stderr).splitlines():
        m = _RE_BASH.search(linea)
        if m:
            errores.append(_err(int(m[1]), m[2]))
        elif linea.strip() and p.returncode != 0 and not errores:
            errores.append(_err(None, linea))
    herramienta = f"bash -n ({donde})"
    sc = shutil.which("shellcheck")
    if sc:
        try:
            q = _correr([sc, "-f", "json", "-s", "bash", "-"], entrada=codigo.replace("\r\n", "\n"))
            for d in json.loads(_txt(q.stdout) or "[]"):
                sev = "error" if d.get("level") == "error" else "aviso"
                errores.append(_err(d.get("line"), f"SC{d.get('code')}: {d.get('message')}", d.get("column"), sev))
            herramienta += " + shellcheck"
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
    return _resultado(errores, herramienta)


# ---------------------------------------------------------------- JavaScript
def _node_exe() -> str | None:
    n = shutil.which("node")
    if n:
        return n
    for var in ("ProgramFiles", "ProgramW6432"):
        c = Path(os.environ.get(var, "")) / "nodejs" / "node.exe"
        if os.environ.get(var) and c.is_file():
            return str(c)
    return None


def _javascript(codigo: str) -> dict[str, Any]:
    node = _node_exe()
    if not node:
        return _no_disponible("javascript", "Verificador de JavaScript no disponible: requiere Node.js.", "node")
    esm = re.search(r"^\s*(import\s.+from\s|import\s*['\"{*]|export\s)", codigo, re.M)
    with tempfile.TemporaryDirectory(prefix="forja-verif-") as d:
        ruta = Path(d) / ("bloque.mjs" if esm else "bloque.js")
        ruta.write_text(codigo, encoding="utf-8")
        p = _correr([node, "--check", str(ruta)], cwd=d)      # --check: solo sintaxis, no ejecuta
    errores = []
    if p.returncode != 0:
        err = _txt(p.stderr)
        m = re.search(r"bloque\.m?js:(\d+)", err)
        msg = next((l for l in err.splitlines() if re.match(r"\s*\w*Error\b", l)), err.strip().splitlines()[-1] if err.strip() else "error de sintaxis")
        errores.append(_err(int(m[1]) if m else None, msg))
    return _resultado(errores, "node --check")


VERIFICADORES = {"python": _python, "powershell": _powershell, "bash": _bash, "javascript": _javascript}


def verificar_sync(lenguaje: str | None, codigo: str) -> dict[str, Any]:
    if len(codigo) > MAX_CODIGO:
        raise VerificadorError(400, "CODIGO_GRANDE", f"El bloque supera {MAX_CODIGO} caracteres.")
    leng = normalizar_lenguaje(lenguaje)
    if leng is None:
        r = _no_disponible(lenguaje or "", f"No hay verificador para «{lenguaje or 'sin lenguaje'}». "
                                           "Soportados: Python, PowerShell, Bash y JavaScript.")
        r["soportado"] = False
        return r
    try:
        r = VERIFICADORES[leng](codigo)
    except subprocess.TimeoutExpired:
        raise VerificadorError(504, "VERIFICADOR_TIEMPO", f"El verificador de {NOMBRE[leng]} tardó demasiado.")
    except OSError as e:
        return _no_disponible(leng, f"No pude lanzar el verificador de {NOMBRE[leng]}: {e}")
    r.setdefault("lenguaje", leng)
    r.setdefault("soportado", True)
    return r


async def verificar(lenguaje: str | None, codigo: str) -> dict[str, Any]:
    return await asyncio.to_thread(verificar_sync, lenguaje, codigo)


def herramientas() -> dict[str, Any]:
    """Qué hay disponible en este equipo (para la UI)."""
    bash = _bash_cmd()
    return {"python": {"disponible": True, "extra": bool(shutil.which("ruff"))},
            "powershell": {"disponible": bool(_powershell_exe())},
            "bash": {"disponible": bool(bash), "donde": bash[0] if bash else None, "extra": bool(shutil.which("shellcheck"))},
            "javascript": {"disponible": bool(_node_exe())}}


def instalar(id_: str, confirmado: bool) -> dict[str, Any]:
    """ST-040: sin `confirmado` solo propone. Con él, abre winget en una ventana aparte (el usuario la ve)."""
    if id_ not in INSTALABLES:
        raise VerificadorError(400, "HERRAMIENTA_DESCONOCIDA", f"No sé instalar «{id_}».")
    info = INSTALABLES[id_]
    propuesta = {"id": id_, **info, "comando": f"winget install --id {info['winget']} -e"}
    if not confirmado:
        return {**propuesta, "estado": "esperando_usuario"}
    if not shutil.which("winget"):
        raise VerificadorError(400, "SIN_WINGET", "No encuentro winget: instala la herramienta a mano con su instalador.")
    try:
        lanzar(["powershell.exe", "-NoProfile", "-Command",
                f"Start-Process -FilePath winget -ArgumentList 'install','--id','{info['winget']}','-e'"],
               creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    except OSError as e:
        raise VerificadorError(500, "LANZAR_FALLO", f"No pude lanzar la instalación: {e}")
    return {**propuesta, "estado": "ejecutando",
            "mensaje": "Se abrió la instalación en una ventana aparte. Cuando termine, vuelve a pulsar «Comprobar»."}


# ---------------------------------------------------------------- BTN-102: prompt de corrección
def prompt_correccion(lenguaje: str | None, codigo: str, errores: list[dict[str, Any]]) -> str:
    leng = normalizar_lenguaje(lenguaje) or (lenguaje or "")
    fence = (lenguaje or leng or "").strip()
    lista = "\n".join(f"- línea {e.get('linea') or '?'}{', col. ' + str(e['columna']) if e.get('columna') else ''}: "
                      f"{e.get('mensaje', '')}" for e in errores[:40]) or "- (sin detalle)"
    return (f"El verificador estático de {NOMBRE.get(leng, leng) or 'código'} encontró estos errores en el bloque de abajo:\n"
            f"{lista}\n\nCorrígelos. Devuelve el bloque COMPLETO corregido en un único bloque ```{fence}``` y, debajo, "
            "una lista breve de qué cambiaste. No cambies nada más que lo necesario.\n\n"
            f"```{fence}\n{codigo.rstrip()}\n```")
