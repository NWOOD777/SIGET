"""Bloqueos transaccionales de PostgreSQL sin agregar tablas de dominio."""
from django.db import connection


def bloquear_operacion(dominio: int, identificador: int = 0) -> None:
    """Serializa operaciones relacionadas hasta commit/rollback (requiere atomic)."""
    if not connection.in_atomic_block:
        raise RuntimeError("El bloqueo requiere una transacción activa.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [dominio, identificador])


def transaccion_operacion(func):
    """Agrupa validaciones, bloqueos y escrituras en una sola transacción."""
    from functools import wraps
    from django.db import transaction

    @wraps(func)
    def ejecutar(*args, **kwargs):
        with transaction.atomic():
            return func(*args, **kwargs)
    return ejecutar


def siguiente_codigo(tabla: str, prefijo: str) -> str:
    consultas = {
        "activo": "SELECT COALESCE(MAX(substring(codigo_inventario FROM '^ACT-([0-9]+)$')::bigint), 0) + 1 FROM activo",
        "ticket": "SELECT COALESCE(MAX(substring(codigo_ticket FROM '^TCK-([0-9]+)$')::bigint), 0) + 1 FROM ticket",
    }
    with connection.cursor() as cursor:
        cursor.execute(consultas[tabla])
        siguiente = cursor.fetchone()[0]
    return f"{prefijo}-{siguiente:04d}"
