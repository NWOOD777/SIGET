"""
Pruebas exhaustivas para la validación de access tokens Auth0,
autenticación Bearer en DRF y el endpoint /api/usuarios/me/.
"""

import time
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings
from rest_framework.response import Response
from rest_framework.test import APIClient

from usuarios.models import Permiso, Rol, RolPermiso, Usuario, UsuarioRol
from usuarios.services import (
    ROL_ADMINISTRADOR,
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
)
from usuarios.tokens import (
    ConfiguracionTokenError,
    ProveedorIdentidadNoDisponibleError,
    TokenExpiradoError,
    TokenInvalidoError,
    validar_access_token,
)


def _respuesta(response: object) -> Response:
    assert isinstance(response, Response)
    return response


def _datos(response: Response) -> dict[str, Any]:
    assert isinstance(response.data, dict)
    return response.data


def _generar_par_claves_rsa():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()
    return private_key, public_key


TEST_PRIVATE_KEY, TEST_PUBLIC_KEY = _generar_par_claves_rsa()
TEST_PRIVATE_KEY_2, _ = _generar_par_claves_rsa()


class ValidacionAccessTokenUnitTests(TestCase):
    """Pruebas unitarias de tokens.py verificando todos los criterios RFC y Auth0."""

    DOMAIN = "siget.us.auth0.com"
    ISSUER = "https://siget.us.auth0.com/"
    AUDIENCE = "https://api.siget.local"
    KID = "test-key-id-1"

    def setUp(self):
        self.mock_jwk_key = MagicMock()
        self.mock_jwk_key.key = TEST_PUBLIC_KEY

        self.patcher = patch("usuarios.tokens._obtener_cliente_jwks")
        self.mock_jwks_client_getter = self.patcher.start()
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = self.mock_jwk_key
        self.mock_jwks_client_getter.return_value = mock_client

    def tearDown(self):
        self.patcher.stop()

    def _crear_token(
        self,
        claims=None,
        headers=None,
        private_key=TEST_PRIVATE_KEY,
        algorithm="RS256",
    ):
        ahora = int(time.time())
        payload = {
            "iss": self.ISSUER,
            "sub": "auth0|tecnico_123",
            "aud": self.AUDIENCE,
            "iat": ahora - 10,
            "exp": ahora + 3600,
        }
        if claims:
            payload.update(claims)
        token_headers = {"kid": self.KID}
        if headers is not None:
            token_headers = headers
        return jwt.encode(
            payload, private_key, algorithm=algorithm, headers=token_headers
        )

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_ISSUER=ISSUER,
        AUTH0_API_AUDIENCE=AUDIENCE,
        AUTH0_TOKEN_LEEWAY=10,
        AUTH0_API_ALLOWED_CLIENT_IDS=[],
    )
    def test_token_valido_retorna_claims(self):
        token = self._crear_token({"sub": "auth0|tecnico_valido"})
        claims = validar_access_token(token)
        self.assertEqual(claims["sub"], "auth0|tecnico_valido")
        self.assertEqual(claims["aud"], self.AUDIENCE)
        self.assertEqual(claims["iss"], self.ISSUER)

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_ISSUER=ISSUER,
        AUTH0_API_AUDIENCE=AUDIENCE,
        AUTH0_TOKEN_LEEWAY=0,
    )
    def test_token_expirado_lanza_excepcion(self):
        ahora = int(time.time())
        token = self._crear_token(
            {
                "iat": ahora - 7200,
                "exp": ahora - 3600,
            }
        )
        with self.assertRaises(TokenExpiradoError):
            validar_access_token(token)

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_ISSUER=ISSUER,
        AUTH0_API_AUDIENCE=AUDIENCE,
    )
    def test_token_con_firma_invalida_lanza_excepcion(self):
        token = self._crear_token(private_key=TEST_PRIVATE_KEY_2)
        with self.assertRaises(TokenInvalidoError):
            validar_access_token(token)

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_ISSUER=ISSUER,
        AUTH0_API_AUDIENCE=AUDIENCE,
    )
    def test_token_sin_kid_lanza_excepcion(self):
        token = self._crear_token(headers={})
        with self.assertRaises(TokenInvalidoError):
            validar_access_token(token)

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_ISSUER=ISSUER,
        AUTH0_API_AUDIENCE=AUDIENCE,
    )
    def test_token_con_algoritmo_no_permitido_lanza_excepcion(self):
        token = jwt.encode(
            {
                "iss": self.ISSUER,
                "aud": self.AUDIENCE,
                "sub": "auth0|x",
                "iat": 100,
                "exp": 200,
            },
            "secret_hmac_32_bytes_longitud_minima_adecuada!",
            algorithm="HS256",
            headers={"kid": self.KID},
        )
        with self.assertRaises(TokenInvalidoError):
            validar_access_token(token)

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_ISSUER=ISSUER,
        AUTH0_API_AUDIENCE=AUDIENCE,
    )
    def test_token_con_emisor_incorrecto_lanza_excepcion(self):
        token = self._crear_token({"iss": "https://malicious-issuer.com/"})
        with self.assertRaises(TokenInvalidoError):
            validar_access_token(token)

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_ISSUER=ISSUER,
        AUTH0_API_AUDIENCE=AUDIENCE,
    )
    def test_token_con_audiencia_incorrecta_lanza_excepcion(self):
        token = self._crear_token({"aud": "client_id_web_o_management"})
        with self.assertRaises(TokenInvalidoError):
            validar_access_token(token)

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_ISSUER=ISSUER,
        AUTH0_API_AUDIENCE=AUDIENCE,
    )
    def test_token_machine_to_machine_rechazado(self):
        token = self._crear_token(
            {
                "gty": "client-credentials",
                "sub": "client_id_123@clients",
            }
        )
        with self.assertRaises(TokenInvalidoError):
            validar_access_token(token)

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_ISSUER=ISSUER,
        AUTH0_API_AUDIENCE=AUDIENCE,
        AUTH0_API_ALLOWED_CLIENT_IDS=["allowed_native_client"],
    )
    def test_token_con_azp_no_autorizado_rechazado(self):
        token = self._crear_token({"azp": "unauthorized_client"})
        with self.assertRaises(TokenInvalidoError):
            validar_access_token(token)

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_API_AUDIENCE="",
    )
    def test_configuracion_incompleta_lanza_excepcion(self):
        with self.assertRaises(ConfiguracionTokenError):
            validar_access_token("some.token.here")

    @override_settings(
        AUTH0_DOMAIN=DOMAIN,
        AUTH0_ISSUER=ISSUER,
        AUTH0_API_AUDIENCE="https://siget.us.auth0.com/api/v2/",
        AUTH0_MGMT_AUDIENCE="https://siget.us.auth0.com/api/v2/",
    )
    def test_audiencia_management_api_prohibida(self):
        with self.assertRaises(ConfiguracionTokenError):
            validar_access_token("some.token.here")


