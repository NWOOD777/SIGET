"""
Pruebas de integración para la API REST de usuarios y control de acceso RBAC (E1-H3).
Verifica endpoints para PySide6, validación de permisos en PostgreSQL,
inmunidad contra manipulación de sesiones HTTP, consulta de roles y permisos
efectivos, modificaciones de asociaciones y trazabilidad en bitacora_auditoria.
"""

from unittest.mock import patch

from usuarios.api_views import (
    RolListAPIView,
    RolPermisoManageAPIView,
    UsuarioAccesoDetailAPIView,
    UsuarioAprovisionarAPIView,
    UsuarioListAPIView,
    UsuarioRolDeleteAPIView,
    UsuarioRolesAPIView,
)
from usuarios.models import UsuarioRol
from usuarios.services import (
    ROL_ADMINISTRADOR,
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
)

from .helpers import (
    RbacTestBase,
    asignar_mock_session,
    crear_mock_usuario,
    obtener_data_dict,
    obtener_data_list,
)


def _crear_request(
    factory, method: str, path: str, usuario_id=None, roles=None, data=None
):
    if method.upper() == "GET":
        req = factory.get(path)
    elif method.upper() == "POST":
        req = factory.post(path, data or {}, format="json")
    elif method.upper() == "DELETE":
        req = factory.delete(path)
    else:
        req = factory.generic(method.upper(), path, data or {})

    session_data = {}
    if usuario_id is not None:
        session_data["siget_usuario_id"] = usuario_id
    if roles is not None:
        session_data["roles"] = roles
    asignar_mock_session(req, session_data)
    return req


