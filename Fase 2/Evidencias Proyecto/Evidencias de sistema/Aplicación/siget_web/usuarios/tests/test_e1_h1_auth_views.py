"""
Pruebas de integración y vistas para E1-H1: Endpoints /auth/* e inicio
utilizando RequestFactory.
"""

from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.http import HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from usuarios.models import UsuarioRol
from usuarios.services import (
    CorreoNoVerificadoError,
    ROL_USUARIO_SOLICITANTE,
    UsuarioInactivoError,
    UsuarioNoEncontradoError,
)
from usuarios.views import (
    auth_callback,
    auth_login,
    auth_logout,
    inicio,
    render_auth_error,
)
from .helpers import asignar_mock_session, crear_mock_usuario


class Auth0VistasTests(SimpleTestCase):
    """
    Pruebas de integración sobre los endpoints /auth/*
    e inicio con RequestFactory.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_login_inicia_redireccion(self):
        """
        Escenario 1: /auth/login/ inicia la redirección
        OAuth hacia Auth0.
        """
        request = self.factory.get(
            reverse("usuarios:auth_login")
        )
        asignar_mock_session(request)

        fake_redirect = HttpResponseRedirect(
            "https://siget.us.auth0.com/authorize?response_type=code"
        )

        with patch(
            "usuarios.views.get_oauth"
        ) as mock_get_oauth:
            mock_oauth = MagicMock()
            mock_oauth.auth0.authorize_redirect.return_value = (
                fake_redirect
            )
            mock_get_oauth.return_value = mock_oauth

            response = auth_login(request)

        self.assertEqual(response.status_code, 302)
        mock_oauth.auth0.authorize_redirect.assert_called_once()

        args, _ = (
            mock_oauth
            .auth0
            .authorize_redirect
            .call_args
        )

        self.assertEqual(args[0], request)
        self.assertIn("/auth/callback/", args[1])

    def test_callback_crea_sesion_correctamente(self):
        """
        Escenario 8: Callback exitoso valida claims,
        busca usuario, obtiene roles y crea sesión SIGET.
        """
        request = self.factory.get(
            reverse("usuarios:auth_callback")
            + "?code=valid_test_code"
        )
        session = asignar_mock_session(request)

        mock_user = crear_mock_usuario(
            id_usuario=7,
            identificador_externo="auth0|ok_user",
            nombres="Felipe",
            apellidos="Castillo",
            correo="f.castillo@duocuc.cl",
            activo=True,
        )

        with (
            patch(
                "usuarios.views.get_oauth"
            ) as mock_get_oauth,
            patch(
                "usuarios.views.vincular_o_obtener_usuario"
            ) as mock_vincular,
            patch.object(
                UsuarioRol.objects,
                "filter",
            ) as mock_ur_filter,
        ):
            mock_oauth = MagicMock()

            (
                mock_oauth
                .auth0
                .authorize_access_token
                .return_value
            ) = {
                "userinfo": {
                    "sub": "auth0|ok_user",
                    "email": "f.castillo@duocuc.cl",
                    "email_verified": True,
                }
            }

            mock_get_oauth.return_value = mock_oauth
            mock_vincular.return_value = mock_user

            (
                mock_ur_filter
                .return_value
                .select_related
                .return_value
                .values_list
                .return_value
            ) = ["Administrador del sistema"]

            response = auth_callback(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("inicio"),
        )
        self.assertEqual(
            session["siget_usuario_id"],
            7,
        )
        self.assertEqual(
            session["auth0_sub"],
            "auth0|ok_user",
        )
        self.assertEqual(
            session["usuario_correo"],
            "f.castillo@duocuc.cl",
        )
        self.assertEqual(
            session["usuario_nombre"],
            "Felipe Castillo",
        )
        self.assertEqual(
            session["roles"],
            ["Administrador del sistema"],
        )
        self.assertEqual(
            session["proveedor_identidad"],
            "Auth0",
        )
        self.assertTrue(session.cycled)

    def test_logout_elimina_sesion_y_redirige_a_auth0(self):
        """
        Escenario 9: /auth/logout/ invalida la sesión
        SIGET y redirige al logout de Auth0.
        """
        request = self.factory.get(
            reverse("usuarios:auth_logout")
        )

        session = asignar_mock_session(
            request,
            {
                "siget_usuario_id": 10,
                "auth0_sub": "auth0|logged_out_user",
                "usuario_nombre": "Felipe",
            },
        )

        response = auth_logout(request)

        self.assertTrue(session.flushed)
        self.assertEqual(len(session), 0)
        self.assertEqual(response.status_code, 302)

        parsed = urlparse(
            response.headers["Location"]
        )

        self.assertEqual(
            parsed.netloc,
            settings.AUTH0_DOMAIN,
        )
        self.assertEqual(
            parsed.path,
            "/v2/logout",
        )

        query_params = parse_qs(parsed.query)

        self.assertIn(
            "client_id",
            query_params,
        )
        self.assertEqual(
            query_params["client_id"][0],
            settings.AUTH0_CLIENT_ID,
        )
        self.assertIn(
            "returnTo",
            query_params,
        )
        self.assertIn(
            "http://testserver/",
            query_params["returnTo"][0],
        )

    def test_error_oauth_en_parametros_get_manejado_controladamente(
        self,
    ):
        """
        Escenario 10a: Error OAuth recibido en parámetros
        GET se maneja de forma controlada.
        """
        request = self.factory.get(
            reverse("usuarios:auth_callback")
            + "?error=access_denied"
            + "&error_description=User%20did%20not%20authorize"
        )
        session = asignar_mock_session(request)

        response = auth_callback(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn(
            "Error de autenticación",
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            settings.AUTH0_CLIENT_SECRET,
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            "siget_usuario_id",
            session,
        )

    def test_error_oauth_en_intercambio_de_token_manejado_controladamente(
        self,
    ):
        """
        Escenario 10b: Una excepción durante el intercambio
        de token se maneja de forma controlada.
        """
        request = self.factory.get(
            reverse("usuarios:auth_callback")
            + "?code=invalid_code"
        )
        session = asignar_mock_session(request)

        with patch(
            "usuarios.views.get_oauth"
        ) as mock_get_oauth:
            mock_oauth = MagicMock()
            (
                mock_oauth
                .auth0
                .authorize_access_token
                .side_effect
            ) = Exception("Conexión fallida")
            mock_get_oauth.return_value = mock_oauth

            response = auth_callback(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "No fue posible validar la respuesta",
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            "Conexión fallida",
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            settings.AUTH0_CLIENT_SECRET,
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            "siget_usuario_id",
            session,
        )

    def test_callback_rechazo_usuario_inexistente(self):
        """
        Callback responde 403 controlado cuando
        el usuario no existe en SIGET.
        """
        request = self.factory.get(
            reverse("usuarios:auth_callback")
            + "?code=valid_code"
        )
        session = asignar_mock_session(request)

        with (
            patch(
                "usuarios.views.get_oauth"
            ) as mock_get_oauth,
            patch(
                "usuarios.views.vincular_o_obtener_usuario"
            ) as mock_vincular,
        ):
            mock_oauth = MagicMock()

            (
                mock_oauth
                .auth0
                .authorize_access_token
                .return_value
            ) = {
                "userinfo": {
                    "sub": "auth0|missing",
                    "email": "missing@duocuc.cl",
                    "email_verified": True,
                }
            }

            mock_get_oauth.return_value = mock_oauth

            mock_vincular.side_effect = (
                UsuarioNoEncontradoError(
                    "Usuario no registrado en SIGET."
                )
            )

            response = auth_callback(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn(
            "Usuario no registrado en SIGET",
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            "siget_usuario_id",
            session,
        )

    def test_callback_rechazo_usuario_inactivo(self):
        """
        Callback responde 403 controlado cuando
        el usuario está inactivo.
        """
        request = self.factory.get(
            reverse("usuarios:auth_callback")
            + "?code=valid_code"
        )
        session = asignar_mock_session(request)

        with (
            patch(
                "usuarios.views.get_oauth"
            ) as mock_get_oauth,
            patch(
                "usuarios.views.vincular_o_obtener_usuario"
            ) as mock_vincular,
        ):
            mock_oauth = MagicMock()

            (
                mock_oauth
                .auth0
                .authorize_access_token
                .return_value
            ) = {
                "userinfo": {
                    "sub": "auth0|inactive",
                    "email": "inactivo@duocuc.cl",
                    "email_verified": True,
                }
            }

            mock_get_oauth.return_value = mock_oauth

            mock_vincular.side_effect = (
                UsuarioInactivoError(
                    "Su cuenta se encuentra inactiva."
                )
            )

            response = auth_callback(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn(
            "inactiva",
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            "siget_usuario_id",
            session,
        )

    def test_callback_rechazo_correo_no_verificado(self):
        """
        Callback responde 403 controlado cuando
        el correo no está verificado.
        """
        request = self.factory.get(
            reverse("usuarios:auth_callback")
            + "?code=valid_code"
        )
        session = asignar_mock_session(request)

        with (
            patch(
                "usuarios.views.get_oauth"
            ) as mock_get_oauth,
            patch(
                "usuarios.views.vincular_o_obtener_usuario"
            ) as mock_vincular,
        ):
            mock_oauth = MagicMock()

            (
                mock_oauth
                .auth0
                .authorize_access_token
                .return_value
            ) = {
                "userinfo": {
                    "sub": "auth0|unverified",
                    "email": "unverified@duocuc.cl",
                    "email_verified": False,
                }
            }

            mock_get_oauth.return_value = mock_oauth

            mock_vincular.side_effect = (
                CorreoNoVerificadoError(
                    "Correo no verificado."
                )
            )

            response = auth_callback(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn(
            "Correo no verificado",
            response.content.decode("utf-8"),
        )
        self.assertNotIn(
            "siget_usuario_id",
            session,
        )

    def test_vista_inicio_sin_sesion(self):
        """
        1. La vista inicio sin sesión debe ofrecer el botón
        para iniciar sesión en el Portal Web.
        """
        request = self.factory.get(
            reverse("inicio")
        )
        asignar_mock_session(request)

        with patch("usuarios.views.obtener_usuario_actual", return_value=None):
            response = inicio(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn(
            "Iniciar sesión institucional",
            content,
        )
        self.assertIn(
            "/auth/login/",
            content,
        )
        self.assertIn(
            "Portal Web de autoservicio",
            content,
        )

    def test_vista_inicio_usuario_solicitante_autorizado(self):
        """
        2. Usuario con rol real Usuario solicitante en PostgreSQL
        puede ver el Portal Web.
        """
        request = self.factory.get(
            reverse("inicio")
        )
        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 1,
                "usuario_nombre": "Constanza Valenzuela",
            },
        )
        mock_user = crear_mock_usuario(
            id_usuario=1,
            nombres="Constanza",
            apellidos="Valenzuela",
        )

        with (
            patch(
                "usuarios.views.obtener_usuario_actual",
                return_value=mock_user,
            ),
            patch(
                "usuarios.views.usuario_tiene_rol",
                return_value=True,
            ),
        ):
            response = inicio(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn(
            "Constanza Valenzuela",
            content,
        )
        self.assertIn(
            "CV",
            content,
        )
        self.assertIn(
            "Portal de autoservicio",
            content,
        )
        self.assertIn(
            "Usuario solicitante",
            content,
        )
        self.assertIn(
            "Mis equipos",
            content,
        )
        self.assertIn(
            "Solicitudes",
            content,
        )
        self.assertIn(
            "Soporte / Tickets",
            content,
        )
        self.assertIn(
            "Notificaciones",
            content,
        )
        self.assertIn(
            "Mi perfil",
            content,
        )
        self.assertIn(
            "Cerrar sesión",
            content,
        )
        self.assertIn(
            "/auth/logout/",
            content,
        )
        # Indicadores neutrales sin datos ficticios
        self.assertIn(
            "—",
            content,
        )
        self.assertIn(
            "Sin información disponible por ahora.",
            content,
        )

    def test_vista_inicio_tecnico_sin_rol_solicitante_recibe_403(self):
        """
        3. Técnico de soporte sin rol Usuario solicitante en PostgreSQL
        no puede ver el Portal Web y recibe HTTP 403.
        """
        request = self.factory.get(
            reverse("inicio")
        )
        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 2,
                "usuario_nombre": "Técnico de Soporte",
                "roles": ["Técnico de soporte"],
            },
        )
        mock_user = crear_mock_usuario(
            id_usuario=2,
            nombres="Técnico",
            apellidos="Soporte",
        )

        with (
            patch(
                "usuarios.views.obtener_usuario_actual",
                return_value=mock_user,
            ),
            patch(
                "usuarios.views.usuario_tiene_rol",
                return_value=False,
            ),
        ):
            response = inicio(request)

        self.assertEqual(response.status_code, 403)
        content = response.content.decode("utf-8")
        self.assertIn(
            "Tu perfil no tiene acceso al Portal Web de autoservicio de SIGET.",
            content,
        )
        self.assertIn(
            "Cerrar sesión",
            content,
        )
        self.assertNotIn(
            "Mis equipos",
            content,
        )

    def test_vista_inicio_administrador_sin_rol_solicitante_recibe_403(self):
        """
        4. Administrador del sistema sin rol Usuario solicitante en PostgreSQL
        no puede ver el Portal Web y recibe HTTP 403.
        """
        request = self.factory.get(
            reverse("inicio")
        )
        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 3,
                "usuario_nombre": "Administrador General",
                "roles": ["Administrador del sistema"],
            },
        )
        mock_user = crear_mock_usuario(
            id_usuario=3,
            nombres="Administrador",
            apellidos="General",
        )

        with (
            patch(
                "usuarios.views.obtener_usuario_actual",
                return_value=mock_user,
            ),
            patch(
                "usuarios.views.usuario_tiene_rol",
                return_value=False,
            ),
        ):
            response = inicio(request)

        self.assertEqual(response.status_code, 403)
        content = response.content.decode("utf-8")
        self.assertIn(
            "Tu perfil no tiene acceso al Portal Web de autoservicio de SIGET.",
            content,
        )
        self.assertIn(
            "Cerrar sesión",
            content,
        )
        self.assertNotIn(
            "Mis equipos",
            content,
        )

    def test_vista_inicio_manipular_session_roles_no_permite_acceso(self):
        """
        5. Manipular session['roles'] = ['Usuario solicitante']
        no permite acceso si PostgreSQL indica que no posee dicho rol.
        """
        request = self.factory.get(
            reverse("inicio")
        )
        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 2,
                "usuario_nombre": "Técnico Manipulador",
                "roles": ["Usuario solicitante"],
            },
        )
        mock_user = crear_mock_usuario(
            id_usuario=2,
            nombres="Técnico",
            apellidos="Manipulador",
        )

        with (
            patch(
                "usuarios.views.obtener_usuario_actual",
                return_value=mock_user,
            ),
            patch(
                "usuarios.views.usuario_tiene_rol",
                return_value=False,
            ) as mock_tiene_rol,
        ):
            response = inicio(request)
            mock_tiene_rol.assert_called_once_with(
                mock_user,
                ROL_USUARIO_SOLICITANTE,
            )

        self.assertEqual(response.status_code, 403)
        content = response.content.decode("utf-8")
        self.assertIn(
            "Tu perfil no tiene acceso al Portal Web de autoservicio de SIGET.",
            content,
        )

    def test_vista_inicio_solicitante_no_contiene_opciones_admin_ni_tecnicas(self):
        """
        6. El inicio del Usuario solicitante no contiene opciones
        administrativas ni técnicas.
        """
        request = self.factory.get(
            reverse("inicio")
        )
        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 1,
                "usuario_nombre": "Constanza Valenzuela",
            },
        )
        mock_user = crear_mock_usuario(
            id_usuario=1,
            nombres="Constanza",
            apellidos="Valenzuela",
        )

        with (
            patch(
                "usuarios.views.obtener_usuario_actual",
                return_value=mock_user,
            ),
            patch(
                "usuarios.views.usuario_tiene_rol",
                return_value=True,
            ),
        ):
            response = inicio(request)

        content = response.content.decode("utf-8")
        self.assertNotIn("Administrador del sistema", content)
        self.assertNotIn("Técnico de soporte", content)
        self.assertNotIn("Usuarios y accesos", content)
        self.assertNotIn("administracion", content.lower())
        self.assertNotIn("diagnóstico", content.lower())
        self.assertNotIn("gestión de activos", content.lower())
        self.assertNotIn("orden de trabajo", content.lower())

    def test_vista_inicio_multiples_roles_muestra_solo_experiencia_solicitante(self):
        """
        Si el usuario posee legítimamente Usuario solicitante y otro rol,
        la Web muestra únicamente la experiencia de Usuario solicitante.
        """
        request = self.factory.get(
            reverse("inicio")
        )
        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 1,
                "usuario_nombre": "Usuario Con Doble Rol",
                "roles": ["Usuario solicitante", "Administrador del sistema"],
            },
        )
        mock_user = crear_mock_usuario(
            id_usuario=1,
            nombres="Usuario",
            apellidos="Doble Rol",
        )

        with (
            patch(
                "usuarios.views.obtener_usuario_actual",
                return_value=mock_user,
            ),
            patch(
                "usuarios.views.usuario_tiene_rol",
                return_value=True,
            ),
        ):
            response = inicio(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Usuario solicitante", content)
        self.assertNotIn("Administrador del sistema", content)
        self.assertNotIn("Usuarios y accesos", content)

    def test_autoescape_en_vista_inicio(self):
        """
        Verifica autoescape de caracteres especiales
        o etiquetas HTML en la vista inicio.
        """
        request = self.factory.get(
            reverse("inicio")
        )

        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 100,
                "usuario_nombre": (
                    "<script>alert('xss_nombre')</script>"
                ),
            },
        )
        mock_user = crear_mock_usuario(
            id_usuario=100,
            nombres="<script>alert('xss_nombre')</script>",
            apellidos="",
        )

        with (
            patch(
                "usuarios.views.obtener_usuario_actual",
                return_value=mock_user,
            ),
            patch(
                "usuarios.views.usuario_tiene_rol",
                return_value=True,
            ),
        ):
            response = inicio(request)

        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")

        self.assertNotIn(
            "<script>alert('xss_nombre')</script>",
            content,
        )
        self.assertIn(
            "&lt;script&gt;alert(&#x27;xss_nombre&#x27;)"
            "&lt;/script&gt;",
            content,
        )

    def test_autoescape_en_vista_error(self):
        """
        Verifica que mensajes de error con etiquetas HTML
        sean autoescapados.
        """
        request = self.factory.get(
            reverse("usuarios:auth_callback")
        )

        malicious_msg = (
            "Error <b>grave</b> "
            "<img src=x onerror=alert(1)>"
        )

        response = render_auth_error(
            request,
            mensaje=malicious_msg,
            status=403,
        )

        self.assertEqual(response.status_code, 403)

        content = response.content.decode("utf-8")

        self.assertNotIn(
            "<b>grave</b>",
            content,
        )
        self.assertNotIn(
            "<img src=x onerror=alert(1)>",
            content,
        )
        self.assertIn(
            "&lt;b&gt;grave&lt;/b&gt;",
            content,
        )
