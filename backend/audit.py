"""MOD-080 Auditoría: registro local de acciones sensibles (DB-008)."""
from __future__ import annotations

import json
from typing import Any

from .db import DB, ahora

TIPOS = {"cambio_alcance", "escalado_nube", "accion_seguridad_confirmada", "descarga_modelo", "export",
         "engagement", "guardarrail",
         "academia_laboratorio", "academia_enfoque", "lab_accion", "guardar_archivo", "proyecto",
         "verificador_instalar"}


def registrar(db: DB, tipo: str, detalle: dict[str, Any]) -> int:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de auditoría desconocido: {tipo}")
    return db.execute(
        "INSERT INTO audit_log(ts, tipo, detalle) VALUES (?, ?, ?)",
        (ahora(), tipo, json.dumps(detalle, ensure_ascii=False)),
    )
