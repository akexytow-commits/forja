"""MOD-060 Persistencia: acceso a SQLite y migraciones incrementales."""
from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import MIGRATIONS_DIR


def ahora() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


class DB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    # --- conexión -------------------------------------------------------
    def conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        return c

    def query(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        with closing(self.conn()) as c:
            return [dict(r) for r in c.execute(sql, params)]

    def one(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    @contextmanager
    def tx(self):
        """Varias escrituras en una sola transacción (y la conexión se cierra al salir)."""
        with closing(self.conn()) as c:
            with c:
                yield c

    def execute(self, sql: str, params: tuple | dict = ()) -> int:
        """Ejecuta una escritura en su propia transacción. Devuelve lastrowid."""
        with closing(self.conn()) as c:
            with c:
                cur = c.execute(sql, params)
                return cur.lastrowid

    # --- migraciones (TST-063) -------------------------------------------
    def schema_version(self) -> int:
        with closing(self.conn()) as c:
            c.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            c.commit()
            row = c.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return row[0] or 0

    def migrate(self) -> list[int]:
        current = self.schema_version()
        pending = []
        for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
            v = int(f.name.split("_", 1)[0])
            if v > current:
                pending.append((v, f))
        if not pending:
            return []
        if current > 0:
            # Nunca migrar datos del usuario sin copia del .db.
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(self.path, self.path.with_name(f"{self.path.name}.bak-v{current}-{stamp}"))
        applied = []
        for v, f in pending:
            sql = f.read_text(encoding="utf-8")
            with closing(self.conn()) as c:
                c.executescript(
                    f"BEGIN;\n{sql}\n;INSERT INTO schema_version(version) VALUES ({v});\nCOMMIT;"
                )
            applied.append(v)
        return applied

    # --- ajustes (DB-001) ------------------------------------------------
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, ahora()),
        )

    def settings(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in self.query("SELECT key, value FROM settings")}
