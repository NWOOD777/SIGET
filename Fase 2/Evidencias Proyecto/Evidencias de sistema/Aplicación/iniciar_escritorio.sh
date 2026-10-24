#!/bin/sh
# Inicia el cliente local desde cualquier directorio.
set -eu

APP_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$APP_DIR"

if [ -x "../../../../.venv/bin/python" ]; then
    REPO_DIR=$(CDPATH='' cd -- "../../../.." && pwd)
    PYTHON_EXE="$REPO_DIR/.venv/bin/python"
elif [ -x ".venv/bin/python" ]; then
    PYTHON_EXE="$APP_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_EXE="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_EXE="python"
else
    echo "No se encontró Python. Instala Python 3.12 o superior y prepara el entorno virtual." >&2
    exit 1
fi

if ! "$PYTHON_EXE" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "SIGET Escritorio requiere Python 3.12 o superior." >&2
    exit 1
fi

if ! "$PYTHON_EXE" -c 'from PySide6.QtWidgets import QApplication; import requests, jwt, dotenv'; then
    echo "No fue posible cargar las dependencias del escritorio." >&2
    echo "Activa el entorno virtual e instala requirements.txt; consulta README.md." >&2
    exit 1
fi

exec "$PYTHON_EXE" -m siget_desktop.main "$@"
