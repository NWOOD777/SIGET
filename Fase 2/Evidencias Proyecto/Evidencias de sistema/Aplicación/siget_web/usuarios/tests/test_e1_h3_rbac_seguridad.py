"""
Pruebas de seguridad para E1-H3: Restricciones de acceso backend,
validación de integridad de roles y prevención de escalada de privilegios.
"""

from unittest.mock import patch

from django.http import HttpResponse
from django.urls import reverse

from usuarios.models import Usuario, UsuarioRol
from usuarios.services import (
    ROL_ADMINISTRADOR,
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
    asignar_roles_usuario,
    obtener_usuario_actual,
    requiere_administrador,
    requiere_permiso,
)
from .helpers import RbacTestBase, asignar_mock_session


class RbacSeguridadTests(RbacTestBase):
    """
    Pruebas críticas de seguridad y autorización para la lógica backend RBAC.
    """

    def test_12_usuario_solicitante_no_puede_acceder_a_operacion_administrativa(
        self,
    ):
        """
        12. Usuario solicitante recibe 403 ante operación protegida.
        """
        request = self.factory.get("/")

        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 3,
                "usuario_nombre": "Solicitante",
                "roles": [ROL_USUARIO_SOLICITANTE],
            },
        )

        @requiere_administrador
        def operacion_protegida(req):
            return HttpResponse("OK")

        with (
            patch(
                "usuarios.services.obtener_usuario_actual",
                return_value=self.solicitante_user,
            ),
            patch(
                "usuarios.services.es_administrador",
                return_value=False,
            ),
        ):
            response = operacion_protegida(request)

            self.assertEqual(
                response.status_code,
                403,
            )

            content = response.content.decode("utf-8")

            self.assertIn(
                "Acceso no autorizado",
                content,
            )

    def test_13_tecnico_de_soporte_no_puede_acceder_a_operacion_administrativa(
        self,
    ):
        """
        13. Técnico de soporte recibe 403 ante operación protegida.
        """
        request = self.factory.get("/")

        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 2,
                "usuario_nombre": "Técnico",
                "roles": [ROL_TECNICO],
            },
        )

        @requiere_administrador
        def operacion_protegida(req):
            return HttpResponse("OK")

        with (
            patch(
                "usuarios.services.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch(
                "usuarios.services.es_administrador",
                return_value=False,
            ),
        ):
            response = operacion_protegida(request)

            self.assertEqual(
                response.status_code,
                403,
            )

            content = response.content.decode("utf-8")

            self.assertIn(
                "Acceso no autorizado",
                content,
            )

    def test_14_usuario_sin_sesion_no_puede_administrar_rbac(
        self,
    ):
        """
        14. Petición sin sesión se redirige al inicio.
        """
        request = self.factory.get("/")

        asignar_mock_session(request)

        @requiere_administrador
        def operacion_protegida(req):
            return HttpResponse("OK")

        with patch(
            "usuarios.services.obtener_usuario_actual",
            return_value=None,
        ):
            response = operacion_protegida(request)

            self.assertEqual(
                response.status_code,
                302,
            )
            self.assertEqual(
                response.headers["Location"],
                reverse("inicio"),
            )

    def test_32_backend_consulta_identidad_siget_actual_mediante_siget_usuario_id(
        self,
    ):
        """
        32. obtener_usuario_actual consulta PostgreSQL
        usando siget_usuario_id.
        """
        request = self.factory.get("/")

        asignar_mock_session(
            request,
            {"siget_usuario_id": 10},
        )

        with patch.object(
            Usuario.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .first
                .return_value
            ) = self.admin_user

            usuario = obtener_usuario_actual(request)

            mock_filter.assert_called_once_with(
                id_usuario=10,
                activo=True,
            )
            self.assertEqual(
                usuario,
                self.admin_user,
            )

    def test_33_modificar_request_session_roles_manualmente_no_concede_privilegios(
        self,
    ):
        """
        33. Manipular session['roles'] no concede
        privilegios si PostgreSQL indica otro rol.
        """
        request = self.factory.get("/")

        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 3,
                "roles": [ROL_ADMINISTRADOR],
            },
        )

        @requiere_administrador
        def operacion_protegida(req):
            return HttpResponse("OK")

        with (
            patch(
                "usuarios.services.obtener_usuario_actual",
                return_value=self.solicitante_user,
            ),
            patch(
                "usuarios.services.es_administrador",
                return_value=False,
            ),
        ):
            response = operacion_protegida(request)

            self.assertEqual(
                response.status_code,
                403,
            )

    def test_34_prueba_critica_escalada_de_privilegios_bloqueada(
        self,
    ):
        """
        34. Técnico con roles manipulados en sesión no puede
        ejecutar una modificación administrativa.
        """
        request = self.factory.post(
            "/operacion-administrativa-protegida/",
            {"roles": [1, 3]},
        )

        asignar_mock_session(
            request,
            {
                "siget_usuario_id": 2,
                "usuario_nombre": "Técnico Malicioso",
                "roles": [ROL_ADMINISTRADOR],
            },
        )

        @requiere_administrador
        def operacion_modificar_roles(req, usuario_target, roles_nuevos) -> HttpResponse:
            asignar_roles_usuario(usuario_target, roles_nuevos)
            return HttpResponse("OK", status=200)

        with (
            patch(
                "usuarios.services.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch(
                "usuarios.services.es_administrador",
                return_value=False,
            ),
            patch.object(
                UsuarioRol.objects,
                "filter",
            ) as mock_ur_filter,
            patch.object(
                UsuarioRol.objects,
                "get_or_create",
            ) as mock_ur_get_or_create,
        ):
            response = operacion_modificar_roles(
                request,
                self.tecnico_user,
                [self.rol_solicitante, self.rol_admin],
            )

            self.assertEqual(
                response.status_code,
                403,
            )

            (
                mock_ur_filter
                .return_value
                .delete
                .assert_not_called()
            )
            mock_ur_get_or_create.assert_not_called()

    def test_35_requiere_permiso_bloquea_usuario_sin_permiso_efectivo(
        self,
    ):
        """
        35. Backend deniega acceso si el usuario carece del permiso efectivo en PostgreSQL.
        """
        @requiere_permiso("USUARIOS_ADMINISTRAR")
        def operacion_con_permiso(req):
            return HttpResponse("Permiso concedido", status=200)

        request = self.factory.get("/")
        asignar_mock_session(request, {"siget_usuario_id": 2})

        with (
            patch(
                "usuarios.services.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch(
                "usuarios.services.usuario_tiene_permiso",
                return_value=False,
            ),
        ):
            response = operacion_con_permiso(request)
            self.assertEqual(response.status_code, 403)
            self.assertIn("Acceso no autorizado", response.content.decode("utf-8"))
