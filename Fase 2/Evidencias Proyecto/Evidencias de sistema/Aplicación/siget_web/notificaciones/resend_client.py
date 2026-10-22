"""Frontera HTTP: los errores nunca incluyen credenciales o el cuerpo remoto."""

from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class ErrorCorreo(Exception):
    def __init__(self, mensaje, *, transitorio=False, espera=0):
        super().__init__(mensaje)
        self.transitorio = transitorio
        self.espera = espera


def enviar_correo(datos, clave_idempotencia):
    clave = settings.RESEND_API_KEY
    if not clave or clave.startswith("REEMPLAZAR_"):
        raise ErrorCorreo("Falta configurar RESEND_API_KEY.")
    try:
        validate_email(parseaddr(datos["from"])[1])
        for destinatario in datos["to"]:
            validate_email(destinatario)
    except (KeyError, TypeError, ValidationError):
        raise ErrorCorreo("Remitente o destinatario inválido.") from None
    try:
        respuesta = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {clave}", "Idempotency-Key": clave_idempotencia},
            json=datos,
            timeout=settings.RESEND_TIMEOUT_SECONDS,
        )
    except (requests.Timeout, requests.ConnectionError):
        raise ErrorCorreo("Resend no respondió; resultado del intento indeterminado.", transitorio=True) from None
    except requests.RequestException:
        raise ErrorCorreo("No se pudo completar la solicitud a Resend.", transitorio=True) from None
    if respuesta.status_code >= 400:
        espera = 0
        try:
            espera = min(max(int(respuesta.headers.get("Retry-After", "0")), 0), 86400)
        except (ValueError, TypeError):
            pass
        raise ErrorCorreo(
            f"Resend respondió HTTP {respuesta.status_code}.",
            transitorio=respuesta.status_code in (409, 429) or respuesta.status_code >= 500,
            espera=espera,
        )
    try:
        identificador = respuesta.json()["id"]
        if not isinstance(identificador, str) or not identificador or len(identificador) > 100:
            raise ValueError
        return identificador
    except (ValueError, TypeError, KeyError):
        raise ErrorCorreo("Respuesta de Resend sin identificador válido; resultado indeterminado.", transitorio=True) from None
