"""
Permisos y autorización RBAC para el módulo de asignaciones y solicitudes de SIGET.
Valida la autorización directamente contra PostgreSQL mediante los servicios oficiales de usuarios.
"""
from django.http import HttpRequest
from rest_framework import exceptions, permissions
from rest_framework.request import Request

from usuarios.models import Usuario
from usuarios.services import (
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


class PuedeCrearSolicitudAsignacion(permissions.BasePermission):
    """
    Permite crear solicitudes de asignación a usuarios con rol
    'Usuario solicitante' validado en PostgreSQL.
    """

    def has_permission(self, request: Request, view) -> bool:
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "No autenticado. Inicie sesión para realizar una solicitud de asignación."
            )

        if (
            usuario_tiene_rol(usuario, ROL_USUARIO_SOLICITANTE)
        ):
            return True

        raise exceptions.PermissionDenied(
            "Acceso no autorizado: Se requiere rol de Usuario solicitante para registrar solicitudes."
        )


class PuedeResolverSolicitudAsignacion(permissions.BasePermission):
    """
    Permite aprobar o rechazar solicitudes de asignación exclusivamente
    a usuarios con rol 'Administrador del sistema' en PostgreSQL.
    """

    def has_permission(self, request: Request, view) -> bool:
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "No autenticado. Inicie sesión para gestionar solicitudes."
            )

        if (
            es_administrador(usuario)
        ):
            return True

        raise exceptions.PermissionDenied(
            "Acceso no autorizado: Se requieren privilegios de Administrador del sistema para resolver solicitudes."
        )


class PuedeConsultarSolicitudes(permissions.BasePermission):
    """
    Permite consultar solicitudes a usuarios autenticados.
    Los administradores y técnicos pueden ver todas; los solicitantes pueden consultar sus propias solicitudes.
    """

    def has_permission(self, request: Request, view) -> bool:
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "No autenticado. Inicie sesión para consultar solicitudes."
            )
        return True


class PuedeConsultarAsignaciones(permissions.BasePermission):
    """
    Permite consultar el listado y detalle de asignaciones.
    Habilitado para Administrador del sistema, Técnico de soporte,
    o solicitante consultando sus propias asignaciones.
    """

    def has_permission(self, request: Request, view) -> bool:
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "No autenticado. Inicie sesión para consultar asignaciones."
            )

        if (
            es_administrador(usuario)
            or usuario_tiene_rol(usuario, ROL_TECNICO)
            or usuario_tiene_rol(usuario, ROL_USUARIO_SOLICITANTE)
            or usuario_tiene_permiso(usuario, "CATALOGO_CONSULTAR")
        ):
            return True

        raise exceptions.PermissionDenied(
            "Acceso no autorizado: No cuenta con permisos para consultar asignaciones."
        )


class PuedeRegistrarEntrega(permissions.BasePermission):
    """
    Permite registrar la entrega física de un equipo a usuarios
    con rol 'Técnico de soporte' en PostgreSQL.
    """

    def has_permission(self, request: Request, view) -> bool:
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "No autenticado. Inicie sesión para registrar entregas."
            )

        if (
            usuario_tiene_rol(usuario, ROL_TECNICO)
        ):
            return True

        raise exceptions.PermissionDenied(
            "Acceso no autorizado: Se requiere rol de Técnico de soporte para registrar entregas de equipo."
        )


class PuedeRegistrarDevolucion(permissions.BasePermission):
    """
    Permite registrar la devolución y evaluación inicial del equipo
    a usuarios con rol 'Técnico de soporte' en PostgreSQL.
    """

    def has_permission(self, request: Request, view) -> bool:
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "No autenticado. Inicie sesión para registrar devoluciones."
            )

        if (
            usuario_tiene_rol(usuario, ROL_TECNICO)
        ):
            return True

        raise exceptions.PermissionDenied(
            "Acceso no autorizado: Se requiere rol de Técnico de soporte para registrar devoluciones de equipo."
        )
