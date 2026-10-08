"""
Permisos y autorización RBAC para el módulo de activos tecnológicos de SIGET.
Valida la autorización directamente contra PostgreSQL mediante los servicios oficiales.
"""

from django.http import HttpRequest
from rest_framework import exceptions, permissions
from rest_framework.request import Request
from usuarios.models import Usuario
from usuarios.services import (
    ROL_TECNICO,
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
        cached = request._siget_usuario_cached
        if isinstance(cached, Usuario) or cached is None:
            return cached

    # DRF Request envuelve el HttpRequest de Django en request._request
    raw_req = getattr(request, "_request", request)
    if not isinstance(raw_req, HttpRequest):
        return None

    usuario = obtener_usuario_actual(raw_req)
    setattr(request, "_siget_usuario_cached", usuario)
    return usuario


class PuedeConsultarActivos(permissions.BasePermission):
    """
    Permite consultar activos y catálogos (GET) a usuarios autenticados
    con rol Técnico de soporte o Administrador del sistema en PostgreSQL,
    o que posean el permiso CATALOGO_CONSULTAR.
    """

    def has_permission(self, request, view):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "No autenticado. Inicie sesión para acceder a este recurso."
            )

        if (
            es_administrador(usuario)
            or usuario_tiene_rol(usuario, ROL_TECNICO)
            or usuario_tiene_permiso(usuario, "CATALOGO_CONSULTAR")
        ):
            return True

        raise exceptions.PermissionDenied(
            "Acceso no autorizado: Se requiere rol de soporte o administración para consultar activos."
        )


class PuedeAdministrarActivos(permissions.BasePermission):
    """
    Permite registrar (E2-H4) y modificar (E2-H5) activos exclusivamente
    a usuarios con rol 'Administrador del sistema' verificado en PostgreSQL.
    Rechaza peticiones de usuarios sin autenticar o sin privilegios administrativos,
    incluso si intentan manipular la sesión del cliente.
    """

    def has_permission(self, request, view):
        usuario = _obtener_usuario_siget(request)
        if not usuario:
            raise exceptions.NotAuthenticated(
                "No autenticado. Inicie sesión para acceder a este recurso."
            )

        if es_administrador(usuario):
            return True

        raise exceptions.PermissionDenied(
            "Acceso no autorizado: Se requieren privilegios de Administrador del sistema para registrar o modificar activos."
        )
