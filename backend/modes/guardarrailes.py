"""Guardarraíles del Modo Seguridad como CÓDIGO (ADR-0005, 10-...md G-1..G-5).

- Alcance: parsea lo declarado (dominios, comodines *.x, IPs, rangos CIDR, URLs) y decide si un host está
  dentro.
- G-3 lista "nunca": detecta peticiones de crear malware, evadir antivirus/EDR, ocultar rastro, DoS,
  phishing/robo de credenciales, o actuar contra objetivos fuera de alcance. No depende de que el modelo
  obedezca: se bloquea antes de llamarlo, se explica el límite y se reconduce.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .lenguaje import sin_tildes

# --- alcance ----------------------------------------------------------------------------------
_EXT_ARCHIVO = {"py", "js", "ts", "txt", "md", "json", "php", "html", "htm", "xml", "yaml", "yml", "csv", "log",
                "sh", "ps1", "exe", "dll", "png", "jpg", "jpeg", "gif", "svg", "css", "zip", "tar", "gz", "pdf",
                "c", "h", "cpp", "java", "go", "rb", "conf", "ini", "bak", "sql", "db", "asp", "aspx", "jsp"}
_RE_HOST = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}\b", re.I)
_RE_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b")


@dataclass
class Alcance:
    dominios: list[str]          # exactos: acme.com
    comodines: list[str]         # *.acme.com → acme.com (incluye subdominios)
    redes: list[ipaddress.IPv4Network]
    bruto: str

    @property
    def vacio(self) -> bool:
        return not (self.dominios or self.comodines or self.redes)


def parsear_alcance(texto: str) -> Alcance:
    dominios: list[str] = []
    comodines: list[str] = []
    redes: list[ipaddress.IPv4Network] = []
    for crudo in re.split(r"[\n,;]+", texto or ""):
        t = crudo.strip().lower()
        if not t or t.startswith("#"):
            continue
        t = re.split(r"\s+", t)[0]
        if "://" in t:
            t = urlsplit(t).hostname or ""
        t = t.split("/")[0] if not _RE_IP.fullmatch(t) else t
        t = t.rstrip(".")
        if not t:
            continue
        if _RE_IP.fullmatch(t):
            try:
                redes.append(ipaddress.ip_network(t, strict=False))
            except ValueError:
                pass
        elif t.startswith("*."):
            comodines.append(t[2:])
        elif _RE_HOST.fullmatch(t):
            dominios.append(t)
    return Alcance(dominios, comodines, redes, texto or "")


def en_alcance(host: str, alcance: Alcance) -> bool:
    h = host.lower().rstrip(".")
    if _RE_IP.fullmatch(h):
        try:
            ip = ipaddress.ip_address(h.split("/")[0])
        except ValueError:
            return False
        return any(ip in red for red in alcance.redes)
    if h in alcance.dominios:
        return True
    return any(h == c or h.endswith("." + c) for c in alcance.comodines)


def hosts_en(texto: str) -> list[str]:
    """Dominios e IPs mencionados en un texto (sin nombres de archivo tipo app.js o config.php)."""
    vistos: list[str] = []
    for m in _RE_IP.finditer(texto):
        if m.group(0) not in vistos:
            vistos.append(m.group(0).split("/")[0])
    for m in _RE_HOST.finditer(texto):
        h = m.group(0).lower()
        if h.rsplit(".", 1)[-1] in _EXT_ARCHIVO or h in vistos:
            continue
        # Evita trozos de IP o versiones ("1.2.3") ya filtrados por la regex (TLD alfabético).
        vistos.append(h)
    return vistos


# --- G-3 lista "nunca" --------------------------------------------------------------------------
_CREAR = r"(crea|creame|crear|escribe|escribeme|genera|generame|haz|hazme|programa|programame|desarrolla|codifica|" \
         r"construye|dame (el )?codigo|write|create|build|make|code)"
_ACCION_ACTIVA = r"(ataca|atacar|explota|explotar|escanea|escanear|fuzzea|fuzzear|fuerza bruta|bruteforce|brute force|" \
                 r"inyecta|inyectar|lanza|lanzar|tumba|tumbar|hackea|hackear|pentestea|scan|exploit|attack)"

REGLAS: list[tuple[str, re.Pattern, str]] = [
    ("malware",
     re.compile(_CREAR + r".{0,60}\b(ransomware|keylogger|troyano|trojan|botnet|rootkit|gusano|worm|stealer|infostealer|"
                r"malware|virus|spyware|cryptojacker|minero oculto|rat\b|backdoor)"),
     "No genero malware ni puertas traseras (lista «nunca», G-3)."),
    ("evasion",
     re.compile(r"(evadir|evade|evasion|bypass\w*|saltar(se)?|esquivar|burlar|desactivar|ofuscar)\b.{0,40}"
                r"\b(antivirus|av|edr|defender|amsi|deteccion|sandbox|siem)\b"),
     "No ayudo a evadir antivirus, EDR ni sistemas de detección (G-3)."),
    ("ocultar_rastro",
     re.compile(r"\b(borr|elimin|limpi|ocult)\w*\b.{0,30}\b(logs?|registros|rastros?|huellas|"
                r"evidencias|historial de eventos|event ?logs?)\b"),
     "No ayudo a ocultar actividad ni a borrar rastros (G-3)."),
    ("dos",
     re.compile(r"\b(ddos|denegacion de servicio|denial of service|ataque dos|dos attack|(syn|udp|icmp|http) flood|floodear|inundar|"
                r"tumbar (el|la|los|las) (servidor|servidores|web|servicio|servicios|pagina))\b"),
     "No ayudo con denegación de servicio: daña a terceros y casi ningún programa lo permite (G-3)."),
    ("phishing",
     re.compile(r"\b(kit de phishing|pagina de phishing|phishing kit|robar (las )?(credenciales|contrasenas|cookies) de|"
                r"capturar (las )?contrasenas de (los )?(usuarios|empleados|clientes))"),
     "No preparo phishing ni robo de credenciales de terceros (G-3)."),
    ("exploit_armado",
     re.compile(_CREAR + r".{0,40}\b(exploit (armado|funcional|completo|listo)|exploit weaponizado|weaponized exploit|"
                r"payload (destructivo|que borre|que cifre))"),
     "No entrego exploits armados listos para causar daño; sí te ayudo a verificar el fallo de forma segura (G-3)."),
]

RECONDUCCION = ("Lo que sí puedo hacer dentro de tu engagement: analizar los datos que aportes, señalar dónde "
                "enfocar, explicar el impacto, proponerte cómo verificarlo con bajo impacto y dentro de alcance, "
                "y redactar el informe con la evidencia que tú valides.")


@dataclass
class Bloqueo:
    categoria: str
    motivo: str
    reconduccion: str = RECONDUCCION
    hosts: list[str] | None = None


def evaluar(texto: str, alcance_texto: str) -> Bloqueo | None:
    """None si la petición puede ir al modelo; un Bloqueo si cruza la lista «nunca» o sale del alcance."""
    t = sin_tildes(texto or "").lower()
    for categoria, patron, motivo in REGLAS:
        if patron.search(t):
            return Bloqueo(categoria, motivo)
    # Fuera de alcance: verbo de acción activa + algún host que no está en el alcance declarado.
    if re.search(r"\b" + _ACCION_ACTIVA + r"\b", t):
        alcance = parsear_alcance(alcance_texto)
        fuera = [h for h in hosts_en(t) if not en_alcance(h, alcance)]
        if fuera:
            return Bloqueo("fuera_de_alcance",
                           f"{', '.join(fuera[:5])} no está en el alcance declarado de este engagement (G-1/G-3). "
                           "Si de verdad está autorizado, añádelo editando el alcance (pedirá confirmar de nuevo).",
                           hosts=fuera)
    return None
