"""
Generación criptográfica de parámetros PKCE (Proof Key for Code Exchange)
conforme al estándar RFC 7636 para clientes nativos de escritorio.
"""

import base64
import hashlib
import secrets
from dataclasses import dataclass


def _base64url_encode(data: bytes) -> str:
    """Codifica bytes en base64url sin relleno '=' conforme a RFC 7636."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def generar_code_verifier(length: int = 64) -> str:
    """
    Genera una cadena aleatoria de alta entropía (43-128 caracteres)
    utilizando exclusivamente caracteres no reservados de RFC 7636.
    """
    if not (43 <= length <= 128):
        raise ValueError("El code_verifier debe tener entre 43 y 128 caracteres.")
    token = secrets.token_urlsafe(length)
    return token[:length]


def generar_code_challenge(verifier: str) -> str:
    """
    Calcula el code_challenge utilizando el método S256:
    code_challenge = BASE64URL-ENCODE(SHA256(ASCII(code_verifier)))
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return _base64url_encode(digest)


def generar_state(length: int = 32) -> str:
    """Genera un identificador opaco y criptográfico para prevención de CSRF."""
    return secrets.token_urlsafe(length)


@dataclass(frozen=True)
class PkceContext:
    """Contenedor de los parámetros generados para una solicitud de autorización."""

    verifier: str
    challenge: str
    challenge_method: str = "S256"
    state: str = ""

    @classmethod
    def create(cls) -> "PkceContext":
        verifier = generar_code_verifier()
        challenge = generar_code_challenge(verifier)
        state = generar_state()
        return cls(verifier=verifier, challenge=challenge, state=state)
