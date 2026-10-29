
from rest_framework import exceptions, permissions

from tickets.permissions import _obtener_usuario_siget
from usuarios.services import ROL_TECNICO, usuario_tiene_permiso, usuario_tiene_rol


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


class PuedeCompletarOrdenTrabajo(PuedeGestionarOrdenesTrabajo):
    """Permiso específico del cierre; no amplía ni altera las otras operaciones."""

    def has_permission(self, request, view):
        super().has_permission(request, view)
        usuario = _obtener_usuario_siget(request)
        if all(usuario_tiene_permiso(usuario, codigo) for codigo in ("OT_GESTIONAR", "TICKET_ATENDER")):
            return True
        raise exceptions.PermissionDenied("Se requieren los permisos OT_GESTIONAR y TICKET_ATENDER.")
