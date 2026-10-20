"""
Servidor HTTP loopback temporal exclusivo para recibir el retorno OAuth 2.0 (callback).
Se ejecuta localmente en 127.0.0.1 por un tiempo limitado y se apaga de inmediato
tras recibir la respuesta o expirar el tiempo de espera. No almacena datos ni
constituye un servidor de negocio.
"""

from __future__ import annotations

import hmac
import logging
import time
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

HTML_EXITO = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>SIGET - Autenticación Exitosa</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0f172a; color: #f8fafc; display: flex; align-items: center;
               justify-content: center; height: 100vh; margin: 0; }
        .card { background: #1e293b; padding: 2.5rem; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                max-width: 480px; text-align: center; border: 1px solid #334155; }
        h1 { color: #38bdf8; font-size: 1.6rem; margin-top: 0; }
        p { color: #cbd5e1; font-size: 1rem; line-height: 1.5; }
        .badge { display: inline-block; background: #065f46; color: #6ee7b7; padding: 0.35rem 0.8rem;
                 border-radius: 9999px; font-weight: 600; font-size: 0.85rem; margin-bottom: 1rem; }
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">Respuesta recibida</div>
        <h1>Inicio de sesión en SIGET</h1>
        <p>La aplicación comprobará la respuesta y los permisos de su cuenta antes de permitir el acceso.</p>
        <p>Puede cerrar esta pestaña del navegador y volver a la <strong>Aplicación de Escritorio</strong>.</p>
    </div>
</body>
</html>
"""

HTML_ERROR = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>SIGET - Error de Autenticación</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0f172a; color: #f8fafc; display: flex; align-items: center;
               justify-content: center; height: 100vh; margin: 0; }
        .card { background: #1e293b; padding: 2.5rem; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                max-width: 480px; text-align: center; border: 1px solid #7f1d1d; }
        h1 { color: #f87171; font-size: 1.6rem; margin-top: 0; }
        p { color: #cbd5e1; font-size: 1rem; }
        .badge { display: inline-block; background: #991b1b; color: #fecaca; padding: 0.35rem 0.8rem;
                 border-radius: 9999px; font-weight: 600; font-size: 0.85rem; margin-bottom: 1rem; }
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">Inicio no completado</div>
        <h1>Acceso Cancelado o Rechazado</h1>
        <p>{error_description}</p>
        <p>Puede cerrar esta pestaña y regresar a la aplicación para reintentar.</p>
    </div>
</body>
</html>
"""


class CallbackResult:
    def __init__(self):
        self.code: str | None = None
        self.state: str | None = None
        self.error: str | None = None
        self.error_description: str | None = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Manejador HTTP para la única ruta /callback esperada."""

    def log_message(self, format, *args):
        # Suprimir logging ruidoso en consola para no exponer querystrings
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        params = parse_qs(parsed.query)
        server = self.server
        assert isinstance(server, OAuthLoopbackServer)
        expected = server.expected_state
        received = params.get("state", [""])[0]
        if expected and not hmac.compare_digest(expected, received):
            self.send_response(400)
            self.end_headers()
            return
        result: CallbackResult = server.callback_result

        if "error" in params:
            result.error = params["error"][0]
            result.error_description = params.get(
                "error_description", ["El inicio de sesión fue cancelado o denegado."]
            )[0]
            contenido = HTML_ERROR.replace(
                "{error_description}", escape(result.error_description)
            ).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(contenido)))
            self.end_headers()
            self.wfile.write(contenido)
        else:
            result.code = params.get("code", [None])[0]
            result.state = params.get("state", [None])[0]
            contenido = HTML_EXITO.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(contenido)))
            self.end_headers()
            self.wfile.write(contenido)

        # Notificar al servidor que se completó la recepción
        server.received = True


class OAuthLoopbackServer(HTTPServer):
    def __init__(self, host: str, port: int, expected_state: str = ""):
        super().__init__((host, port), OAuthCallbackHandler)
        self.callback_result = CallbackResult()
        self.expected_state = expected_state
        self.received = False


def esperar_retorno_oauth(port: int, timeout_segundos: int = 120, *,
                         on_ready=None, cancel_event=None, expected_state="") -> CallbackResult:
    """
    Inicia el servidor en 127.0.0.1:port y espera la redirección del navegador.
    Retorna el CallbackResult (con code o error) o timeout.
    """
    # Abrir el puerto antes del navegador. handle_request permite cancelar sin
    # terminar hilos de forma abrupta y garantiza liberar el socket.
    with OAuthLoopbackServer("127.0.0.1", port, expected_state) as server:
        server.timeout = 0.1
        if on_ready:
            on_ready()
        deadline = time.monotonic() + timeout_segundos
        while not server.received and time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                break
            server.handle_request()
        return server.callback_result
