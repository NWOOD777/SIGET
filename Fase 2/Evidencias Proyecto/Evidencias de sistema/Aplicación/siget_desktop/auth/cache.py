"""Caché privada del token de acceso, separada por entorno y sin permisos locales."""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from siget_desktop.auth.session import current_session
from siget_desktop.config import config


def ruta_cache() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    return Path(base) / "sesion" / "acceso.json"


def entorno() -> str:
    values = [config.api_base_url, config.auth0_domain, config.auth0_client_id, config.auth0_audience]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def eliminar_cache():
    try:
        ruta_cache().unlink(missing_ok=True)
    except OSError:
        pass


def guardar_cache() -> bool:
    if not current_session.is_authenticated() or not current_session.acceso_escritorio:
        eliminar_cache()
        return False
    path = ruta_cache()
    temp = None
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        fd, temp = tempfile.mkstemp(prefix=".acceso-", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"entorno": entorno(), "access_token": current_session.access_token,
                       "expires_at": current_session.expires_at}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        return True
    except OSError:
        return False
    finally:
        if temp:
            Path(temp).unlink(missing_ok=True)


def leer_cache() -> tuple[str, float] | None:
    path = ruta_cache()
    try:
        if path.is_symlink() or path.stat().st_size > 65536:
            eliminar_cache()
            return None
        if os.name == "posix" and (path.stat().st_mode & 0o077 or path.parent.stat().st_mode & 0o077):
            eliminar_cache()
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        token, expiry = data["access_token"], float(data["expires_at"])
        if data["entorno"] != entorno() or not isinstance(token, str) or not token or not math.isfinite(expiry) or expiry <= time.time() + 30:
            eliminar_cache()
            return None
        return token, expiry
    except (OSError, ValueError, TypeError, KeyError):
        eliminar_cache()
        return None
