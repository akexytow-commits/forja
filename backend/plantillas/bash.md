nombre: Script Bash
descripcion: modo estricto, ayuda, opciones con getopts y limpieza con trap
lenguaje: bash
orden: 20
---
Escríbeme un script de Bash que: <describe aquí qué debe hacer>
Respeta este andamiaje (modo estricto, getopts, trap) y explícame cómo probarlo.

```bash
#!/usr/bin/env bash
# <nombre_del_script>: <qué hace en una línea>
set -Eeuo pipefail
IFS=$'\n\t'

usage() {
  cat <<USO
Uso: $(basename "$0") [-n] [-v] <entrada>
  -n  simulación (no cambia nada)
  -v  modo detallado
USO
}

DRY_RUN=0
VERBOSE=0
while getopts ":nvh" opt; do
  case "$opt" in
    n) DRY_RUN=1 ;;
    v) VERBOSE=1 ;;
    h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))
[[ $# -ge 1 ]] || { usage >&2; exit 2; }

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

log() { [[ $VERBOSE -eq 1 ]] && echo "[*] $*" >&2 || true; }

main() {
  local entrada="$1"
  log "entrada: $entrada (dry-run=$DRY_RUN)"
  # TODO: lógica principal
}

main "$@"
```
