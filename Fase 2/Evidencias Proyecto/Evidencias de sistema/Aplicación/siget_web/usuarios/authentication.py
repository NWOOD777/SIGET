"""Autenticación DRF de SIGET: sesión Web con CSRF y access token Bearer para clientes nativos."""
from rest_framework import exceptions
from rest_framework.authentication import (
    BaseAuthentication,
    SessionAuthentication,
    get_authorization_header,
)

from usuarios.services import (
    ATRIBUTO_USUARIO_BEARER,
    AuthServiceError,
    obtener_usuario_actual,
    resolver_usuario_access_token,
)
from usuarios.tokens import (
    ConfiguracionTokenError,
    ProveedorIdentidadNoDisponibleError,
    TokenExpiradoError,
    TokenInvalidoError,
    validar_access_token,
)

REALM = "siget-api"


class SigetSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        usuario = obtener_usuario_actual(request._request)
        if usuario is None:
            return None
        self.enforce_csrf(request)
        request._siget_usuario_cached = usuario
        return usuario, None


class ServicioIdentidadNoDisponible(exceptions.APIException):
    status_code = 503
    default_detail = "El servicio de identidad no se encuentra disponible. Intente nuevamente."
    default_code = "identidad_no_disponible"


class SigetAccessTokenAuthentication(BaseAuthentication):
    """
    Autentica peticiones con ``Authorization: Bearer <access_token>`` emitido por Auth0
    para la audiencia de la API de SIGET (aplicación de Escritorio).

    - Sin encabezado Bearer retorna None y DRF continúa con la sesión Web.
    - Un Bearer inválido o vencido responde 401 (no se intenta la sesión).
    - Una identidad válida sin cuenta SIGET activa o vinculada responde 403.
    - El usuario resuelto queda disponible para obtener_usuario_actual(), de modo
      que los permisos y servicios existentes lo reconocen igual que a la sesión.
    - No usa cookies, por lo que no requiere CSRF.
    """

    keyword = b"bearer"

    def authenticate(self, request):
        partes = get_authorization_header(request).split()
        if not partes or partes[0].lower() != self.keyword:
            return None

        if len(partes) != 2:
            self._fallar(request, "Encabezado Authorization inválido.", "token_invalido")
        try:
            token = partes[1].decode("ascii")
        except UnicodeError:
            self._fallar(request, "Encabezado Authorization inválido.", "token_invalido")

        try:
            claims = validar_access_token(token)
        except TokenExpiradoError:
            self._fallar(request, "Su acceso expiró. Inicie sesión nuevamente.", "token_expirado")
        except TokenInvalidoError:
            self._fallar(request, "Credencial de acceso inválida.", "token_invalido")
        except ConfiguracionTokenError:
            self._fallar(
                request,
                "La autenticación de la aplicación de Escritorio no está habilitada en el servidor.",
                "token_no_configurado",
            )
        except ProveedorIdentidadNoDisponibleError:
            raise ServicioIdentidadNoDisponible()

        try:
            usuario = resolver_usuario_access_token(claims, token)
        except ProveedorIdentidadNoDisponibleError:
            raise ServicioIdentidadNoDisponible()
        except AuthServiceError as exc:
            raise exceptions.PermissionDenied(str(exc), code="cuenta_sin_acceso")

        setattr(request._request, ATRIBUTO_USUARIO_BEARER, usuario)
        request._siget_usuario_cached = usuario
        request._siget_metodo_autenticacion = "bearer"
        return usuario, claims

    def _fallar(self, request, mensaje: str, codigo: str):
        request._siget_bearer_error = "invalid_token"
        raise exceptions.AuthenticationFailed(mensaje, code=codigo)

    def authenticate_header(self, request):
        # Solo se anuncia el esquema Bearer a quien lo utilizó. Las peticiones de
        # la sesión Web mantienen la respuesta 403 vigente para accesos sin sesión.
        partes = get_authorization_header(request).split()
        if not partes or partes[0].lower() != self.keyword:
            return None
        error = getattr(request, "_siget_bearer_error", None)
        if error:
            return f'Bearer realm="{REALM}", error="{error}"'
        return f'Bearer realm="{REALM}"'
