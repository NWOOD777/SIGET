"""
Cliente HTTP/REST centralizado para la aplicación de escritorio PySide6.
Encapsula la URL base, cabeceras de autorización Bearer, control de timeouts,
parseo consistente de respuestas JSON y categorización estricta de errores HTTP.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from siget_desktop.auth.session import current_session
from siget_desktop.config import config

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Excepción base para errores de comunicación con la API de SIGET."""

    def __init__(self, mensaje: str, status_code: int | None = None, codigo: str | None = None, payload: Any = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status_code = status_code
        self.codigo = codigo
        self.payload = payload


class ConnectionApiError(ApiError):
    """Fallo de red o timeout al conectar con el servidor backend."""


class TokenExpiredApiError(ApiError):
    """El access token expiró o fue revocado por el servidor."""


class ForbiddenApiError(ApiError):
    """El usuario no posee permisos suficientes para ejecutar la acción solicitada."""


class NotFoundApiError(ApiError):
    """El recurso solicitado no fue encontrado en el servidor."""


class ValidationApiError(ApiError):
    """Datos de entrada inválidos o conflicto de negocio (400 / 409)."""


class ServerApiError(ApiError):
    """Fallo interno o de servicio en el servidor (500 / 502 / 503)."""


class ApiClient:
    """
    Cliente REST centralizado que inyecta automáticamente el token de la sesión activa
    y gestiona errores de manera uniforme.
    """

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        self.base_url = (base_url or config.api_base_url).rstrip("/")
        self.timeout = timeout or config.http_timeout
        self._session = requests.Session()

    def _preparar_cabeceras(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        cabeceras = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if current_session.access_token:
            if current_session.is_expired():
                current_session.clear()
                raise TokenExpiredApiError("Su sesión expiró. Inicie sesión nuevamente.", status_code=401)
            cabeceras["Authorization"] = f"Bearer {current_session.access_token}"
        if headers:
            cabeceras.update(headers)
        return cabeceras

    def _procesar_respuesta(self, resp: requests.Response) -> Any:
        # Extraer JSON o texto
        datos = None
        try:
            datos = resp.json()
        except ValueError:
            datos = resp.text

        codigo_error = None
        mensaje_error = None
        if isinstance(datos, dict):
            codigo_error = datos.get("codigo")
            mensaje_error = datos.get("detail") or datos.get("error") or datos.get("mensaje")
        elif isinstance(datos, str) and datos:
            mensaje_error = datos

        if 200 <= resp.status_code < 300:
            return datos

        # Mapeo estructurado por código de estado
        if resp.status_code == 401:
            if codigo_error == "token_expirado" or "expiró" in str(mensaje_error).lower():
                raise TokenExpiredApiError(
                    mensaje_error or "Su sesión ha expirado. Por favor inicie sesión nuevamente.",
                    status_code=401,
                    codigo=codigo_error,
                    payload=datos,
                )
            raise TokenExpiredApiError(
                mensaje_error or "Credencial de acceso inválida o no reconocida.",
                status_code=401,
                codigo=codigo_error,
                payload=datos,
            )

        if resp.status_code == 403:
            raise ForbiddenApiError(
                mensaje_error or "Acceso denegado: No posee los permisos requeridos para esta operación.",
                status_code=403,
                codigo=codigo_error,
                payload=datos,
            )

        if resp.status_code == 404:
            raise NotFoundApiError(
                mensaje_error or "El registro o recurso solicitado no fue encontrado.",
                status_code=404,
                codigo=codigo_error,
                payload=datos,
            )

        if resp.status_code in (400, 409):
            raise ValidationApiError(
                mensaje_error or "Los datos enviados contienen errores o entran en conflicto.",
                status_code=resp.status_code,
                codigo=codigo_error,
                payload=datos,
            )

        if resp.status_code >= 500:
            raise ServerApiError(
                mensaje_error or f"El servidor respondió con un error ({resp.status_code}). Intente nuevamente más tarde.",
                status_code=resp.status_code,
                codigo=codigo_error,
                payload=datos,
            )

        raise ApiError(
            mensaje_error or f"Error HTTP inesperado ({resp.status_code}).",
            status_code=resp.status_code,
            codigo=codigo_error,
            payload=datos,
        )

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """
        Ejecuta una petición HTTP centralizada.
        Las operaciones de escritura (POST/PUT/PATCH/DELETE) NO se reintentan automáticamente
        para evitar duplicaciones accidentales.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        cabeceras = self._preparar_cabeceras(headers)
        generation = current_session.generation

        try:
            resp = self._session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json,
                headers=cabeceras,
                timeout=self.timeout,
            )
            cuenta_inactiva = False
            if resp.status_code == 403:
                try:
                    data = resp.json()
                    cuenta_inactiva = isinstance(data, dict) and data.get("codigo") == "cuenta_sin_acceso"
                except ValueError:
                    pass
            if (resp.status_code == 401 or cuenta_inactiva) and generation == current_session.generation:
                current_session.clear()
            return self._procesar_respuesta(resp)
        except requests.Timeout as exc:
            raise ConnectionApiError(
                f"Tiempo de espera agotado al conectar con el servidor ({self.timeout}s).",
                payload=str(exc),
            ) from exc
        except requests.ConnectionError as exc:
            raise ConnectionApiError(
                f"No fue posible establecer conexión con el backend SIGET en {self.base_url}. "
                "Verifique que el servicio esté en ejecución.",
                payload=str(exc),
            ) from exc
        except requests.RequestException as exc:
            raise ConnectionApiError(
                f"Error en la comunicación de red: {exc}",
                payload=str(exc),
            ) from exc

    def get(self, path: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        return self.request("GET", path, params=params, headers=headers)

    def post(self, path: str, json: Any = None, headers: dict[str, str] | None = None) -> Any:
        return self.request("POST", path, json=json, headers=headers)

    def put(self, path: str, json: Any = None, headers: dict[str, str] | None = None) -> Any:
        return self.request("PUT", path, json=json, headers=headers)

    def patch(self, path: str, json: Any = None, headers: dict[str, str] | None = None) -> Any:
        return self.request("PATCH", path, json=json, headers=headers)

    def delete(self, path: str, headers: dict[str, str] | None = None) -> Any:
        return self.request("DELETE", path, headers=headers)


api_client = ApiClient()