@override_settings(
    AUTH0_DOMAIN="siget.us.auth0.com",
    AUTH0_ISSUER="https://siget.us.auth0.com/",
    AUTH0_API_AUDIENCE="https://api.siget.local",
    AUTH0_TOKEN_LEEWAY=10,
    AUTH0_API_ALLOWED_CLIENT_IDS=[],
)
class BearerAuthYUsuarioMeIntegrationTests(TestCase):
    """
    Pruebas de integración sobre la API REST de SIGET con autenticación Bearer
    y endpoint /api/usuarios/me/.
    """

    def setUp(self):
        # Roles de catálogo
        self.rol_admin, _ = Rol.objects.get_or_create(
            nombre=ROL_ADMINISTRADOR,
            defaults={"descripcion": "Administrador del sistema"},
        )
        self.rol_tecnico, _ = Rol.objects.get_or_create(
            nombre=ROL_TECNICO,
            defaults={"descripcion": "Técnico de soporte"},
        )
        self.rol_solicitante, _ = Rol.objects.get_or_create(
            nombre=ROL_USUARIO_SOLICITANTE,
            defaults={"descripcion": "Usuario solicitante"},
        )

        # Permisos
        self.perm_catalogo, _ = Permiso.objects.get_or_create(
            codigo="CATALOGO_CONSULTAR",
            defaults={"descripcion": "Consultar catálogo"},
        )
        self.perm_usuarios, _ = Permiso.objects.get_or_create(
            codigo="USUARIOS_ADMINISTRAR",
            defaults={"descripcion": "Administrar usuarios"},
        )
        self.perm_atender, _ = Permiso.objects.get_or_create(
            codigo="TICKET_ATENDER",
            defaults={"descripcion": "Atender tickets"},
        )

        RolPermiso.objects.get_or_create(rol=self.rol_admin, permiso=self.perm_usuarios)
        RolPermiso.objects.get_or_create(rol=self.rol_admin, permiso=self.perm_catalogo)
        RolPermiso.objects.get_or_create(
            rol=self.rol_tecnico, permiso=self.perm_atender
        )
        RolPermiso.objects.get_or_create(
            rol=self.rol_tecnico, permiso=self.perm_catalogo
        )
        RolPermiso.objects.get_or_create(
            rol=self.rol_solicitante, permiso=self.perm_catalogo
        )

        # Usuarios
        self.usuario_admin = Usuario.objects.create(
            identificador_externo="auth0|admin_sub_1",
            proveedor_identidad="Auth0",
            rut="11111111-1",
            nombres="Carlos",
            apellidos="Admin",
            correo="carlos.admin@siget.cl",
            activo=True,
        )
        UsuarioRol.objects.create(usuario=self.usuario_admin, rol=self.rol_admin)

        self.usuario_tecnico = Usuario.objects.create(
            identificador_externo="auth0|tecnico_sub_2",
            proveedor_identidad="Auth0",
            rut="22222222-2",
            nombres="Tomás",
            apellidos="Técnico",
            correo="tomas.tecnico@siget.cl",
            activo=True,
        )
        UsuarioRol.objects.create(usuario=self.usuario_tecnico, rol=self.rol_tecnico)

        self.usuario_solicitante = Usuario.objects.create(
            identificador_externo="auth0|solicitante_sub_3",
            proveedor_identidad="Auth0",
            rut="33333333-3",
            nombres="Sara",
            apellidos="Solicitante",
            correo="sara.solicitante@siget.cl",
            activo=True,
        )
        UsuarioRol.objects.create(
            usuario=self.usuario_solicitante, rol=self.rol_solicitante
        )

        self.usuario_inactivo = Usuario.objects.create(
            identificador_externo="auth0|inactivo_sub_4",
            proveedor_identidad="Auth0",
            rut="44444444-4",
            nombres="Iván",
            apellidos="Inactivo",
            correo="ivan.inactivo@siget.cl",
            activo=False,
        )
        UsuarioRol.objects.create(usuario=self.usuario_inactivo, rol=self.rol_tecnico)

        # Usuario multi-rol (Técnico + Administrador)
        self.usuario_multirole = Usuario.objects.create(
            identificador_externo="auth0|multirole_sub_5",
            proveedor_identidad="Auth0",
            rut="55555555-5",
            nombres="Marta",
            apellidos="DobleRol",
            correo="marta.doblerol@siget.cl",
            activo=True,
        )
        UsuarioRol.objects.create(usuario=self.usuario_multirole, rol=self.rol_admin)
        UsuarioRol.objects.create(usuario=self.usuario_multirole, rol=self.rol_tecnico)

        # Mocks para validar_access_token
        self.patcher = patch("usuarios.authentication.validar_access_token")
        self.mock_validar = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_me_api_con_token_tecnico_retorna_200_y_permisos(self):
        self.mock_validar.return_value = {
            "sub": "auth0|tecnico_sub_2",
            "aud": "https://api.siget.local",
            "iss": "https://siget.us.auth0.com/",
        }

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token_valido_tecnico")
        response = _respuesta(client.get("/api/usuarios/me/"))

        self.assertEqual(response.status_code, 200)
        datos = _datos(response)
        self.assertEqual(datos["id_usuario"], self.usuario_tecnico.id_usuario)
        self.assertEqual(datos["correo"], "tomas.tecnico@siget.cl")
        self.assertEqual(datos["nombre_completo"], "Tomás Técnico")
        self.assertIn("Técnico de soporte", datos["roles"])
        self.assertTrue(datos["acceso_escritorio"])
        self.assertIn("TICKET_ATENDER", datos["permisos"])
        self.assertEqual(datos["metodo_autenticacion"], "bearer")

    def test_token_firmado_consulta_identidad_e_inventario_y_rechaza_cuenta_desactivada(
        self,
    ):
        # Se sustituye únicamente el proveedor remoto de claves. La firma JWT,
        # autenticación DRF, permisos y consultas PostgreSQL se ejecutan realmente.
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": self.usuario_tecnico.identificador_externo,
                "iss": "https://siget.us.auth0.com/",
                "aud": "https://api.siget.local",
                "iat": now,
                "exp": now + 3600,
            },
            TEST_PRIVATE_KEY,
            algorithm="RS256",
            headers={"kid": "test-local-key"},
        )
        key = MagicMock()
        key.key = TEST_PUBLIC_KEY
        self.mock_validar.side_effect = validar_access_token
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        with patch("usuarios.tokens._obtener_cliente_jwks") as jwks:
            jwks.return_value.get_signing_key_from_jwt.return_value = key
            identity = _respuesta(client.get("/api/usuarios/me/"))
            self.assertEqual(identity.status_code, 200)
            self.assertEqual(_datos(identity)["id_usuario"], self.usuario_tecnico.pk)
            inventory = _respuesta(client.get("/api/activos/"))
            self.assertEqual(inventory.status_code, 200)
            self.assertIsInstance(inventory.data, list)
            self.usuario_tecnico.activo = False
            self.usuario_tecnico.save(update_fields=["activo"])
            self.assertEqual(
                _respuesta(client.get("/api/usuarios/me/")).status_code, 403
            )

    def test_me_api_con_token_admin_retorna_200_y_roles(self):
        self.mock_validar.return_value = {
            "sub": "auth0|admin_sub_1",
            "aud": "https://api.siget.local",
            "iss": "https://siget.us.auth0.com/",
        }

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token_valido_admin")
        response = _respuesta(client.get("/api/usuarios/me/"))

        self.assertEqual(response.status_code, 200)
        datos = _datos(response)
        self.assertIn("Administrador del sistema", datos["roles"])
        self.assertTrue(datos["acceso_escritorio"])
        self.assertIn("USUARIOS_ADMINISTRAR", datos["permisos"])

    def test_me_api_con_token_solicitante_indica_sin_acceso_escritorio(self):
        self.mock_validar.return_value = {
            "sub": "auth0|solicitante_sub_3",
            "aud": "https://api.siget.local",
            "iss": "https://siget.us.auth0.com/",
        }

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token_solicitante")
        response = _respuesta(client.get("/api/usuarios/me/"))

        self.assertEqual(response.status_code, 200)
        datos = _datos(response)
        self.assertEqual(datos["roles"], ["Usuario solicitante"])
        self.assertFalse(datos["acceso_escritorio"])

    def test_me_api_con_usuario_multirole(self):
        self.mock_validar.return_value = {
            "sub": "auth0|multirole_sub_5",
            "aud": "https://api.siget.local",
            "iss": "https://siget.us.auth0.com/",
        }

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token_multirole")
        response = _respuesta(client.get("/api/usuarios/me/"))

        self.assertEqual(response.status_code, 200)
        datos = _datos(response)
        self.assertIn("Administrador del sistema", datos["roles"])
        self.assertIn("Técnico de soporte", datos["roles"])
        self.assertTrue(datos["acceso_escritorio"])
        self.assertIn("USUARIOS_ADMINISTRAR", datos["permisos"])
        self.assertIn("TICKET_ATENDER", datos["permisos"])

    def test_token_expirado_responde_401_con_codigo(self):
        self.mock_validar.side_effect = TokenExpiradoError("El token de acceso expiró.")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token_expirado")
        response = _respuesta(client.get("/api/usuarios/me/"))

        self.assertEqual(response.status_code, 401)
        self.assertIn("Bearer", response.headers.get("WWW-Authenticate", ""))
        self.assertEqual(_datos(response).get("codigo"), "token_expirado")

    def test_token_invalido_responde_401_con_codigo(self):
        self.mock_validar.side_effect = TokenInvalidoError("Token inválido.")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token_invalido")
        response = _respuesta(client.get("/api/usuarios/me/"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(_datos(response).get("codigo"), "token_invalido")

    def test_usuario_inactivo_responde_403(self):
        self.mock_validar.return_value = {
            "sub": "auth0|inactivo_sub_4",
            "aud": "https://api.siget.local",
            "iss": "https://siget.us.auth0.com/",
        }

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token_inactivo")
        response = _respuesta(client.get("/api/usuarios/me/"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(_datos(response).get("codigo"), "cuenta_sin_acceso")

    def test_usuario_no_registrado_responde_403(self):
        self.mock_validar.return_value = {
            "sub": "auth0|no_registrado_999",
            "aud": "https://api.siget.local",
            "iss": "https://siget.us.auth0.com/",
        }

        with patch("usuarios.tokens.obtener_perfil_userinfo") as mock_userinfo:
            mock_userinfo.return_value = {
                "sub": "auth0|no_registrado_999",
                "email": "desconocido@empresa.cl",
                "email_verified": True,
            }
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION="Bearer token_no_registrado")
            response = _respuesta(client.get("/api/usuarios/me/"))

            self.assertEqual(response.status_code, 403)
            self.assertEqual(_datos(response).get("codigo"), "cuenta_sin_acceso")

    def test_servidor_identidad_caido_responde_503(self):
        self.mock_validar.side_effect = ProveedorIdentidadNoDisponibleError(
            "Auth0 no disponible"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token_jwks_down")
        response = _respuesta(client.get("/api/usuarios/me/"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(_datos(response).get("codigo"), "identidad_no_disponible")

    def test_endpoint_protegido_activos_con_bearer_tecnico(self):
        """Verifica que endpoints existentes de negocio reconozcan al usuario Bearer."""
        self.mock_validar.return_value = {
            "sub": "auth0|tecnico_sub_2",
            "aud": "https://api.siget.local",
            "iss": "https://siget.us.auth0.com/",
        }

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token_tecnico")
        # El Técnico puede consultar el catálogo de categorías de activos (GET protegido)
        response = _respuesta(client.get("/api/activos/categorias/"))
        self.assertEqual(response.status_code, 200)

    def test_endpoint_administrativo_rechaza_bearer_tecnico(self):
        """Un Técnico no puede administrar roles de usuarios aunque envíe Bearer válido."""
        self.mock_validar.return_value = {
            "sub": "auth0|tecnico_sub_2",
            "aud": "https://api.siget.local",
            "iss": "https://siget.us.auth0.com/",
        }

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer token_tecnico")
        # Listado administrativo de usuarios
        response = _respuesta(client.get("/api/usuarios/"))
        self.assertEqual(response.status_code, 403)

    def test_sesion_web_mantiene_compatibilidad(self):
        """Peticiones sin encabezado Bearer usan la sesión Web como siempre."""
        client = APIClient()
        session = client.session
        session["siget_usuario_id"] = self.usuario_admin.id_usuario
        session.save()

        response = _respuesta(client.get("/api/usuarios/me/"))
        self.assertEqual(response.status_code, 200)
        datos = _datos(response)
        self.assertEqual(datos["correo"], "carlos.admin@siget.cl")
        self.assertEqual(datos["metodo_autenticacion"], "sesion")
