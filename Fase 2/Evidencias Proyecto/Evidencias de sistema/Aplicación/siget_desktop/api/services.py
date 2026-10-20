"""
Servicios de alto nivel que consumen las APIs REST existentes de SIGET.
No contienen lógica de persistencia ni acceden directamente a la base de datos.
"""

from __future__ import annotations

from typing import Any

from siget_desktop.api.client import api_client


def obtener_perfil_actual() -> dict[str, Any]:
    """Consulta la identidad, roles y permisos efectivos del usuario actual."""
    return api_client.get("/api/usuarios/me/")


def listar_activos(
    search: str | None = None,
    tipo: str | None = None,
    ubicacion: str | None = None,
    estado: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta el inventario de activos TI aplicando filtros."""
    params: dict[str, Any] = {}
    if search:
        params["search"] = search
    if tipo:
        params["tipo"] = tipo
    if ubicacion:
        params["ubicacion"] = ubicacion
    if estado:
        params["estado"] = estado
    resultado = api_client.get("/api/activos/", params=params)
    return resultado if isinstance(resultado, list) else []


def listar_categorias_activos() -> list[dict[str, Any]]:
    """Consulta el catálogo de categorías de activos TI."""
    resultado = api_client.get("/api/activos/categorias/")
    return resultado if isinstance(resultado, list) else []


def listar_solicitudes(
    estado: str | None = None,
    categoria: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta las solicitudes de asignación en el alcance del usuario."""
    params: dict[str, Any] = {}
    if estado:
        params["estado"] = estado
    if categoria:
        params["categoria"] = categoria
    if search:
        params["search"] = search
    resultado = api_client.get("/api/solicitudes-asignacion/", params=params)
    return resultado if isinstance(resultado, list) else []


def listar_asignaciones(
    estado: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta asignaciones de equipos."""
    params: dict[str, Any] = {}
    if estado:
        params["estado"] = estado
    if search:
        params["search"] = search
    resultado = api_client.get("/api/asignaciones/", params=params)
    return resultado if isinstance(resultado, list) else []


def listar_tickets(
    estado: str | None = None,
    prioridad: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta tickets de soporte dentro del alcance del usuario."""
    params: dict[str, Any] = {}
    if estado:
        params["estado"] = estado
    if prioridad:
        params["prioridad"] = prioridad
    if search:
        params["search"] = search
    resultado = api_client.get("/api/tickets/", params=params)
    return resultado if isinstance(resultado, list) else []


def listar_usuarios_rbac() -> list[dict[str, Any]]:
    """Consulta administrativa de usuarios y roles RBAC (exclusivo Administrador)."""
    resultado = api_client.get("/api/usuarios/")
    return resultado if isinstance(resultado, list) else []
