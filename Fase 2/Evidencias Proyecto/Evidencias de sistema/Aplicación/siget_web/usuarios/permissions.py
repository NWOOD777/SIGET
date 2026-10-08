"""
Permisos DRF para control de acceso RBAC en el módulo de usuarios.
PostgreSQL es la fuente autoritativa de roles y permisos.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from usuarios.services import (
    es_administrador,
    obtener_usuario_actual,
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
