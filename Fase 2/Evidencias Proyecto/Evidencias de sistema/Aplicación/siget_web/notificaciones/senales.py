"""Despierta al consumidor de la cola sin enviar correo desde la petición web."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

from django.db import connection
from psycopg import Connection

CANAL_CORREO_PENDIENTE = "siget_correo_pendiente"


def avisar_correo_pendiente() -> None:
    """Emitir después del commit; la señal no contiene datos del aviso ni del usuario."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_notify(%s, %s)", [CANAL_CORREO_PENDIENTE, ""])


@contextmanager
def escuchar_correos() -> Iterator[Connection]:
    """Conexión dedicada en autocommit: LISTEN antes de recuperar la cola persistida."""
    escucha = connection.copy(alias="correo_escucha")
    try:
        escucha.ensure_connection()
        escucha.set_autocommit(True)
        with escucha.cursor() as cursor:
            cursor.execute("LISTEN siget_correo_pendiente")
        yield cast(Connection, escucha.connection)
    finally:
        escucha.close()


def esperar_aviso(escucha: Connection, timeout: float) -> bool:
    """Espera hasta una señal o el siguiente barrido de respaldo, sin sondeo continuo."""
    return bool(list(escucha.notifies(timeout=max(0, timeout), stop_after=1)))
