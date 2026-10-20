"""Pruebas para el orquestador de autenticación OAuth 2.0 PKCE."""

import unittest
from unittest.mock import MagicMock, patch

from siget_desktop.auth.manager import (
    AuthCancelledError,
    AuthForbiddenError,
    AuthManager,
    AuthProviderError,
)
from siget_desktop.auth.pkce import PkceContext
from siget_desktop.auth.server import CallbackResult
from siget_desktop.auth.session import current_session
from siget_desktop.config import config


class AuthManagerTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        self.mock_opener = MagicMock(return_value=True)
        self.manager = AuthManager(browser_opener=self.mock_opener)
        self.config_patch = patch("siget_desktop.auth.manager.config", __import__("dataclasses").replace(config, auth0_domain="example.auth0.com", auth0_client_id="native-test", auth0_audience="https://api.siget.local"))
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def tearDown(self):
        current_session.clear()

    def test_construir_url_autorizacion_contiene_parametros_pkce(self):
        pkce = PkceContext(
            verifier="verifier_123",
            challenge="challenge_123",
            challenge_method="S256",
            state="state_xyz",
        )
        url = self.manager.construir_url_autorizacion(pkce)

        self.assertIn("response_type=code", url)
        self.assertIn("client_id=native-test", url)
        self.assertIn("code_challenge=challenge_123", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("state=state_xyz", url)
        self.assertIn("scope=openid+profile+email", url)
        self.assertIn(f"audience={config.auth0_audience}".replace(":", "%3A").replace("/", "%2F"), url)

    @patch("siget_desktop.auth.manager.esperar_retorno_oauth")
    def test_cancelacion_por_el_usuario_lanza_excepcion(self, mock_esperar):
        callback_res = CallbackResult()
        callback_res.code = None  # Usuario cerró o timeout
        mock_esperar.return_value = callback_res

        with self.assertRaises(AuthCancelledError):
            self.manager.iniciar_flujo_login(timeout_segundos=1)

    @patch("siget_desktop.auth.manager.esperar_retorno_oauth")
    def test_error_devuelto_por_auth0_lanza_excepcion(self, mock_esperar):
        callback_res = CallbackResult()
        callback_res.error = "access_denied"
        callback_res.error_description = "Usuario rechazó el consentimiento"
        mock_esperar.return_value = callback_res

        with self.assertRaises(AuthProviderError) as ctx:
            self.manager.iniciar_flujo_login(timeout_segundos=1)
        self.assertIn("Usuario rechazó el consentimiento", str(ctx.exception))

    @patch("siget_desktop.auth.manager.esperar_retorno_oauth")
    def test_mismatch_state_rechazado_por_seguridad(self, mock_esperar):
        callback_res = CallbackResult()
        callback_res.code = "code_valido"
        callback_res.state = "state_falsificado"
        mock_esperar.return_value = callback_res

        with self.assertRaises(AuthProviderError) as ctx:
            self.manager.iniciar_flujo_login(timeout_segundos=1)
        self.assertIn("state", str(ctx.exception).lower())

    @patch("siget_desktop.auth.manager.esperar_retorno_oauth")
    @patch.object(AuthManager, "_intercambiar_codigo")
    @patch.object(AuthManager, "_sincronizar_perfil_con_backend")
    def test_usuario_solicitante_sin_acceso_escritorio_rechazado(
        self, mock_sync, mock_intercambio, mock_esperar
    ):
        mock_intercambio.return_value = {
            "access_token": "token_solicitante_123",
            "expires_in": 3600,
        }
        # Backend responde con rol Solicitante (sin rol técnico ni admin)
        mock_sync.return_value = {
            "id_usuario": 40,
            "correo": "solicitante@siget.cl",
            "nombre_completo": "Juan Solicitante",
            "roles": ["Usuario solicitante"],
            "permisos": ["SOLICITUD_CREAR"],
            "acceso_escritorio": False,
        }

        # Simular que el callback devolvió el state correcto
        def _fake_esperar(port, timeout_segundos, **kwargs):
            res = CallbackResult()
            res.code = "code_ok"
            # Recuperar el state del último PkceContext creado
            res.state = self.manager._ultimo_state  # type: ignore
            return res

        # Interceptar construir_url para guardar state
        original_construir = self.manager.construir_url_autorizacion

        def _wrap_construir(pkce):
            self.manager._ultimo_state = pkce.state  # type: ignore
            return original_construir(pkce)

        self.manager.construir_url_autorizacion = _wrap_construir
        mock_esperar.side_effect = _fake_esperar

        with self.assertRaises(AuthForbiddenError) as ctx:
            self.manager.iniciar_flujo_login(timeout_segundos=1)
        self.assertIn("Técnico de soporte", str(ctx.exception))
        # Debe haberse limpiado la sesión
        self.assertFalse(current_session.is_authenticated())

    @patch("siget_desktop.auth.manager.esperar_retorno_oauth")
    @patch.object(AuthManager, "_intercambiar_codigo")
    @patch.object(AuthManager, "_sincronizar_perfil_con_backend")
    def test_login_exitoso_tecnico(
        self, mock_sync, mock_intercambio, mock_esperar
    ):
        mock_intercambio.return_value = {
            "access_token": "token_tecnico_abc",
            "expires_in": 7200,
            "id_token": "id_token_xyz",
        }
        mock_sync.return_value = {
            "id_usuario": 25,
            "correo": "tecnico@siget.cl",
            "nombre_completo": "Roberto Técnico",
            "roles": ["Técnico de soporte"],
            "permisos": ["CATALOGO_CONSULTAR", "TICKET_ATENDER"],
            "acceso_escritorio": True,
        }

        original_construir = self.manager.construir_url_autorizacion

        def _wrap_construir(pkce):
            self.manager._ultimo_state = pkce.state  # type: ignore
            return original_construir(pkce)

        self.manager.construir_url_autorizacion = _wrap_construir

        def _fake_esperar(port, timeout_segundos, **kwargs):
            res = CallbackResult()
            res.code = "code_ok"
            res.state = self.manager._ultimo_state  # type: ignore
            return res

        mock_esperar.side_effect = _fake_esperar

        info = self.manager.iniciar_flujo_login(timeout_segundos=1)
        self.assertEqual(info["id_usuario"], 25)
        self.assertTrue(current_session.is_authenticated())
        self.assertTrue(current_session.is_tecnico())
        self.assertFalse(current_session.is_admin())
        self.assertEqual(current_session.access_token, "token_tecnico_abc")


if __name__ == "__main__":
    unittest.main()
