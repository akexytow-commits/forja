"""MOD-100 Estudio de Apariencia (20-estudio-apariencia.md, FR-073) — la paleta y el contraste, en un solo sitio.

La UI no calcula colores: pide aquí la paleta resultante (vista previa en vivo) y aquí se valida el contraste al
guardar (PUT /ajustes rechaza combinaciones ilegibles). Mínimos WCAG 2.x:
- texto sobre fondo y sobre superficie ≥ 4,5 (AA texto normal);
- texto secundario (muted) ≥ 3 (se deriva solo y se corrige si hiciera falta);
- acento sobre fondo ≥ 3 (componentes de interfaz, 1.4.11); la tinta sobre el acento se elige (negro/blanco).
"""
from __future__ import annotations

import json
import re
from typing import Any

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
MIN_TEXTO, MIN_SECUNDARIO, MIN_ACENTO = 4.5, 3.0, 3.0
MODOS = ("scripts", "seguridad", "tareas")
TEMAS = ("oscuro", "claro", "sistema", "contraste")
FUENTES = ("sistema", "mono", "serif", "redondeada", "humanista")
OPACIDAD_MIN, OPACIDAD_MAX = 0.05, 0.45

# Temas base (= ui/styles.css y ui/estudio.css). texto = --text-strong.
BASES: dict[str, dict[str, str]] = {
    "oscuro": {"bg": "#0d0d0e", "surface": "#151517", "texto": "#f1f1ee"},
    "claro": {"bg": "#e4e4e1", "surface": "#efefec", "texto": "#050505"},
    "contraste": {"bg": "#000000", "surface": "#0a0a0a", "texto": "#ffffff"},
}
# Acentos con nombre (= ui/rama5.css): versión para fondos oscuros y para fondos claros.
ACENTOS: dict[str, dict[str, str]] = {
    "naranja-forja": {"oscuro": "#e8701a", "claro": "#c2560b"},
    "ambar": {"oscuro": "#d9a21b", "claro": "#946800"},
    "verde": {"oscuro": "#3fa45b", "claro": "#237a3a"},
    "azul": {"oscuro": "#3d84e0", "claro": "#1f63bd"},
    "violeta": {"oscuro": "#8f64e0", "claro": "#6a3fc0"},
    "rojo": {"oscuro": "#d9483b", "claro": "#b0322a"},
}
LISO, DEGRADADO = {"tipo": "liso"}, {"tipo": "degradado"}
# BTN-095: presets (punto de partida; luego se retoca todo). "Fragua", "Medianoche" y "Papel" = con personalidad.
PRESETS: list[dict[str, Any]] = [
    {"id": "forja-oscuro", "nombre": "FORJA oscuro", "descripcion": "Negro y gris con naranja de fragua.",
     "ajustes": {"ui.tema": "oscuro", "ui.acento": "naranja-forja", "ui.base": "", "ui.fondo": LISO}},
    {"id": "forja-claro", "nombre": "FORJA claro", "descripcion": "Gris claro y negro, el mismo naranja.",
     "ajustes": {"ui.tema": "claro", "ui.acento": "naranja-forja", "ui.base": "", "ui.fondo": LISO}},
    {"id": "alto-contraste", "nombre": "Alto contraste", "descripcion": "Negro puro, texto blanco, acento amarillo.",
     "ajustes": {"ui.tema": "contraste", "ui.acento": "#ffd60a", "ui.base": "", "ui.fondo": LISO}},
    {"id": "fragua", "nombre": "Fragua", "descripcion": "Brasas sobre hierro: marrones cálidos y naranja vivo.",
     "ajustes": {"ui.tema": "oscuro", "ui.acento": "#ff7a1a", "ui.fondo": DEGRADADO,
                 "ui.base": {"bg": "#120c09", "surface": "#1c1410", "texto": "#f6e9df"}}},
    {"id": "medianoche", "nombre": "Medianoche", "descripcion": "Azul noche profundo con cian.",
     "ajustes": {"ui.tema": "oscuro", "ui.acento": "#38bdf8", "ui.fondo": DEGRADADO,
                 "ui.base": {"bg": "#0a0f1d", "surface": "#111a2e", "texto": "#e6ecf8"}}},
    {"id": "papel", "nombre": "Papel", "descripcion": "Crema cálido, tinta oscura y verde pino.",
     "ajustes": {"ui.tema": "claro", "ui.acento": "#2f6f5e", "ui.fondo": LISO,
                 "ui.base": {"bg": "#f3efe6", "surface": "#fbf8f1", "texto": "#1f1b16"}}},
]


class AparienciaError(ValueError):
    def __init__(self, codigo: str, mensaje: str, problemas: list[dict[str, Any]] | None = None):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.problemas = codigo, mensaje, problemas or []


# ---------------------------------------------------------------- color
def _rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _hex(c: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(x))):02x}" for x in c)


