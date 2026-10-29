from rest_framework import exceptions, permissions

from tickets.permissions import _obtener_usuario_siget
from usuarios.services import ROL_TECNICO, es_administrador, usuario_tiene_rol


class PuedeConsultarCatalogoRepuestos(permissions.BasePermission):
    """
    Permite consultar el catálogo de repuestos a administradores
    y técnicos de soporte autenticados.
    """

    def has_permission(self, request, view):
        usuario = _obtener_usuario_siget(request)

        if usuario is None:
            raise exceptions.NotAuthenticated("Debe iniciar sesión para consultar repuestos.")

        if es_administrador(usuario) or usuario_tiene_rol(usuario, ROL_TECNICO):
            return True

        raise exceptions.PermissionDenied("Solo administradores y técnicos de soporte pueden consultar repuestos.")
