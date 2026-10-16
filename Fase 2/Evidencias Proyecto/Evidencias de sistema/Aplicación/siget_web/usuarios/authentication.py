"""Autenticación de sesiones SIGET para DRF, con CSRF obligatorio."""
from rest_framework.authentication import SessionAuthentication
from usuarios.services import obtener_usuario_actual


class SigetSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        usuario = obtener_usuario_actual(request._request)
        if usuario is None:
            return None
        self.enforce_csrf(request)
        request._siget_usuario_cached = usuario
        return usuario, None