def mezcla(a: str, b: str, t: float) -> str:
    """a → b en proporción t (0 = a, 1 = b), en sRGB."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(x + (y - x) * t for x, y in zip(ra, rb, strict=False)))


def luminancia(h: str) -> float:
    def lin(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def es_oscuro(bg: str) -> bool:
    return luminancia(bg) < 0.18


def _alfa(h: str, a: float) -> str:
    r, g, b = _rgb(h)
    return f"rgba({r}, {g}, {b}, {a})"


# ---------------------------------------------------------------- estado
def _json(v: Any, defecto: Any) -> Any:
    if isinstance(v, (dict, list)):
        return v
    if not v:
        return defecto
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return defecto


def base_de(tema: str, base: Any) -> dict[str, str]:
    b = _json(base, {})
    t = "contraste" if tema == "contraste" else ("claro" if tema == "claro" else "oscuro")
    out = dict(BASES[t])
    if isinstance(b, dict) and all(HEX.match(str(b.get(k, ""))) for k in ("bg", "surface", "texto")):
        out = {k: b[k].lower() for k in ("bg", "surface", "texto")}
    return out


def color_acento(acento: str | None, oscuro: bool) -> str:
    acento = (acento or "naranja-forja").strip()
    if acento in ACENTOS:
        return ACENTOS[acento]["oscuro" if oscuro else "claro"]
    if HEX.match(acento):
        return acento.lower()
    return ACENTOS["naranja-forja"]["oscuro" if oscuro else "claro"]


def _vars_acento(acc: str, bg: str, oscuro: bool) -> dict[str, str]:
    tinta = "#000000" if contraste(acc, "#000000") >= contraste(acc, "#ffffff") else "#ffffff"
    hover = mezcla(acc, "#ffffff" if oscuro else "#000000", 0.14)
    return {"--accent": acc, "--accent-hover": hover, "--accent-ink": tinta,
            "--accent-soft": _alfa(acc, 0.14 if oscuro else 0.12), "--accent-line": _alfa(acc, 0.45)}


def paleta(estado: dict[str, Any], tema_efectivo: str | None = None) -> dict[str, Any]:
    """Variables CSS resultantes de un estado ui.* (lo que pinta la app y la vista previa)."""
    tema = estado.get("ui.tema") or "oscuro"
    if tema == "sistema":
        tema = tema_efectivo if tema_efectivo in ("oscuro", "claro") else "oscuro"
    b = base_de(tema, estado.get("ui.base"))
    bg, surface, texto = b["bg"], b["surface"], b["texto"]
    oscuro = es_oscuro(bg)
    muted = mezcla(texto, bg, 0.45)
    for t in (0.40, 0.35, 0.30, 0.25, 0.2):        # el secundario se aclara/oscurece hasta leerse (≥ 3)
        if contraste(muted, bg) >= MIN_SECUNDARIO:
            break
        muted = mezcla(texto, bg, t)
    v = {
        "--bg": bg, "--surface": surface,
        "--surface-2": mezcla(surface, texto, 0.06), "--surface-3": mezcla(surface, texto, 0.12),
        "--line": mezcla(surface, texto, 0.14), "--text-strong": texto, "--text": mezcla(texto, bg, 0.14),
        "--muted": muted,
    }
    acc = color_acento(estado.get("ui.acento"), oscuro)
    v.update(_vars_acento(acc, bg, oscuro))
    por_modo = {}
    for modo, a in (_json(estado.get("ui.acento_por_modo"), {}) or {}).items():
        if modo in MODOS and a:
            por_modo[modo] = _vars_acento(color_acento(a, oscuro), bg, oscuro)
    return {"variables": v, "por_modo": por_modo, "tema": tema, "familia": "oscuro" if oscuro else "claro",
            "contrastes": comprobaciones(v, por_modo), "problemas": problemas(v, por_modo)}


def comprobaciones(v: dict[str, str], por_modo: dict[str, dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Todas las parejas que se comprueban, con su ratio y si pasan (el Estudio enseña el informe entero)."""
    out = []

    def chk(par: str, a: str, b: str, minimo: float, donde: str = "") -> None:
        r = contraste(a, b)
        out.append({"par": par, "donde": donde, "ratio": r, "minimo": minimo, "ok": r >= minimo})

    chk("texto/fondo", v["--text-strong"], v["--bg"], MIN_TEXTO)
    chk("texto/superficie", v["--text-strong"], v["--surface"], MIN_TEXTO)
    chk("secundario/fondo", v["--muted"], v["--bg"], MIN_SECUNDARIO)
    chk("acento/fondo", v["--accent"], v["--bg"], MIN_ACENTO)
    for modo, av in (por_modo or {}).items():
        chk("acento/fondo", av["--accent"], v["--bg"], MIN_ACENTO, modo)
    return out


def problemas(v: dict[str, str], por_modo: dict[str, dict[str, str]] | None = None) -> list[dict[str, Any]]:
    return [{k: c[k] for k in ("par", "donde", "ratio", "minimo")} for c in comprobaciones(v, por_modo) if not c["ok"]]


