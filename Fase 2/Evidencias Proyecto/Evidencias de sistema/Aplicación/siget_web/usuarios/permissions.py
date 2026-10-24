"""
Permisos DRF para control de acceso RBAC en el módulo de usuarios.
PostgreSQL es la fuente autoritativa de roles y permisos.
"""
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from usuarios.services import (
    es_administrador,
    obtener_usuario_actual,
    usuario_tiene_permiso,
)


class PuedeAdministrarUsuarios(BasePermission):
    """
    Permiso DRF que exige el rol canónico 'Administrador del sistema'
    validado directamente contra los registros en PostgreSQL.
    Rechaza usuarios no autenticados o con roles no privilegiados,
    incluso si intentan manipular datos en la sesión HTTP.
    """

    def has_permission(self, request: Request, view):
        # request._request proporciona el HttpRequest subyacente de Django
        from django.http import HttpRequest
        django_request = request._request
        assert isinstance(django_request, HttpRequest)
        usuario = obtener_usuario_actual(django_request)
        if not usuario:
            raise PermissionDenied(
                "Debe iniciar sesión para realizar esta operación."
            )
        if not es_administrador(usuario):
            raise PermissionDenied(
                "Acceso no autorizado: Se requieren privilegios de Administrador del sistema."
            )
        return True


class EsUsuarioSigetAutenticado(BasePermission):
    """
    Exige un Usuario SIGET activo, autenticado por sesión Web o por access token.
    No exige rol: cada usuario solo consulta su propia información.
    """

    def has_permission(self, request: Request, view):
        from rest_framework.exceptions import NotAuthenticated

        if not obtener_usuario_actual(request._request):
            raise NotAuthenticated("Debe iniciar sesión para realizar esta operación.")
        return True


class PuedeConsultarAuditoria(BasePermission):
    """
    Permiso DRF que restringe la consulta de la bitácora de auditoría
    exclusivamente a usuarios activos con rol 'Administrador del sistema'
    y permiso 'AUDITORIA_CONSULTAR', verificados autoritativamente contra PostgreSQL.
    Rechaza solicitudes anónimas, usuarios inactivos y roles no autorizados (Técnico, Solicitante).
    """

    def has_permission(self, request: Request, view):
        from django.http import HttpRequest
        django_request = getattr(request, "_request", request)
        if not isinstance(django_request, HttpRequest):
            raise NotAuthenticated("Debe iniciar sesión para realizar esta operación.")

        usuario = getattr(request, "_siget_usuario_cached", None)
        if not usuario:
            usuario = obtener_usuario_actual(django_request)
            if usuario:
                setattr(request, "_siget_usuario_cached", usuario)

        if not usuario:
            raise NotAuthenticated("Debe iniciar sesión para consultar la bitácora de auditoría.")

        if not usuario.activo:
            raise PermissionDenied("La cuenta de usuario se encuentra inactiva.")

        if not es_administrador(usuario):
            raise PermissionDenied(
                "Acceso no autorizado: Se requieren privilegios de Administrador del sistema."
            )

        if not usuario_tiene_permiso(usuario, "AUDITORIA_CONSULTAR"):
            raise PermissionDenied(
                "Acceso no autorizado: Se requiere el permiso AUDITORIA_CONSULTAR."
            )

        return True
