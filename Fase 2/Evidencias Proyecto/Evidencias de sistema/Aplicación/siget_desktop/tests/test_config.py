"""Pruebas unitarias de configuración del cliente de escritorio SIGET."""

import os
import unittest
from unittest.mock import patch

from siget_desktop.config import DesktopConfig


class DesktopConfigTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"AUTH0_DOMAIN":"example.auth0.com", "AUTH0_DESKTOP_CLIENT_ID":"native-test", "AUTH0_API_AUDIENCE":"https://api.siget.local", "SIGET_HTTP_TIMEOUT":"10", "AUTH0_DESKTOP_CALLBACK_PORT":"42813"})
        env.start()
        self.addCleanup(env.stop)

    def test_valores_predeterminados(self):
        cfg = DesktopConfig()
        self.assertTrue(cfg.api_base_url.startswith("http"))
        self.assertFalse(cfg.api_base_url.endswith("/"))
        self.assertEqual(cfg.http_timeout, 10)
        self.assertIn("auth0.com", cfg.auth0_domain)
        self.assertTrue(bool(cfg.auth0_client_id))
        self.assertEqual(cfg.auth0_audience, "https://api.siget.local")
        self.assertEqual(cfg.auth0_callback_port, 42813)

    def test_propiedades_auth0(self):
        cfg = DesktopConfig(auth0_domain="test.auth0.com", auth0_callback_port=9999)
        self.assertEqual(cfg.auth0_issuer, "https://test.auth0.com/")
        self.assertEqual(cfg.auth0_authorize_url, "https://test.auth0.com/authorize")
        self.assertEqual(cfg.auth0_token_url, "https://test.auth0.com/oauth/token")
        self.assertEqual(cfg.auth0_redirect_uri, "http://127.0.0.1:9999/callback")


if __name__ == "__main__":
    unittest.main()
