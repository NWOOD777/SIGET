"""
Pruebas unitarias para E1-H1: Servicios de autenticación y vinculación
de usuarios externos con el modelo local de SIGET.
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from usuarios.models import Usuario, UsuarioRol
from usuarios.services import (
    ClaimInvalidoError,
    CorreoNoVerificadoError,
    ErrorVinculacionError,
    UsuarioInactivoError,
    UsuarioNoEncontradoError,
    iniciar_sesion_siget,
    vincular_o_obtener_usuario,
)
from .helpers import asignar_mock_session, crear_mock_usuario


class UsuarioVinculacionServiceTests(SimpleTestCase):
    """
    Pruebas unitarias sobre la lógica de vinculación RBAC en usuarios/services.py.
    """

    def test_usuario_encontrado_por_sub(self):
        """
        Escenario 2: Usuario existente identificado directamente por
        identificador_externo (sub).
        No debe invocar save() pues la cuenta ya está vinculada.
        """
        mock_user = crear_mock_usuario(
            identificador_externo="auth0|existing_sub"
        )
        claims = {
            "sub": "auth0|existing_sub",
            "email": "c.valenzuela@duocuc.cl",
            "email_verified": True,
        }

        with patch.object(Usuario.objects, "filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_user
            usuario = vincular_o_obtener_usuario(claims)

        self.assertEqual(usuario, mock_user)
        mock_user.save.assert_not_called()
        mock_filter.assert_called_once_with(
            identificador_externo="auth0|existing_sub"
        )

    def test_usuario_encontrado_por_correo_verificado(self):
        """
        Escenario 3: Usuario no encontrado por sub, pero localizado
        por correo verificado.
        """
        mock_user = crear_mock_usuario(
            identificador_externo="",
            proveedor_identidad="",
            correo="profesor@duocuc.cl",
        )
        claims = {
            "sub": "auth0|new_teacher_sub",
            "email": "profesor@duocuc.cl",
            "email_verified": True,
        }

        with patch.object(Usuario.objects, "filter") as mock_filter:
            mock_filter.return_value.first.side_effect = [None, mock_user]
            usuario = vincular_o_obtener_usuario(claims)

        self.assertEqual(usuario, mock_user)

    def test_vinculacion_correo_a_sub(self):
        """
        Escenario 4: Al vincular por correo verificado, se actualizan
        únicamente identificador_externo y proveedor_identidad.
        """
        mock_user = crear_mock_usuario(
            identificador_externo="pre_vinculado",
            proveedor_identidad="Local",
            correo="tecnico@duocuc.cl",
        )
        claims = {
            "sub": "auth0|tecnico_sub_999",
            "email": "tecnico@duocuc.cl",
            "email_verified": True,
        }

        with patch.object(Usuario.objects, "filter") as mock_filter:
            mock_filter.return_value.first.side_effect = [None, mock_user]
            vincular_o_obtener_usuario(claims)

        self.assertEqual(
            mock_user.identificador_externo,
            "auth0|tecnico_sub_999",
        )
        self.assertEqual(mock_user.proveedor_identidad, "Auth0")
        mock_user.save.assert_called_once_with(
            update_fields=[
                "identificador_externo",
                "proveedor_identidad",
            ]
        )

    def test_rechazo_correo_no_verificado_en_claims(self):
        """
        Escenario 5a: Si email_verified es False, se rechaza
        la autenticación de inmediato.
        """
        claims = {
            "sub": "auth0|unverified_user",
            "email": "unverified@duocuc.cl",
            "email_verified": False,
        }

        with self.assertRaises(CorreoNoVerificadoError):
            vincular_o_obtener_usuario(claims)

    def test_rechazo_vinculacion_si_correo_no_esta_verificado(self):
        """
        Escenario 5b: Si el usuario existe por correo pero
        email_verified no es True, se rechaza la vinculación.
        """
        mock_user = crear_mock_usuario(
            correo="sinverificar@duocuc.cl"
        )
        claims = {
            "sub": "auth0|sub_sin_verificar",
            "email": "sinverificar@duocuc.cl",
        }

        with patch.object(Usuario.objects, "filter") as mock_filter:
            mock_filter.return_value.first.side_effect = [
                None,
                mock_user,
            ]
            with self.assertRaises(CorreoNoVerificadoError):
                vincular_o_obtener_usuario(claims)

        mock_user.save.assert_not_called()

    def test_rechazo_usuario_siget_inexistente(self):
        """
        Escenario 6: Si no existe por sub ni por correo,
        no se crea automáticamente.
        """
        claims = {
            "sub": "auth0|usuario_nuevo_externo",
            "email": "externo@gmail.com",
            "email_verified": True,
        }

        with patch.object(Usuario.objects, "filter") as mock_filter:
            mock_filter.return_value.first.side_effect = [None, None]

            with self.assertRaises(UsuarioNoEncontradoError):
                vincular_o_obtener_usuario(claims)

    def test_rechazo_usuario_inactivo_por_sub(self):
        """
        Escenario 7a: Usuario localizado por sub pero con
        activo=False debe ser rechazado.
        """
        mock_user = crear_mock_usuario(
            identificador_externo="auth0|inactivo",
            activo=False,
        )
        claims = {
            "sub": "auth0|inactivo",
            "email": "inactivo@duocuc.cl",
            "email_verified": True,
        }

        with patch.object(Usuario.objects, "filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_user

            with self.assertRaises(UsuarioInactivoError):
                vincular_o_obtener_usuario(claims)

    def test_rechazo_usuario_inactivo_por_correo(self):
        """
        Escenario 7b: Usuario vinculado por correo pero
        inactivo debe ser rechazado.
        """
        mock_user = crear_mock_usuario(
            correo="inactivo2@duocuc.cl",
            activo=False,
        )
        claims = {
            "sub": "auth0|inactivo_sub2",
            "email": "inactivo2@duocuc.cl",
            "email_verified": True,
        }

        with patch.object(Usuario.objects, "filter") as mock_filter:
            mock_filter.return_value.first.side_effect = [
                None,
                mock_user,
            ]

            with self.assertRaises(UsuarioInactivoError):
                vincular_o_obtener_usuario(claims)

    def test_rechazo_claims_sin_sub(self):
        """Rechazo controlado si el claim sub no está presente."""
        claims = {
            "email": "test@duocuc.cl",
            "email_verified": True,
        }

        with self.assertRaises(ClaimInvalidoError):
            vincular_o_obtener_usuario(claims)

    def test_rechazo_claims_sin_email(self):
        """Rechazo controlado si el claim email no está presente."""
        claims = {
            "sub": "auth0|12345",
            "email_verified": True,
        }

        with self.assertRaises(ClaimInvalidoError):
            vincular_o_obtener_usuario(claims)

    def test_error_persistencia_en_vinculacion(self):
        """
        Si ocurre un error en la base de datos durante save(),
        se lanza ErrorVinculacionError.
        """
        mock_user = crear_mock_usuario(
            correo="dbfail@duocuc.cl"
        )
        mock_user.save.side_effect = Exception("DB error")

        claims = {
            "sub": "auth0|dbfail_sub",
            "email": "dbfail@duocuc.cl",
            "email_verified": True,
        }

        with patch.object(Usuario.objects, "filter") as mock_filter:
            mock_filter.return_value.first.side_effect = [
                None,
                mock_user,
            ]

            with self.assertRaises(ErrorVinculacionError):
                vincular_o_obtener_usuario(claims)

    def test_iniciar_sesion_siget_estructura(self):
        """
        Escenario 8: Verifica que la sesión SIGET almacene
        los campos requeridos y aplique cycle_key().
        """
        request = MagicMock()
        session = asignar_mock_session(request)

        mock_user = crear_mock_usuario(
            id_usuario=42,
            nombres="Ana",
            apellidos="Rojas",
            correo="a.rojas@duocuc.cl",
        )

        with patch.object(
            UsuarioRol.objects,
            "filter",
        ) as mock_ur_filter:
            (
                mock_ur_filter
                .return_value
                .select_related
                .return_value
                .values_list
                .return_value
            ) = ["Administrador del sistema"]

            iniciar_sesion_siget(
                request,
                mock_user,
                "auth0|ana_42",
            )

        self.assertTrue(session.cycled)
        self.assertEqual(session["siget_usuario_id"], 42)
        self.assertEqual(session["auth0_sub"], "auth0|ana_42")
        self.assertEqual(
            session["usuario_correo"],
            "a.rojas@duocuc.cl",
        )
        self.assertEqual(
            session["usuario_nombre"],
            "Ana Rojas",
        )
        self.assertEqual(
            session["roles"],
            ["Administrador del sistema"],
        )
        self.assertEqual(
            session["proveedor_identidad"],
            mock_user.proveedor_identidad,
        )
        self.assertEqual(
            session["proveedor_identidad"],
            "Auth0",
        )

    def test_iniciar_sesion_siget_guarda_proveedor_identidad_dinamico(
        self,
    ):
        """
        Verifica que iniciar_sesion_siget almacene exactamente
        usuario.proveedor_identidad.
        """
        request = MagicMock()
        session = asignar_mock_session(request)

        mock_user = crear_mock_usuario(
            id_usuario=88,
            nombres="Carlos",
            apellidos="Muñoz",
            correo="c.munoz@duocuc.cl",
            proveedor_identidad="Google Workspace",
        )

        with patch.object(
            UsuarioRol.objects,
            "filter",
        ) as mock_ur_filter:
            (
                mock_ur_filter
                .return_value
                .select_related
                .return_value
                .values_list
                .return_value
            ) = ["Técnico de soporte"]

            iniciar_sesion_siget(
                request,
                mock_user,
                "google-oauth2|carlos88",
            )

        self.assertEqual(
            session["proveedor_identidad"],
            "Google Workspace",
        )
        self.assertEqual(
            session["proveedor_identidad"],
            mock_user.proveedor_identidad,
        )
        self.assertEqual(session["siget_usuario_id"], 88)
        self.assertEqual(
            session["auth0_sub"],
            "google-oauth2|carlos88",
        )
        self.assertEqual(
            session["usuario_correo"],
            "c.munoz@duocuc.cl",
        )
        self.assertEqual(
            session["usuario_nombre"],
            "Carlos Muñoz",
        )
        self.assertEqual(
            session["roles"],
            ["Técnico de soporte"],
        )
