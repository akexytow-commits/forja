"""P1 (17-patrones-planificador.md, copia de Todoist): captura en lenguaje natural.

Capa 1 — reglas locales: fechas relativas (hoy, mañana, pasado mañana, lunes…, en 3 días, la semana que
viene, el finde, 25/12, 25 de diciembre), hora (17:00, a las 5, 9am), prioridad (!!!, !!, !, urgente,
importante, p1…p5) y duración (30 min, 1h, 1h30, 2 horas).
Capa 2 — si queda una referencia temporal que las reglas no entienden ("a final de mes", "por la tarde"),
`ambigua()` lo señala para que el backend pregunte al modelo Pequeño.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

DIAS_SEMANA = {
    "lunes": 0, "lun": 0, "martes": 1, "miercoles": 2, "mie": 2, "jueves": 3, "jue": 3,
    "viernes": 4, "vie": 4, "sabado": 5, "sab": 5, "domingo": 6, "dom": 6,
}
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "ene": 1, "feb": 2, "abr": 4, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}
NUMEROS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
           "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}
PRIORIDAD_DEFECTO = 3

_A = str.maketrans("áéíóúüÁÉÍÓÚÜ", "aeiouuAEIOUU")
_N = r"(\d{1,2}|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)"
_PREP = r"(?:(?:para|el|la|este|esta|antes\s+del?|hasta\s+el)\s+)?"
_VINETA = re.compile(r"^\s*(?:[-*•·]+|\d{1,2}[.)]|\[\s?[xX ]?\s?\])\s*")

# Señales de fecha que las reglas no resuelven → capa 2 (modelo Pequeño).
_AMBIGUAS = re.compile(
    r"\b(final(?:es)? de(?:l)? mes|fin de mes|principios de|mediados de|proximo mes|mes que viene|"
    r"quincena|por la (?:manana|tarde|noche)|esta (?:tarde|noche)|luego|pronto|cuanto antes|"
    r"despues de (?:comer|cenar|clase|trabajar))\b")


def sin_tildes(s: str) -> str:
    return s.translate(_A).replace("ñ", "n").replace("Ñ", "N")


def _num(tok: str) -> int:
    return int(tok) if tok.isdigit() else NUMEROS[tok]


def _proximo(hoy: date, dia_semana: int) -> date:
    delta = (dia_semana - hoy.weekday()) % 7
    return hoy + timedelta(days=delta or 7)


class _Lector:
    """Busca patrones sobre el texto sin tildes y los recorta del texto original (mismas posiciones)."""

    def __init__(self, texto: str):
        self.orig = texto
        self.norm = sin_tildes(texto).lower()

    def tomar(self, patron: str) -> re.Match | None:
        m = re.search(patron, self.norm)
        if m:
            a, b = m.span()
            self.orig = self.orig[:a] + " " + self.orig[b:]
            self.norm = self.norm[:a] + " " + self.norm[b:]
        return m


def interpretar(linea: str, hoy: date) -> dict[str, Any]:
    """Devuelve {texto, dia_asignado, hora, prioridad, estimacion_min, detectado:[...]}."""
    linea = _VINETA.sub("", _VINETA.sub("", linea.strip()))
    lec = _Lector(linea)
    res: dict[str, Any] = {"dia_asignado": None, "hora": None, "prioridad": PRIORIDAD_DEFECTO,
                           "estimacion_min": None, "detectado": []}

    # Prioridad
    if lec.tomar(r"!!!|\burgente\b|\bp1\b"):
        res["prioridad"] = 1
    elif lec.tomar(r"!!|\bimportante\b|\bp2\b"):
        res["prioridad"] = 2
    elif m := lec.tomar(r"\bp([345])\b"):
        res["prioridad"] = int(m.group(1))
    elif lec.tomar(r"(?<!\S)!(?!\S)"):
        res["prioridad"] = 2
    elif lec.tomar(r"\b(?:cuando pueda|algun dia|sin prisa)\b"):
        res["prioridad"] = 5
    if res["prioridad"] != PRIORIDAD_DEFECTO:
        res["detectado"].append("prioridad")

    # "17h" / "9 h" (9–23) es una hora, no una duración.
    if m := lec.tomar(r"\b(?:a las?\s+)?(9|1\d|2[0-3])\s*h\b(?!\s*\d)"):
        res["hora"] = f"{int(m.group(1)):02d}:00"

    # Duración: "1h30", "1 h 30 min", "90 min", "2 horas", "media hora", "(45m)"
    if m := lec.tomar(r"\(?\b(\d{1,2})\s*h(?:oras?)?\s*(\d{1,2})\s*(?:m|min|minutos)?\b\)?"):
        res["estimacion_min"] = int(m.group(1)) * 60 + int(m.group(2))
    elif m := lec.tomar(r"\(?\b(\d{1,3})\s*(?:m|min|mins|minutos)\b\)?"):
        res["estimacion_min"] = int(m.group(1))
    elif m := lec.tomar(r"\(?\b" + _N + r"\s*(?:h|hrs?|horas?)\b\)?"):
        res["estimacion_min"] = _num(m.group(1)) * 60
    elif lec.tomar(r"\bmedia hora\b"):
        res["estimacion_min"] = 30
    if res["estimacion_min"] is not None:
        res["estimacion_min"] = max(5, min(res["estimacion_min"], 1440))
        res["detectado"].append("duracion")

    # Hora: "17:00", "a las 5", "a las 5 de la tarde", "9am", "9 pm"
    if res["hora"]:
        pass
    elif m := lec.tomar(r"\b(?:a las?\s+)?([01]?\d|2[0-3])[:.]([0-5]\d)\s*(?:h\b)?"):
        res["hora"] = f"{int(m.group(1)):02d}:{m.group(2)}"
    elif m := lec.tomar(r"\b([01]?\d)\s*(am|pm)\b"):
        h = int(m.group(1)) % 12 + (12 if m.group(2) == "pm" else 0)
        res["hora"] = f"{h:02d}:00"
    elif m := lec.tomar(r"\ba las?\s+([01]?\d|2[0-3])(?:\s+de la\s+(manana|tarde|noche))?\b"):
        h = int(m.group(1))
        if m.group(2) in ("tarde", "noche") and h < 12:
            h += 12
        res["hora"] = f"{h:02d}:00"
    if res["hora"]:
        res["detectado"].append("hora")

    # Fecha
    dia: date | None = None
    if lec.tomar(_PREP + r"\bpasado\s+manana\b"):
        dia = hoy + timedelta(days=2)
    elif lec.tomar(_PREP + r"\bmanana\b"):
        dia = hoy + timedelta(days=1)
    elif lec.tomar(_PREP + r"\b(?:hoy|esta\s+manana)\b"):
        dia = hoy
    elif m := lec.tomar(r"\b(?:en|dentro\s+de)\s+" + _N + r"\s+dias?\b"):
        dia = hoy + timedelta(days=_num(m.group(1)))
    elif m := lec.tomar(r"\b(?:en|dentro\s+de)\s+" + _N + r"\s+semanas?\b"):
        dia = hoy + timedelta(days=7 * _num(m.group(1)))
    elif lec.tomar(_PREP + r"\b(?:la\s+)?(?:semana\s+que\s+viene|proxima\s+semana)\b"):
        dia = hoy + timedelta(days=(7 - hoy.weekday()))  # lunes siguiente
    elif lec.tomar(_PREP + r"\b(?:el\s+)?(?:finde|fin\s+de\s+semana)\b"):
        dia = hoy if hoy.weekday() == 5 else _proximo(hoy, 5)
    elif m := lec.tomar(_PREP + r"\b(?:proximo\s+|el\s+)?(lunes|martes|miercoles|jueves|viernes|sabado|domingo"
                        r"|lun|mie|jue|vie|sab|dom)\b(?:\s+que\s+viene)?"):
        dia = _proximo(hoy, DIAS_SEMANA[m.group(1)])
    elif m := lec.tomar(r"\b(\d{4})-(\d{2})-(\d{2})\b"):
        dia = _fecha(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    elif m := lec.tomar(r"\b(?:el\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b"):
        anio = int(m.group(3)) if m.group(3) else None
        anio = anio + 2000 if anio is not None and anio < 100 else anio
        dia = _fecha_futura(hoy, int(m.group(1)), int(m.group(2)), anio)
    elif m := lec.tomar(r"\b(?:el\s+)?(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")\b(?:\s+(?:de\s+)?(\d{4}))?"):
        dia = _fecha_futura(hoy, int(m.group(1)), MESES[m.group(2)], int(m.group(3)) if m.group(3) else None)
    if dia:
        res["dia_asignado"] = dia.isoformat()
        res["detectado"].append("fecha")

    texto = re.sub(r"(?<!\S)[¡!]+(?!\S)", " ", lec.orig)  # restos de "¡urgente!"
    texto = re.sub(r"\s{2,}", " ", texto).strip(" ,;:-")
    texto = re.sub(r"\s+([,.;:])", r"\1", texto)
    res["texto"] = texto or linea
    res["ambigua"] = bool(_AMBIGUAS.search(lec.norm))
    return res


def _fecha(a: int, m: int, d: int) -> date | None:
    try:
        return date(a, m, d)
    except ValueError:
        return None


def _fecha_futura(hoy: date, d: int, m: int, anio: int | None) -> date | None:
    if anio:
        return _fecha(anio, m, d)
    f = _fecha(hoy.year, m, d)
    if f and f < hoy:
        f = _fecha(hoy.year + 1, m, d)
    return f


def partir(texto: str) -> list[str]:
    """Texto libre → líneas de tarea. Una por línea; si es una sola línea con ';', se parte por ahí."""
    lineas = [l for l in (x.strip() for x in texto.splitlines()) if l]
    if len(lineas) == 1 and ";" in lineas[0]:
        lineas = [p.strip() for p in lineas[0].split(";") if p.strip()]
    return lineas


def sangria(linea_cruda: str) -> int:
    """Nivel de anidado por sangría (2 espacios o 1 tabulador por nivel), estilo outliner (P4)."""
    m = re.match(r"^([ \t]*)", linea_cruda)
    s = m.group(1).replace("\t", "  ") if m else ""
    return len(s) // 2
