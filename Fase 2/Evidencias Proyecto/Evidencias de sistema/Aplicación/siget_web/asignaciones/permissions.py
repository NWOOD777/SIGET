
from django.http import HttpRequest
from rest_framework import exceptions, permissions

from usuarios.services import ROL_TECNICO, obtener_usuario_actual, usuario_tiene_rol


class PuedeRegistrarDevolucion(permissions.BasePermission):
    """Permite registrar devoluciones únicamente a técnicos autenticados."""

    def has_permission(self, request, view):
        raw_request = getattr(request, "_request", request)

        if not isinstance(raw_request, HttpRequest):
            raise exceptions.NotAuthenticated(
                "No se pudo identificar la sesión del usuario."
            )

        usuario = obtener_usuario_actual(raw_request)

        if usuario is None:
            raise exceptions.NotAuthenticated(
                "Debe iniciar sesión para registrar una devolución."
            )

        if usuario_tiene_rol(usuario, ROL_TECNICO):
            return True

        raise exceptions.PermissionDenied(
            "Solo un Técnico de soporte puede registrar devoluciones."
        )
