"""Configuración pública del escritorio desde el .env común de Aplicación."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
PUBLIC_KEYS = frozenset({
    "SIGET_PUBLIC_URL", "SIGET_HTTP_TIMEOUT", "AUTH0_DOMAIN",
    "AUTH0_API_AUDIENCE", "AUTH0_DESKTOP_CLIENT_ID", "AUTH0_DESKTOP_CALLBACK_PORT",
})


def _leer_configuracion_publica(path: Path = ENV_PATH) -> dict[str, str]:
    values = dotenv_values(path, interpolate=False) if path.is_file() else {}
    return {key: value for key, value in values.items() if key in PUBLIC_KEYS and value is not None}


_ENV_LOCAL = _leer_configuracion_publica()


def _valor(key: str, default: str = "") -> str:
    return os.environ.get(key, _ENV_LOCAL.get(key, default))


@dataclass(frozen=True)
class DesktopConfig:
    app_name: str = "SIGET - Sistema Integral de Gestión de Equipos y Soporte Tecnológico"
    app_version: str = "1.0.0"
    api_base_url: str = field(default_factory=lambda: _valor("SIGET_PUBLIC_URL", "http://localhost:8000").rstrip("/"))
    http_timeout: int = field(default_factory=lambda: int(_valor("SIGET_HTTP_TIMEOUT", "10")))
    auth0_domain: str = field(default_factory=lambda: _valor("AUTH0_DOMAIN"))
    auth0_client_id: str = field(default_factory=lambda: _valor("AUTH0_DESKTOP_CLIENT_ID"))
    auth0_audience: str = field(default_factory=lambda: _valor("AUTH0_API_AUDIENCE"))
    auth0_callback_port: int = field(default_factory=lambda: int(_valor("AUTH0_DESKTOP_CALLBACK_PORT", "42813")))

    @property
    def auth0_issuer(self) -> str:
        return f"https://{self.auth0_domain}/"

    @property
    def auth0_authorize_url(self) -> str:
        return f"https://{self.auth0_domain}/authorize"

    @property
    def auth0_token_url(self) -> str:
        return f"https://{self.auth0_domain}/oauth/token"

    @property
    def auth0_redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.auth0_callback_port}/callback"


config = DesktopConfig()