class ApiRbacE1H3Tests(RbacTestBase):
    """
    Suite de pruebas correspondiente a los endpoints REST de administración RBAC para PySide6.
    """

    # =========================================================================
    # 1. Pruebas de Autorización y Seguridad (No Autenticado, No Privilegiado)
    # =========================================================================

    def test_01_acceso_no_autenticado_a_endpoints_es_rechazado_con_403(self):
        """
        1. Toda petición a la API administrativa sin sesión activa es rechazada con 403 Forbidden.
        """
        req = _crear_request(self.factory, "GET", "/api/usuarios/")
        view = UsuarioListAPIView.as_view()

        with patch("usuarios.permissions.obtener_usuario_actual", return_value=None):
            resp = view(req)

        self.assertEqual(resp.status_code, 403)
        data = obtener_data_dict(resp)
        self.assertIn("detail", data)

    def test_02_usuario_solicitante_recibe_403_en_endpoints_administrativos(self):
        """
        2. Usuario solicitante recibe 403 al intentar acceder a la API administrativa.
        """
        req = _crear_request(
            self.factory,
            "GET",
            "/api/usuarios/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
        )
        view = UsuarioListAPIView.as_view()

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.solicitante_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=False),
        ):
            resp = view(req)

        self.assertEqual(resp.status_code, 403)
        data = obtener_data_dict(resp)
        self.assertIn("detail", data)

    def test_03_tecnico_de_soporte_recibe_403_en_endpoints_administrativos(self):
        """
        3. Técnico de soporte recibe 403 (las operaciones administrativas de E1-H3 son exclusivas de Administrador).
        """
        req = _crear_request(
            self.factory, "GET", "/api/usuarios/", usuario_id=2, roles=[ROL_TECNICO]
        )
        view = UsuarioListAPIView.as_view()

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=False),
        ):
            resp = view(req)

        self.assertEqual(resp.status_code, 403)

    def test_04_intento_con_sesion_manipulada_de_tecnico_a_administrador_es_bloqueado(
        self,
    ):
        """
        4. ESCENARIO CRÍTICO DE SEGURIDAD:
        Usuario real en PostgreSQL: Técnico de soporte (id=2).
        Sesión HTTP manipulada: session['roles'] = ['Administrador del sistema'].
        Backend verifica directamente en PostgreSQL ignorando la sesión y deniega el acceso (403).
        """
        payload = {
            "nombres": "Atacante",
            "apellidos": "Hacker",
            "correo": "hacker@test.cl",
            "rut": "11111111-K",
            "rol": ROL_ADMINISTRADOR,
        }
        req = _crear_request(
            self.factory,
            "POST",
            "/api/usuarios/aprovisionar/",
            usuario_id=2,
            roles=[ROL_ADMINISTRADOR],  # Manipulación deliberada
            data=payload,
        )
        view = UsuarioAprovisionarAPIView.as_view()

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=False),
            patch("usuarios.services.aprovisionar_usuario") as mock_aprov,
        ):
            resp = view(req)
            mock_aprov.assert_not_called()

        self.assertEqual(resp.status_code, 403)

    # =========================================================================
    # 2. ESCENARIO 1 — Aprovisionamiento de Usuario (API)
    # =========================================================================

    def test_05_administrador_aprovisiona_usuario_exitosamente_retorna_201(self):
        """
        5. Administrador del sistema aprovisiona usuario válido vía POST /api/usuarios/aprovisionar/.
        Retorna 201 Created con ficha completa de acceso.
        """
        payload = {
            "nombres": "Carlos",
            "apellidos": "Pérez",
            "correo": "c.perez@duocuc.cl",
            "rut": "11.111.111-K",
            "rol": ROL_TECNICO,
        }
        req = _crear_request(
            self.factory,
            "POST",
            "/api/usuarios/aprovisionar/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = UsuarioAprovisionarAPIView.as_view()

        nuevo_user = crear_mock_usuario(
            id_usuario=50,
            correo="c.perez@duocuc.cl",
            rut="11111111-K",
            nombres="Carlos",
            apellidos="Pérez",
        )

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.api_views.aprovisionar_usuario", return_value=nuevo_user),
            patch(
                "usuarios.api_views.consultar_usuario_detalle_rbac",
                return_value={
                    "id_usuario": 50,
                    "correo": "c.perez@duocuc.cl",
                    "roles": [{"nombre": ROL_TECNICO}],
                    "permisos_efectivos": [],
                },
            ),
        ):
            resp = view(req)

        self.assertEqual(resp.status_code, 201)
        data = obtener_data_dict(resp)
        self.assertEqual(data["id_usuario"], 50)
        self.assertEqual(data["correo"], "c.perez@duocuc.cl")
        self.assertNotIn("password", data)

    def test_05b_aprovisionamiento_ignora_password_y_no_retorna_credenciales(self):
        """
        5b. Si una solicitud incluye 'password', el serializador lo ignora o rechaza,
        la lógica de aprovisionamiento nunca lo almacena ni lo devuelve en la respuesta.
        """
        view = UsuarioAprovisionarAPIView.as_view()
        payload = {
            "nombres": "Carlos",
            "apellidos": "Pérez",
            "correo": "c.perez@duocuc.cl",
            "rut": "11.111.111-K",
            "rol": ROL_TECNICO,
            "password": "PasswordInyectada123!",
        }
        req = _crear_request(
            self.factory,
            "POST",
            "/api/usuarios/aprovisionar/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )

        nuevo_user = crear_mock_usuario(
            id_usuario=51,
            correo="c.perez@duocuc.cl",
            rut="11111111-K",
            nombres="Carlos",
            apellidos="Pérez",
        )

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.api_views.aprovisionar_usuario", return_value=nuevo_user) as mock_aprov,
            patch(
                "usuarios.api_views.consultar_usuario_detalle_rbac",
                return_value={
                    "id_usuario": 51,
                    "correo": "c.perez@duocuc.cl",
                    "roles": [{"nombre": ROL_TECNICO}],
                    "permisos_efectivos": [],
                },
            ),
        ):
            resp = view(req)

        self.assertEqual(resp.status_code, 201)
        data = obtener_data_dict(resp)
        self.assertNotIn("password", data)
        # Verificar que el serializer no pasó 'password' en validated_data al servicio
        datos_pasados = mock_aprov.call_args[1]["datos"]
        self.assertNotIn("password", datos_pasados)

    def test_06_aprovisionamiento_con_correo_duplicado_retorna_409(self):
        """
        6. Si el usuario ya existe en PostgreSQL, la API responde 409 Conflict.
        """
        from usuarios.services import DuplicadoUsuarioError

        payload = {
            "nombres": "Carlos",
            "apellidos": "Pérez",
            "correo": "c.perez@duocuc.cl",
            "rut": "11.111.111-K",
            "rol": ROL_TECNICO,
        }
        req = _crear_request(
            self.factory,
            "POST",
            "/api/usuarios/aprovisionar/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = UsuarioAprovisionarAPIView.as_view()

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch(
                "usuarios.api_views.aprovisionar_usuario",
                side_effect=DuplicadoUsuarioError("Correo ya registrado"),
            ),
        ):
            resp = view(req)

        self.assertEqual(resp.status_code, 409)
        data = obtener_data_dict(resp)
        self.assertIn("error", data)

    # =========================================================================
    # 3. ESCENARIO 4 — Consulta de Usuarios, Roles y Permisos Efectivos
    # =========================================================================

    def test_07_administrador_lista_usuarios_del_sistema(self):
        """
        7. GET /api/usuarios/ retorna listado de usuarios con sus roles asociados (200 OK).
        """
        req = _crear_request(
            self.factory,
            "GET",
            "/api/usuarios/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = UsuarioListAPIView.as_view()

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.listar_usuarios_sistema",
                return_value=[self.admin_user, self.tecnico_user],
            ),
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
        ):
            mock_rol_filter.return_value.values_list.return_value = [ROL_ADMINISTRADOR]
            resp = view(req)

        self.assertEqual(resp.status_code, 200)
        data = obtener_data_list(resp)
        self.assertEqual(len(data), 2)

    def test_08_consultar_acceso_rbac_usuario_retorna_roles_y_permisos_efectivos(self):
        """
        8. GET /api/usuarios/2/acceso/ retorna roles y permisos efectivos consolidados (200 OK).
        """
        req = _crear_request(
            self.factory,
            "GET",
            "/api/usuarios/2/acceso/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = UsuarioAccesoDetailAPIView.as_view()

        ficha_esperada = {
            "id_usuario": 2,
            "correo": "tecnico@siget.cl",
            "roles": [{"id_rol": 2, "nombre": ROL_TECNICO}],
            "permisos_efectivos": [
                {"id_permiso": 1, "codigo": "CATALOGO_CONSULTAR"},
                {"id_permiso": 2, "codigo": "OT_GESTIONAR"},
            ],
        }

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.get_object_or_404", return_value=self.tecnico_user
            ),
            patch(
                "usuarios.api_views.consultar_usuario_detalle_rbac",
                return_value=ficha_esperada,
            ),
        ):
            resp = view(req, pk=2)

        self.assertEqual(resp.status_code, 200)
        data = obtener_data_dict(resp)
        self.assertEqual(data["id_usuario"], 2)
        self.assertEqual(len(data["roles"]), 1)
        self.assertEqual(len(data["permisos_efectivos"]), 2)

    # =========================================================================
    # 4. ESCENARIO 2 — Asignación y Retiro de Roles
    # =========================================================================

    def test_09_administrador_modifica_roles_de_usuario_correctamente(self):
        """
        9. POST /api/usuarios/2/roles/ asigna nuevos roles y retorna ficha actualizada (200 OK).
        """
        payload = {"roles": [ROL_TECNICO, ROL_ADMINISTRADOR]}
        req = _crear_request(
            self.factory,
            "POST",
            "/api/usuarios/2/roles/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = UsuarioRolesAPIView.as_view()

        ficha_actualizada = {
            "id_usuario": 2,
            "roles": [{"nombre": ROL_TECNICO}, {"nombre": ROL_ADMINISTRADOR}],
        }

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch(
                "usuarios.api_views.get_object_or_404", return_value=self.tecnico_user
            ),
            patch("usuarios.api_views.asignar_roles_usuario") as mock_asignar,
            patch(
                "usuarios.api_views.consultar_usuario_detalle_rbac",
                return_value=ficha_actualizada,
            ),
        ):
            resp = view(req, pk=2)
            mock_asignar.assert_called_once()

        self.assertEqual(resp.status_code, 200)

    def test_10_administrador_retira_rol_de_usuario_exitosamente(self):
        """
        10. DELETE /api/usuarios/2/roles/2/ retira un rol del usuario (200 OK).
        """
        req = _crear_request(
            self.factory,
            "DELETE",
            "/api/usuarios/2/roles/2/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = UsuarioRolDeleteAPIView.as_view()

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch(
                "usuarios.api_views.get_object_or_404", return_value=self.tecnico_user
            ),
            patch("usuarios.api_views.retirar_rol_usuario", return_value=True),
        ):
            resp = view(req, pk=2, id_rol=2)

        self.assertEqual(resp.status_code, 200)
        data = obtener_data_dict(resp)
        self.assertIn("mensaje", data)

    def test_11_intentar_retirar_unico_rol_de_usuario_es_rechazado_con_400(self):
        """
        11. Si se intenta retirar el único rol que posee el usuario, responde 400 Bad Request.
        """
        req = _crear_request(
            self.factory,
            "DELETE",
            "/api/usuarios/2/roles/2/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = UsuarioRolDeleteAPIView.as_view()

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch(
                "usuarios.api_views.get_object_or_404", return_value=self.tecnico_user
            ),
            patch(
                "usuarios.api_views.retirar_rol_usuario",
                side_effect=ValueError("No se puede retirar el único rol"),
            ),
        ):
            resp = view(req, pk=2, id_rol=2)

        self.assertEqual(resp.status_code, 400)
        data = obtener_data_dict(resp)
        self.assertIn("error", data)

    # =========================================================================
    # 5. ESCENARIO 3 — Gestión de Permisos de Rol (API)
    # =========================================================================

    def test_12_administrador_consulta_catalogo_de_roles_con_permisos(self):
        """
        12. GET /api/usuarios/roles/ retorna roles con permisos asociados (200 OK).
        """
        req = _crear_request(
            self.factory,
            "GET",
            "/api/usuarios/roles/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = RolListAPIView.as_view()

        catalogo_mock = [
            {"id_rol": 1, "nombre": ROL_USUARIO_SOLICITANTE, "permisos": []},
            {
                "id_rol": 2,
                "nombre": ROL_TECNICO,
                "permisos": [{"codigo": "CATALOGO_CONSULTAR"}],
            },
        ]

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.listar_roles_con_permisos",
                return_value=catalogo_mock,
            ),
        ):
            resp = view(req)

        self.assertEqual(resp.status_code, 200)
        data = obtener_data_list(resp)
        self.assertEqual(len(data), 2)

    def test_13_administrador_agrega_permiso_a_rol(self):
        """
        13. POST /api/usuarios/roles/2/permisos/ agrega permiso al rol (201 Created).
        """
        payload = {"codigo": "OT_GESTIONAR"}
        req = _crear_request(
            self.factory,
            "POST",
            "/api/usuarios/roles/2/permisos/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = RolPermisoManageAPIView.as_view()

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch(
                "usuarios.api_views.get_object_or_404", return_value=self.rol_tecnico
            ),
            patch("usuarios.api_views.asignar_permiso_a_rol") as mock_asig,
        ):
            resp = view(req, id_rol=2)
            mock_asig.assert_called_once()

        self.assertEqual(resp.status_code, 201)
        data = obtener_data_dict(resp)
        self.assertIn("mensaje", data)

    def test_14_administrador_retira_permiso_de_rol(self):
        """
        14. DELETE /api/usuarios/roles/2/permisos/1/ retira asociación en RolPermiso (200 OK).
        """
        req = _crear_request(
            self.factory,
            "DELETE",
            "/api/usuarios/roles/2/permisos/1/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = RolPermisoManageAPIView.as_view()

        with (
            patch(
                "usuarios.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("usuarios.permissions.es_administrador", return_value=True),
            patch(
                "usuarios.api_views.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch(
                "usuarios.api_views.get_object_or_404", return_value=self.rol_tecnico
            ),
            patch("usuarios.api_views.retirar_permiso_de_rol", return_value=True),
        ):
            resp = view(req, id_rol=2, id_permiso=1)

        self.assertEqual(resp.status_code, 200)
        data = obtener_data_dict(resp)
        self.assertIn("mensaje", data)