# ---------------------------------------------------------------- validación de PUT /ajustes
CLAVES = {"ui.tema", "ui.acento", "ui.base", "ui.fondo", "ui.acento_por_modo", "ui.animacion", "ui.preset",
          "ui.tipografia", "ui.densidad"}


def normalizar(clave: str, valor: str) -> str:
    """Valida el formato de una clave de apariencia y devuelve el valor a guardar (JSON compacto)."""
    if clave == "ui.tema":
        if valor not in TEMAS:
            raise AparienciaError("AJUSTE_INVALIDO", f"'ui.tema' admite: {', '.join(TEMAS)}.")
    elif clave == "ui.tipografia":
        if valor not in FUENTES:
            raise AparienciaError("AJUSTE_INVALIDO", f"'ui.tipografia' admite: {', '.join(FUENTES)}.")
    elif clave == "ui.densidad":
        if valor not in ("comoda", "compacta"):
            raise AparienciaError("AJUSTE_INVALIDO", "'ui.densidad' admite: comoda, compacta.")
    elif clave == "ui.acento":
        if valor not in ACENTOS and not HEX.match(valor):
            raise AparienciaError("AJUSTE_INVALIDO", "El acento es un color con nombre o un #rrggbb.")
        return valor.lower()
    elif clave == "ui.animacion":
        if valor not in ("0", "1"):
            raise AparienciaError("AJUSTE_INVALIDO", "'ui.animacion' admite: 0, 1.")
    elif clave == "ui.preset":
        if valor and valor not in {p["id"] for p in PRESETS}:
            raise AparienciaError("AJUSTE_INVALIDO", "Preset desconocido.")
    elif clave == "ui.base":
        if not valor:
            return ""
        b = _json(valor, None)
        if not (isinstance(b, dict) and set(b) == {"bg", "surface", "texto"} and all(HEX.match(str(x)) for x in b.values())):
            raise AparienciaError("AJUSTE_INVALIDO", "Colores base: {bg, surface, texto} como #rrggbb.")
        return json.dumps({k: b[k].lower() for k in ("bg", "surface", "texto")}, separators=(",", ":"))
    elif clave == "ui.acento_por_modo":
        m = _json(valor or "{}", None)
        if not isinstance(m, dict) or not set(m) <= set(MODOS) or \
                any(x and x not in ACENTOS and not HEX.match(str(x)) for x in m.values()):
            raise AparienciaError("AJUSTE_INVALIDO", "Acento por modo: {scripts|seguridad|tareas: color}.")
        return json.dumps({k: v.lower() for k, v in m.items() if v}, separators=(",", ":"))
    elif clave == "ui.fondo":
        f = _json(valor, None)
        if not isinstance(f, dict) or f.get("tipo") not in ("liso", "degradado", "imagen"):
            raise AparienciaError("AJUSTE_INVALIDO", "Fondo: {tipo: liso | degradado | imagen}.")
        if f["tipo"] != "imagen":
            return json.dumps({"tipo": f["tipo"]}, separators=(",", ":"))
        archivo = str(f.get("archivo", ""))
        if not re.fullmatch(r"[0-9a-f]{16}\.(png|jpg|webp|gif)", archivo):
            raise AparienciaError("AJUSTE_INVALIDO", "Fondo: sube primero la imagen.")
        try:
            op = float(f.get("opacidad", 0.2))
        except (TypeError, ValueError):
            raise AparienciaError("AJUSTE_INVALIDO", "Fondo: opacidad numérica.") from None
        op = round(min(OPACIDAD_MAX, max(OPACIDAD_MIN, op)), 2)      # nunca tan opaca que reste legibilidad
        return json.dumps({"tipo": "imagen", "archivo": archivo, "opacidad": op}, separators=(",", ":"))
    return valor


def validar_contraste(estado: dict[str, Any]) -> None:
    """Rechaza un estado ilegible. Con «seguir el sistema» se comprueban las dos variantes."""
    temas = ("oscuro", "claro") if estado.get("ui.tema") == "sistema" else (None,)
    todos = []
    for t in temas:
        for p in paleta(estado, t)["problemas"]:
            todos.append({**p, **({"tema": t} if t else {})})
    if todos:
        p = todos[0]
        donde = f" (modo {p['donde']})" if p.get("donde") else ""
        raise AparienciaError("CONTRASTE_INSUFICIENTE",
                              f"Contraste insuficiente en {p['par']}{donde}: {p['ratio']}:1, mínimo {p['minimo']}:1.",
                              todos)


# ---------------------------------------------------------------- imagen de fondo (BTN-098)
FIRMAS = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpg", b"GIF87a": "gif", b"GIF89a": "gif"}
MAX_IMAGEN = 8 * 1024 * 1024


def tipo_imagen(datos: bytes) -> str | None:
    for firma, ext in FIRMAS.items():
        if datos.startswith(firma):
            return ext
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "webp"
    return None
