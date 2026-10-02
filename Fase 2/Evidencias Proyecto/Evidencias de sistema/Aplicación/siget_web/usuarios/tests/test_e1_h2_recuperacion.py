"""
Pruebas unitarias para E1-H2: Recuperación de acceso mediante Auth0.
"""

from unittest.mock import MagicMock, patch
import requests

from django.conf import settings
from django.test import Client, SimpleTestCase
from django.urls import reverse

from usuarios.models import Usuario, UsuarioRol


class RecuperarAccesoTests(SimpleTestCase):
    """
    Pruebas unitarias para E1-H2: Recuperar acceso.
    """

    def setUp(self):
        self.recover_url = reverse(
            "usuarios:auth_recover"
        )
        self.correo_valido = (
            "c.valenzuela@duocuc.cl"
        )

    def test_01_get_auth_recover_responde_correctamente(self):
        """
        1. GET /auth/recover/ responde correctamente.
        """
        response = self.client.get(
            self.recover_url
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertTemplateUsed(
            response,
            "usuarios/recover.html",
        )

        content = response.content.decode(
            "utf-8"
        )

        self.assertIn(
            'name="correo"',
            content,
        )
        self.assertIn(
            "Enviar instrucciones",
            content,
        )
        self.assertIn(
            reverse("inicio"),
            content,
        )

    @patch("usuarios.services.requests.post")
    def test_02_formulario_contiene_proteccion_csrf(
        self,
        mock_post,
    ):
        """
        2. El formulario contiene token CSRF y rechaza
        POST sin protección.
        """
        mock_response = MagicMock(
            ok=True,
            status_code=200,
        )
        mock_post.return_value = mock_response

        response = self.client.get(
            self.recover_url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        content = response.content.decode(
            "utf-8"
        )

        self.assertIn(
            "csrfmiddlewaretoken",
            content,
        )

        csrf_client = Client(
            enforce_csrf_checks=True
        )

        response_sin_csrf = csrf_client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        self.assertEqual(
            response_sin_csrf.status_code,
            403,
        )
        mock_post.assert_not_called()

    @patch("usuarios.services.requests.post")
    def test_03_correo_invalido_no_ejecuta_llamada_auth0(
        self,
        mock_post,
    ):
        """
        3. Correo inválido o vacío no ejecuta llamada Auth0.
        """
        response = self.client.post(
            self.recover_url,
            {"correo": "correo-no-valido"},
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        mock_post.assert_not_called()

        self.assertTemplateUsed(
            response,
            "usuarios/recover.html",
        )

        response_vacio = self.client.post(
            self.recover_url,
            {"correo": ""},
        )

        self.assertEqual(
            response_vacio.status_code,
            200,
        )
        mock_post.assert_not_called()

    @patch("usuarios.services.requests.post")
    def test_04_correo_valido_construye_correctamente_la_solicitud(
        self,
        mock_post,
    ):
        """
        4. Correo válido construye y envía solicitud Auth0.
        """
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        response = self.client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        self.assertEqual(
            response.status_code,
            200,
        )
        self.assertEqual(
            mock_post.call_count,
            1,
        )

    @patch("usuarios.services.requests.post")
    def test_05_url_auth0_correcta(
        self,
        mock_post,
    ):
        """
        5. La URL corresponde a
        /dbconnections/change_password.
        """
        mock_response = MagicMock(
            ok=True,
            status_code=200,
        )
        mock_post.return_value = mock_response

        self.client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        url_llamada = (
            mock_post.call_args[0][0]
        )

        expected_url = (
            f"https://{settings.AUTH0_DOMAIN}"
            "/dbconnections/change_password"
        )

        self.assertEqual(
            url_llamada,
            expected_url,
        )

    @patch("usuarios.services.requests.post")
    def test_06_client_id_correcto(
        self,
        mock_post,
    ):
        """
        6. El payload incluye client_id.
        """
        mock_response = MagicMock(
            ok=True,
            status_code=200,
        )
        mock_post.return_value = mock_response

        self.client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        payload = (
            mock_post.call_args
            .kwargs
            .get("json", {})
        )

        self.assertEqual(
            payload.get("client_id"),
            settings.AUTH0_CLIENT_ID,
        )

    @patch("usuarios.services.requests.post")
    def test_07_connection_correcta(
        self,
        mock_post,
    ):
        """
        7. El payload usa la conexión configurada.
        """
        mock_response = MagicMock(
            ok=True,
            status_code=200,
        )
        mock_post.return_value = mock_response

        self.client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        payload = (
            mock_post.call_args
            .kwargs
            .get("json", {})
        )

        self.assertEqual(
            payload.get("connection"),
            "Username-Password-Authentication",
        )
        self.assertEqual(
            payload.get("connection"),
            settings.AUTH0_DB_CONNECTION,
        )

    @patch("usuarios.services.requests.post")
    def test_08_timeout_configurado(
        self,
        mock_post,
    ):
        """
        8. La solicitud incluye timeout de 10 segundos.
        """
        mock_response = MagicMock(
            ok=True,
            status_code=200,
        )
        mock_post.return_value = mock_response

        self.client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        timeout = (
            mock_post.call_args
            .kwargs
            .get("timeout")
        )

        self.assertEqual(
            timeout,
            10,
        )

    @patch("usuarios.services.requests.post")
    def test_09_respuesta_exitosa_muestra_mensaje_generico(
        self,
        mock_post,
    ):
        """
        9. Respuesta exitosa muestra mensaje genérico.
        """
        mock_response = MagicMock(
            ok=True,
            status_code=200,
        )
        mock_post.return_value = mock_response

        response = self.client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        content = response.content.decode(
            "utf-8"
        )

        mensaje_esperado = (
            "Si existe una cuenta compatible asociada a ese correo, "
            "recibirás instrucciones para recuperar el acceso."
        )

        self.assertIn(
            mensaje_esperado,
            content,
        )

    @patch("usuarios.services.requests.post")
    def test_10_usuario_inexistente_no_se_revela_mediante_mensaje(
        self,
        mock_post,
    ):
        """
        10. Usuario inexistente no se revela.
        """
        mock_response = MagicMock(
            ok=True,
            status_code=200,
        )
        mock_post.return_value = mock_response

        correo_inexistente = (
            "desconocido.absoluto@duocuc.cl"
        )

        response = self.client.post(
            self.recover_url,
            {"correo": correo_inexistente},
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        content = response.content.decode(
            "utf-8"
        )

        mensaje_esperado = (
            "Si existe una cuenta compatible asociada a ese correo, "
            "recibirás instrucciones para recuperar el acceso."
        )

        self.assertIn(
            mensaje_esperado,
            content,
        )
        self.assertNotIn(
            "no encontrado",
            content.lower(),
        )
        self.assertNotIn(
            "no existe",
            content.lower(),
        )

    @patch("usuarios.services.requests.post")
    def test_11_timeout_se_maneja_de_forma_controlada(
        self,
        mock_post,
    ):
        """
        11. Timeout hacia Auth0 se maneja controladamente.
        """
        mock_post.side_effect = requests.Timeout(
            "Connection timed out"
        )

        response = self.client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        content = response.content.decode(
            "utf-8"
        )

        self.assertIn(
            "No fue posible procesar la solicitud en este momento",
            content,
        )
        self.assertNotIn(
            "Traceback",
            content,
        )
        self.assertNotIn(
            "Timeout",
            content,
        )
        self.assertNotIn(
            "Exception",
            content,
        )

    @patch("usuarios.services.requests.post")
    def test_12_error_http_auth0_se_maneja_de_forma_controlada(
        self,
        mock_post,
    ):
        """
        12. Error HTTP de Auth0 se maneja controladamente.
        """
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = (
            "Internal Auth0 database error details"
        )
        mock_post.return_value = mock_response

        response = self.client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        content = response.content.decode(
            "utf-8"
        )

        self.assertIn(
            "No fue posible procesar la solicitud en este momento",
            content,
        )
        self.assertNotIn(
            "Traceback",
            content,
        )
        self.assertNotIn(
            "Internal Auth0 database error details",
            content,
        )

    @patch("usuarios.services.requests.post")
    def test_13_client_secret_no_es_enviado(
        self,
        mock_post,
    ):
        """
        13. Client Secret no es enviado.
        """
        mock_response = MagicMock(
            ok=True,
            status_code=200,
        )
        mock_post.return_value = mock_response

        self.client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        payload = (
            mock_post.call_args
            .kwargs
            .get("json", {})
        )
        all_kwargs = str(
            mock_post.call_args
        )

        self.assertNotIn(
            "client_secret",
            payload,
        )
        self.assertNotIn(
            settings.AUTH0_CLIENT_SECRET,
            all_kwargs,
        )

    @patch("usuarios.services.requests.post")
    def test_14_no_se_modifica_usuario_ni_ninguna_tabla_siget(
        self,
        mock_post,
    ):
        """
        14. Recuperación no consulta ni modifica Usuario.
        """
        mock_response = MagicMock(
            ok=True,
            status_code=200,
        )
        mock_post.return_value = mock_response

        with (
            patch.object(
                Usuario.objects,
                "filter",
            ) as mock_u_filter,
            patch.object(
                Usuario.objects,
                "get",
            ) as mock_u_get,
            patch.object(
                Usuario.objects,
                "all",
            ) as mock_u_all,
            patch.object(
                UsuarioRol.objects,
                "filter",
            ) as mock_ur_filter,
        ):
            self.client.get(
                self.recover_url
            )
            self.client.post(
                self.recover_url,
                {"correo": self.correo_valido},
            )

            mock_u_filter.assert_not_called()
            mock_u_get.assert_not_called()
            mock_u_all.assert_not_called()
            mock_ur_filter.assert_not_called()

    def test_15_enlace_recuperar_acceso_visible_en_pantalla_login(
        self,
    ):
        """
        15. Pantalla de login muestra Recuperar acceso.
        """
        response = self.client.get(
            reverse("inicio")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        content = response.content.decode(
            "utf-8"
        )

        self.assertIn(
            "Recuperar acceso",
            content,
        )
        self.assertIn(
            self.recover_url,
            content,
        )

    @patch("usuarios.services.settings")
    def test_16_error_configuracion_auth0_se_maneja_controladamente(
        self,
        mock_settings,
    ):
        """
        16. Configuración incompleta Auth0 se maneja
        sin error 500.
        """
        mock_settings.AUTH0_DOMAIN = ""
        mock_settings.AUTH0_CLIENT_ID = ""

        response = self.client.post(
            self.recover_url,
            {"correo": self.correo_valido},
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        content = response.content.decode(
            "utf-8"
        )

        self.assertIn(
            "No fue posible procesar la solicitud en este momento",
            content,
        )
