"""
Permisos y autorización RBAC para el módulo Service Desk y Tickets de SIGET.
Valida la autorización directamente contra PostgreSQL.
"""
from django.http import HttpRequest
from rest_framework import exceptions, permissions
from rest_framework.request import Request
from usuarios.models import Usuario
from usuarios.services import (
    ROL_ADMINISTRADOR,
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
    es_administrador,
    obtener_usuario_actual,
    usuario_tiene_permiso,
    usuario_tiene_rol,
)


def _obtener_usuario_siget(request: Request) -> Usuario | None:
    """
    Obtiene el usuario autenticado consultando PostgreSQL mediante la sesión actual.
    Guarda en cache la instancia dentro del request para evitar múltiples consultas.
    """
    if hasattr(request, "_siget_usuario_cached"):
        cached = getattr(request, "_siget_usuario_cached")
        if isinstance(cached, Usuario) or cached is None:
            return cached

    raw_req = getattr(request, "_request", request)
    if not isinstance(raw_req, HttpRequest):
        return None

    usuario = obtener_usuario_actual(raw_req)
    setattr(request, "_siget_usuario_cached", usuario)
    return usuario


class PuedeCrearTicket(permissions.BasePermission):
    """
    Permite crear tickets de soporte (E5-H13) a usuarios autenticados con rol
    'Usuario solicitante', 'Técnico de soporte', o 'Administrador del sistema' (o permiso TICKET_CREAR).
    """

    def has_permission(self, request: Request, view) -> bool:
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "No autenticado. Inicie sesión para registrar un ticket de soporte."
            )

        if (
            usuario_tiene_rol(usuario, ROL_USUARIO_SOLICITANTE)
            or usuario_tiene_rol(usuario, ROL_TECNICO)
            or es_administrador(usuario)
            or usuario_tiene_permiso(usuario, "TICKET_CREAR")
        ):
            return True

        raise exceptions.PermissionDenied(
            "Acceso no autorizado: No cuenta con permisos para crear tickets de soporte."
        )


class PuedeConsultarTickets(permissions.BasePermission):
    """
    Permite consultar tickets de soporte a usuarios autenticados.
    Los usuarios solicitantes pueden consultar sus propios tickets;
    administradores y técnicos pueden consultar todos los tickets.
    """

    def has_permission(self, request: Request, view) -> bool:
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "No autenticado. Inicie sesión para consultar tickets de soporte."
            )
        return True
