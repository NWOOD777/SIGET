"""Pruebas unitarias para el cliente HTTP/REST centralizado del escritorio."""

import unittest
from unittest.mock import MagicMock, patch

import requests

from siget_desktop.api.client import (
    ApiClient,
    ConnectionApiError,
    ForbiddenApiError,
    NotFoundApiError,
    ServerApiError,
    TokenExpiredApiError,
    ValidationApiError,
)
from siget_desktop.auth.session import current_session


class ApiClientTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        self.client = ApiClient(base_url="http://testserver:8000", timeout=5)

    def tearDown(self):
        current_session.clear()

    @patch("requests.Session.request")
    def test_inyecta_bearer_token_si_hay_sesion(self, mock_request):
        current_session.set_tokens("test_token_123", expires_in=3600)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": 1}]
        mock_request.return_value = mock_resp

        self.client.get("/api/activos/")

        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        headers = kwargs.get("headers", {})
        self.assertEqual(headers.get("Authorization"), "Bearer test_token_123")
        self.assertEqual(headers.get("Accept"), "application/json")

    @patch("requests.Session.request")
    def test_sin_token_no_envia_authorization(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_request.return_value = mock_resp

        self.client.get("/api/tickets/sla/")

        headers = mock_request.call_args[1].get("headers", {})
        self.assertNotIn("Authorization", headers)

    @patch("requests.Session.request")
    def test_error_401_token_expirado(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"detail": "Su acceso expiró.", "codigo": "token_expirado"}
        mock_request.return_value = mock_resp

        with self.assertRaises(TokenExpiredApiError) as ctx:
            self.client.get("/api/usuarios/me/")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.codigo, "token_expirado")

    @patch("requests.Session.request")
    def test_error_403_permiso_denegado(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.json.return_value = {"detail": "Acceso no autorizado: Se requieren privilegios de Administrador."}
        mock_request.return_value = mock_resp

        with self.assertRaises(ForbiddenApiError) as ctx:
            self.client.get("/api/usuarios/")
        self.assertEqual(ctx.exception.status_code, 403)

    @patch("requests.Session.request")
    def test_error_404_no_encontrado(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"detail": "Activo no encontrado."}
        mock_request.return_value = mock_resp

        with self.assertRaises(NotFoundApiError):
            self.client.get("/api/activos/9999/")

    @patch("requests.Session.request")
    def test_error_400_o_409_validacion(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.json.return_value = {"detail": "Conflicto de negocio."}
        mock_request.return_value = mock_resp

        with self.assertRaises(ValidationApiError) as ctx:
            self.client.post("/api/solicitudes-asignacion/", json={"id_categoria": 1})
        self.assertEqual(ctx.exception.status_code, 409)

    @patch("requests.Session.request")
    def test_error_500_servidor(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.json.return_value = {"detail": "Bad Gateway"}
        mock_request.return_value = mock_resp

        with self.assertRaises(ServerApiError) as ctx:
            self.client.get("/api/activos/")
        self.assertEqual(ctx.exception.status_code, 502)

    @patch("requests.Session.request")
    def test_timeout_conexion(self, mock_request):
        mock_request.side_effect = requests.Timeout("Timeout agotado")

        with self.assertRaises(ConnectionApiError):
            self.client.get("/api/activos/")

    @patch("requests.Session.request")
    def test_fallo_red_desconexion(self, mock_request):
        mock_request.side_effect = requests.ConnectionError("Connection refused")

        with self.assertRaises(ConnectionApiError) as ctx:
            self.client.get("/api/activos/")
        self.assertIn("No fue posible establecer conexión", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
