nombre: Script Python
descripcion: CLI con argparse, logging y main() listo para ampliar
lenguaje: python
orden: 10
---
Escríbeme un script de Python que: <describe aquí qué debe hacer>
Respeta este andamiaje (argparse, logging, códigos de salida) y explícame cómo probarlo.

```python
#!/usr/bin/env python3
"""<nombre_del_script>: <qué hace en una línea>."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("entrada", type=Path, help="archivo o carpeta de entrada")
    p.add_argument("-n", "--dry-run", action="store_true", help="no cambia nada, solo muestra lo que haría")
    p.add_argument("-v", "--verbose", action="store_true", help="más detalle en el log")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    if not args.entrada.exists():
        log.error("No existe: %s", args.entrada)
        return 2
    # TODO: lógica principal
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
