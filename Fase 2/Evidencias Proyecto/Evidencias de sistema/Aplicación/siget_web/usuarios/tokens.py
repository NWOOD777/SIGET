"""Validación de tokens de acceso Auth0 para la API.

Comprueba firma RS256, emisor, audiencia y vigencia del token del cliente de
escritorio. La cuenta local y sus permisos se resuelven en usuarios.services.
"""

import logging
from typing import Any

import jwt
import requests
from django.conf import settings
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

ALGORITMOS_PERMITIDOS = ("RS256",)
CLAIMS_OBLIGATORIOS = ("exp", "iat", "iss", "aud", "sub")


class TokenAccesoError(Exception):
    """Excepción base para errores de validación de access tokens."""


class TokenExpiradoError(TokenAccesoError):
    """El access token superó su vigencia."""


class TokenInvalidoError(TokenAccesoError):
    """El access token es inválido (firma, emisor, audiencia, formato o tipo)."""


class ConfiguracionTokenError(TokenAccesoError):
    """La validación de access tokens no está configurada en el backend."""


class ProveedorIdentidadNoDisponibleError(TokenAccesoError):
    """No fue posible comunicarse con Auth0 (JWKS o userinfo)."""


_jwks_clientes: dict[str, PyJWKClient] = {}


def _obtener_cliente_jwks(url: str) -> PyJWKClient:
    """Retorna un cliente JWKS con caché de claves por URL de tenant."""
    cliente = _jwks_clientes.get(url)
    if cliente is None:
        cliente = PyJWKClient(
            url,
            cache_keys=True,
            lifespan=settings.AUTH0_JWKS_CACHE_SEGUNDOS,
            timeout=settings.AUTH0_HTTP_TIMEOUT,
        )
        _jwks_clientes[url] = cliente
    return cliente


def validacion_bearer_configurada() -> bool:
    return bool(settings.AUTH0_DOMAIN and settings.AUTH0_API_AUDIENCE)


def _verificar_configuracion() -> None:
    if not validacion_bearer_configurada():
        raise ConfiguracionTokenError(
            "La autenticación por access token no está configurada (AUTH0_API_AUDIENCE)."
        )
    audiencia = settings.AUTH0_API_AUDIENCE.rstrip("/")
    prohibidas = {
        settings.AUTH0_MGMT_AUDIENCE.rstrip("/"),
        f"https://{settings.AUTH0_DOMAIN}/api/v2",
        settings.AUTH0_CLIENT_ID,
    }
    if audiencia in prohibidas:
        raise ConfiguracionTokenError(
            "AUTH0_API_AUDIENCE debe ser el identificador de la API de SIGET, "
            "no la Management API ni el client_id."
        )


def validar_access_token(token: str) -> dict[str, Any]:
    """
    Valida un access token de Auth0 dirigido a la API de SIGET y retorna sus claims.

    Lanza TokenExpiradoError, TokenInvalidoError, ConfiguracionTokenError o
    ProveedorIdentidadNoDisponibleError. Nunca registra el token en los logs.
    """
    _verificar_configuracion()

    if not token or not isinstance(token, str):
        raise TokenInvalidoError("Token de acceso ausente.")

    try:
        encabezado = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise TokenInvalidoError("Formato de token de acceso inválido.") from exc

    if encabezado.get("alg") not in ALGORITMOS_PERMITIDOS:
        raise TokenInvalidoError("Algoritmo de firma no permitido.")
    if not encabezado.get("kid"):
        raise TokenInvalidoError("El token no identifica su clave de firma.")

    try:
        clave = _obtener_cliente_jwks(settings.AUTH0_JWKS_URL).get_signing_key_from_jwt(token)
    except jwt.PyJWKClientConnectionError as exc:
        logger.error("No fue posible obtener las claves JWKS de Auth0: %s", type(exc).__name__)
        raise ProveedorIdentidadNoDisponibleError(
            "El servicio de identidad no se encuentra disponible."
        ) from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalidoError("Clave de firma desconocida.") from exc

    try:
        claims = jwt.decode(
            token,
            clave.key,
            algorithms=list(ALGORITMOS_PERMITIDOS),
            audience=settings.AUTH0_API_AUDIENCE,
            issuer=settings.AUTH0_ISSUER,
            leeway=settings.AUTH0_TOKEN_LEEWAY,
            options={"require": list(CLAIMS_OBLIGATORIOS)},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiradoError("El token de acceso expiró.") from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalidoError("Token de acceso inválido.") from exc

    sub = str(claims.get("sub") or "").strip()
    if not sub:
        raise TokenInvalidoError("El token no identifica al usuario.")
    if claims.get("gty") == "client-credentials" or sub.endswith("@clients"):
        raise TokenInvalidoError("Los tokens de aplicación no representan a un usuario de SIGET.")

    permitidos = settings.AUTH0_API_ALLOWED_CLIENT_IDS
    if permitidos and claims.get("azp") not in permitidos:
        raise TokenInvalidoError("El token fue emitido para una aplicación no autorizada.")

    return claims


def obtener_perfil_userinfo(access_token: str) -> dict[str, Any]:
    """
    Consulta /userinfo de Auth0 con el access token ya validado.

    Solo se utiliza para la primera vinculación de una cuenta SIGET cuyo
    identificador externo aún no coincide con ``sub``. Auth0 entrega el correo
    y su verificación; SIGET no acepta esos datos desde el cliente.
    """
    try:
        respuesta = requests.get(
            f"https://{settings.AUTH0_DOMAIN}/userinfo",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=settings.AUTH0_HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.error("Error de red al consultar userinfo de Auth0: %s", type(exc).__name__)
        raise ProveedorIdentidadNoDisponibleError(
            "El servicio de identidad no se encuentra disponible."
        ) from exc

    if respuesta.status_code >= 500 or respuesta.status_code == 429:
        raise ProveedorIdentidadNoDisponibleError(
            "El servicio de identidad no se encuentra disponible."
        )
    if respuesta.status_code != 200:
        return {}
    try:
        datos = respuesta.json()
    except ValueError:
        return {}
    return datos if isinstance(datos, dict) else {}
