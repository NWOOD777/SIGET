"""
Orquestador de autenticación OAuth 2.0 / PKCE para la aplicación de escritorio.
Coordina el inicio en navegador, la recepción de código, el intercambio de tokens
y la sincronización de la sesión con el backend Django (/api/usuarios/me/).
"""

from __future__ import annotations

import logging
import urllib.parse
import webbrowser
from typing import Callable

import requests

from siget_desktop.auth.pkce import PkceContext
from siget_desktop.auth.server import CallbackResult, esperar_retorno_oauth
from siget_desktop.auth.session import current_session
from siget_desktop.config import config

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Excepción base para errores del flujo de autenticación."""


class AuthCancelledError(AuthError):
    """El usuario canceló el inicio de sesión o cerró el navegador."""


class AuthProviderError(AuthError):
    """Auth0 retornó un error explícito o falló el intercambio de código."""


class AuthForbiddenError(AuthError):
    """El usuario no posee permisos de escritorio o su cuenta está inactiva."""


class AuthManager:
    """Administra el ciclo de vida de la autenticación de escritorio."""

    def __init__(self, browser_opener: Callable[[str], bool] | None = None):
        self._browser_opener = browser_opener or webbrowser.open

    def construir_url_autorizacion(self, pkce: PkceContext) -> str:
        """Construye la URL para iniciar el flujo en Auth0."""
        params = {
            "response_type": "code",
            "client_id": config.auth0_client_id,
            "redirect_uri": config.auth0_redirect_uri,
            "scope": "openid profile email",
            "audience": config.auth0_audience,
            "code_challenge": pkce.challenge,
            "code_challenge_method": pkce.challenge_method,
            "state": pkce.state,
        }
        return f"{config.auth0_authorize_url}?{urllib.parse.urlencode(params)}"

    def iniciar_flujo_login(
        self,
        on_browser_opened: Callable[[], None] | None = None,
        timeout_segundos: int = 120,
        cancel_event=None,
    ) -> dict:
        """
        Ejecuta el flujo completo de inicio de sesión PKCE:
        1. Genera code_verifier y code_challenge.
        2. Abre la URL en el navegador del sistema.
        3. Espera el callback en el servidor loopback local.
        4. Intercambia el código por tokens en Auth0.
        5. Valida la identidad y roles en el backend Django.
        """
        current_session.clear()
        if not all((config.auth0_domain, config.auth0_client_id, config.auth0_audience)):
            raise AuthProviderError("Complete AUTH0_DOMAIN, AUTH0_DESKTOP_CLIENT_ID y AUTH0_API_AUDIENCE en el .env común.")
        pkce = PkceContext.create()
        authorize_url = self.construir_url_autorizacion(pkce)

        logger.info("Abriendo navegador para autenticación: %s", config.auth0_domain)
        def abrir_navegador():
            if not self._browser_opener(authorize_url):
                raise AuthProviderError("No fue posible abrir el navegador del sistema.")
            if on_browser_opened:
                on_browser_opened()

        # Esperar retorno en el loopback
        callback_res: CallbackResult = esperar_retorno_oauth(
            port=config.auth0_callback_port,
            timeout_segundos=timeout_segundos,
            on_ready=abrir_navegador,
            cancel_event=cancel_event,
            expected_state=pkce.state,
        )

        if callback_res.error:
            raise AuthProviderError(
                f"Error devuelto por Auth0: {callback_res.error_description or callback_res.error}"
            )

        if not callback_res.code:
            raise AuthCancelledError(
                "No se recibió respuesta de autenticación. El proceso fue cancelado o expiró."
            )

        if callback_res.state != pkce.state:
            raise AuthProviderError(
                "El parámetro 'state' recibido no coincide con el enviado. Posible respuesta corrupta."
            )

        # Intercambiar código por tokens
        tokens = self._intercambiar_codigo(callback_res.code, pkce.verifier)
        access_token = tokens.get("access_token")
        if not access_token:
            raise AuthProviderError("Auth0 no devolvió un access_token válido.")

        expires_in = int(tokens.get("expires_in", 3600))
        id_token = tokens.get("id_token")

        # No almacenar credenciales hasta que Django autorice la cuenta.
        user_info = self._sincronizar_perfil_con_backend(access_token)
        if cancel_event is not None and cancel_event.is_set():
            raise AuthCancelledError("Inicio de sesión cancelado.")
        if not user_info.get("acceso_escritorio"):
            raise AuthForbiddenError("Acceso exclusivo para Técnico de soporte o Administrador del sistema.")
        current_session.set_tokens(
            access_token=access_token,
            expires_in=expires_in,
            id_token=id_token,
        )

        # Validar identidad, roles y permisos efectivos en Django
        current_session.update_user_info(user_info)

        if not current_session.acceso_escritorio:
            current_session.clear()
            raise AuthForbiddenError(
                "Acceso no autorizado: Su cuenta no cuenta con rol de Técnico de soporte "
                "ni Administrador del sistema para operar la aplicación de Escritorio."
            )

        return user_info

    def _intercambiar_codigo(self, code: str, code_verifier: str) -> dict:
        """Realiza POST /oauth/token con PKCE verifier."""
        payload = {
            "grant_type": "authorization_code",
            "client_id": config.auth0_client_id,
            "code_verifier": code_verifier,
            "code": code,
            "redirect_uri": config.auth0_redirect_uri,
        }
        try:
            resp = requests.post(
                config.auth0_token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=config.http_timeout,
            )
        except requests.RequestException as exc:
            raise AuthProviderError(
                f"No fue posible comunicarse con el servicio de tokens de Auth0: {exc}"
            ) from exc

        if resp.status_code != 200:
            detalle = resp.text
            try:
                data = resp.json()
                detalle = data.get("error_description") or data.get("error") or detalle
            except Exception:
                pass
            raise AuthProviderError(f"Fallo al canjear código en Auth0 ({resp.status_code}): {detalle}")

        return resp.json()

    def _sincronizar_perfil_con_backend(self, access_token: str) -> dict:
        """Consulta /api/usuarios/me/ en Django para verificar la cuenta y permisos."""
        url = f"{config.api_base_url}/api/usuarios/me/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=config.http_timeout)
        except requests.RequestException as exc:
            raise AuthProviderError(
                f"No fue posible conectar con el backend Django en {config.api_base_url}: {exc}"
            ) from exc

        if resp.status_code == 401:
            raise AuthProviderError("El token de acceso fue rechazado por el backend Django.")
        if resp.status_code == 403:
            raise AuthForbiddenError(
                "Su cuenta no tiene acceso a SIGET o se encuentra inactiva. "
                "Contacte al administrador del sistema."
            )
        if resp.status_code != 200:
            raise AuthProviderError(
                f"Respuesta inesperada del backend Django ({resp.status_code}): {resp.text}"
            )

        return resp.json()

    def cerrar_sesion(self, abrir_logout_auth0: bool = False):
        """Limpia las credenciales locales de la sesión."""
        current_session.clear()
        if abrir_logout_auth0:
            params = {
                "client_id": config.auth0_client_id,
                "returnTo": "http://127.0.0.1",
            }
            logout_url = f"https://{config.auth0_domain}/v2/logout?{urllib.parse.urlencode(params)}"
            try:
                self._browser_opener(logout_url)
            except Exception:
                pass


auth_manager = AuthManager()
