"""
Pruebas de integración directa entre el cliente de escritorio y el backend Django en ejecución.
"""

import os
import unittest

import requests

from siget_desktop.api.client import ApiClient, ForbiddenApiError, TokenExpiredApiError
from siget_desktop.auth.session import current_session
from siget_desktop.config import config


class LiveBackendIntegrationTests(unittest.TestCase):
    """Comprueba la conectividad y respuestas reales del backend local Django."""

    @classmethod
    def setUpClass(cls):
        cls.backend_url = config.api_base_url
        try:
            resp = requests.get(f"{cls.backend_url}/", timeout=2)
            cls.backend_disponible = (resp.status_code in (200, 302, 403))
        except Exception:
            cls.backend_disponible = False

    def setUp(self):
        current_session.clear()
        self.client = ApiClient()

    def tearDown(self):
        current_session.clear()

    def test_backend_rechaza_me_sin_token(self):
        if not self.backend_disponible:
            self.skipTest("El contenedor backend Django no se encuentra en ejecución en localhost:8000.")

        # Sin token debe rechazar con 401 o 403
        with self.assertRaises((TokenExpiredApiError, ForbiddenApiError)):
            self.client.get("/api/usuarios/me/")

    def test_backend_rechaza_token_invalido(self):
        if not self.backend_disponible:
            self.skipTest("El contenedor backend Django no se encuentra en ejecución en localhost:8000.")

        current_session.set_tokens("token_ficticio_no_valido_en_auth0", expires_in=3600)
        with self.assertRaises(TokenExpiredApiError) as ctx:
            self.client.get("/api/usuarios/me/")
        self.assertEqual(ctx.exception.status_code, 401)


    @unittest.skipUnless(os.getenv("SIGET_TEST_ACCESS_TOKEN"), "Requiere token real de una cuenta de prueba autorizada.")
    def test_consulta_autenticada_me_y_activos(self):
        self.assertTrue(self.backend_disponible, "El backend debe estar disponible para esta prueba explícita.")
        current_session.set_tokens(os.environ["SIGET_TEST_ACCESS_TOKEN"], 3600)
        profile = self.client.get("/api/usuarios/me/")
        self.assertTrue(profile["acceso_escritorio"])
        self.assertIsInstance(self.client.get("/api/activos/"), list)


if __name__ == "__main__":
    unittest.main()
