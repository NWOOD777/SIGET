
from rest_framework import exceptions, permissions

from tickets.permissions import _obtener_usuario_siget
from usuarios.services import ROL_TECNICO, usuario_tiene_rol


class PuedeGestionarOrdenesTrabajo(permissions.BasePermission):
    def has_permission(self, request, view):
        usuario = _obtener_usuario_siget(request)

        if not usuario:
            raise exceptions.NotAuthenticated(
                "Debe iniciar sesión para gestionar órdenes de trabajo."
            )

        if usuario_tiene_rol(usuario, ROL_TECNICO):
            return True

        raise exceptions.PermissionDenied(
            "Solo el Técnico de soporte puede gestionar órdenes de trabajo."
        )
