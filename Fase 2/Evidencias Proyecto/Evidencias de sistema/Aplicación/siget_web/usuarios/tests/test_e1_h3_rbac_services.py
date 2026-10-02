"""
Pruebas unitarias para E1-H3: Lógica de servicios RBAC, roles oficiales,
consultas de permisos efectivos y asignaciones de roles y permisos.
"""

from unittest.mock import MagicMock, patch

from usuarios.models import Permiso, Rol, RolPermiso, UsuarioRol
from usuarios.services import (
    ROL_ADMINISTRADOR,
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
    ROLES_OFICIALES,
    PermisoNoEncontradoError,
    RolNoEncontradoError,
    asignar_permiso_a_rol,
    asignar_roles_usuario,
    obtener_codigos_permisos_usuario,
    obtener_permisos_usuario,
    obtener_roles_usuario,
    retirar_permiso_de_rol,
    usuario_tiene_permiso,
)
from .helpers import RbacTestBase


class RbacRolesTests(RbacTestBase):
    """
    Pruebas sobre la definición y resolución de los roles oficiales de SIGET.
    """

    def test_01_rol_usuario_solicitante_existe_y_puede_resolverse(
        self,
    ):
        """
        1. Rol Usuario solicitante existe y puede resolverse.
        """
        self.assertIn(
            ROL_USUARIO_SOLICITANTE,
            ROLES_OFICIALES,
        )
        self.assertEqual(
            ROL_USUARIO_SOLICITANTE,
            "Usuario solicitante",
        )

        with patch.object(
            Rol.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .first
                .return_value
            ) = self.rol_solicitante

            rol = Rol.objects.filter(
                nombre=ROL_USUARIO_SOLICITANTE
            ).first()

            assert rol is not None

            self.assertEqual(
                rol.nombre,
                "Usuario solicitante",
            )

    def test_02_rol_tecnico_de_soporte_existe_y_puede_resolverse(
        self,
    ):
        """
        2. Rol Técnico de soporte existe y puede resolverse.
        """
        self.assertIn(
            ROL_TECNICO,
            ROLES_OFICIALES,
        )
        self.assertEqual(
            ROL_TECNICO,
            "Técnico de soporte",
        )

        with patch.object(
            Rol.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .first
                .return_value
            ) = self.rol_tecnico

            rol = Rol.objects.filter(
                nombre=ROL_TECNICO
            ).first()

            assert rol is not None

            self.assertEqual(
                rol.nombre,
                "Técnico de soporte",
            )

    def test_03_rol_administrador_del_sistema_existe_y_puede_resolverse(
        self,
    ):
        """
        3. Rol Administrador del sistema existe
        y puede resolverse.
        """
        self.assertIn(
            ROL_ADMINISTRADOR,
            ROLES_OFICIALES,
        )
        self.assertEqual(
            ROL_ADMINISTRADOR,
            "Administrador del sistema",
        )

        with patch.object(
            Rol.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .first
                .return_value
            ) = self.rol_admin

            rol = Rol.objects.filter(
                nombre=ROL_ADMINISTRADOR
            ).first()

            assert rol is not None

            self.assertEqual(
                rol.nombre,
                "Administrador del sistema",
            )


class RbacConsultasTests(RbacTestBase):
    """
    Pruebas sobre consultas de roles y permisos efectivos derivados de RBAC.
    """

    def test_04_obtener_roles_usuario_devuelve_roles_reales(
        self,
    ):
        """
        4. obtener_roles_usuario devuelve roles asociados
        mediante UsuarioRol.
        """
        with patch.object(
            Rol.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .distinct
                .return_value
                .order_by
                .return_value
            ) = [self.rol_admin]

            roles = obtener_roles_usuario(
                self.admin_user
            )

            self.assertEqual(
                roles,
                [self.rol_admin],
            )
            self.assertEqual(
                roles[0].nombre,
                ROL_ADMINISTRADOR,
            )

    def test_05_obtener_permisos_usuario_devuelve_permisos_derivados_de_rol_permiso(
        self,
    ):
        """
        5. obtener_permisos_usuario devuelve permisos
        derivados de RolPermiso.
        """
        with patch.object(
            Permiso.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .distinct
                .return_value
                .order_by
                .return_value
            ) = [
                self.permiso_cat,
                self.permiso_adm,
            ]

            permisos = obtener_permisos_usuario(
                self.admin_user
            )

            self.assertEqual(
                len(permisos),
                2,
            )
            self.assertEqual(
                permisos[0].codigo,
                "CATALOGO_CONSULTAR",
            )
            self.assertEqual(
                permisos[1].codigo,
                "USUARIOS_ADMINISTRAR",
            )

    def test_06_permisos_efectivos_no_tienen_duplicados(
        self,
    ):
        """
        6. Permisos efectivos eliminan duplicados.
        """
        with patch.object(
            Permiso.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .values_list
                .return_value
                .distinct
                .return_value
            ) = [
                "CATALOGO_CONSULTAR",
                "TICKET_CREAR",
            ]

            codigos = (
                obtener_codigos_permisos_usuario(
                    self.admin_user
                )
            )

            self.assertIsInstance(
                codigos,
                set,
            )
            self.assertEqual(
                len(codigos),
                2,
            )
            self.assertIn(
                "CATALOGO_CONSULTAR",
                codigos,
            )

    def test_07_usuario_tiene_permiso_devuelve_true_cuando_corresponde(
        self,
    ):
        """
        7. usuario_tiene_permiso devuelve True
        cuando corresponde.
        """
        with patch.object(
            Permiso.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .exists
                .return_value
            ) = True

            tiene_permiso = usuario_tiene_permiso(
                self.admin_user,
                "CATALOGO_CONSULTAR",
            )

            self.assertTrue(
                tiene_permiso
            )

    def test_08_usuario_tiene_permiso_devuelve_false_cuando_no_corresponde(
        self,
    ):
        """
        8. usuario_tiene_permiso devuelve False
        cuando no corresponde.
        """
        with patch.object(
            Permiso.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .exists
                .return_value
            ) = False

            tiene_permiso = usuario_tiene_permiso(
                self.solicitante_user,
                "USUARIOS_ADMINISTRAR",
            )

            self.assertFalse(
                tiene_permiso
            )


class RbacAsignacionRolesTests(RbacTestBase):
    """
    Pruebas sobre asignación y modificación de roles a usuarios.
    """

    def test_17_administrador_puede_asignar_rol_existente(
        self,
    ):
        """
        17. Administrador puede asignar rol existente.
        """
        with (
            patch.object(
                UsuarioRol.objects,
                "filter",
            ) as mock_ur_filter,
            patch.object(
                UsuarioRol.objects,
                "get_or_create",
            ) as mock_get_or_create,
        ):
            (
                mock_ur_filter
                .return_value
                .exclude
                .return_value
                .delete
                .return_value
            ) = (1, {})

            mock_get_or_create.return_value = (
                MagicMock(),
                True,
            )

            roles_result = asignar_roles_usuario(
                self.tecnico_user,
                [self.rol_tecnico],
            )

            self.assertEqual(
                roles_result,
                [self.rol_tecnico],
            )

    def test_18_relacion_usuario_rol_se_guarda_correctamente(
        self,
    ):
        """
        18. UsuarioRol se persiste mediante get_or_create.
        """
        with (
            patch.object(
                UsuarioRol.objects,
                "filter",
            ) as mock_ur_filter,
            patch.object(
                UsuarioRol.objects,
                "get_or_create",
            ) as mock_get_or_create,
        ):
            (
                mock_ur_filter
                .return_value
                .exclude
                .return_value
                .delete
                .return_value
            ) = (0, {})

            mock_get_or_create.return_value = (
                MagicMock(),
                True,
            )

            asignar_roles_usuario(
                self.tecnico_user,
                [self.rol_tecnico],
            )

            mock_get_or_create.assert_called_once_with(
                usuario=self.tecnico_user,
                rol=self.rol_tecnico,
            )

    def test_19_no_se_crean_roles_duplicados(
        self,
    ):
        """
        19. Si el mismo rol se procesa repetidamente,
        get_or_create evita crear una segunda relación.
        """
        with (
            patch.object(
                UsuarioRol.objects,
                "filter",
            ) as mock_ur_filter,
            patch.object(
                UsuarioRol.objects,
                "get_or_create",
            ) as mock_get_or_create,
        ):
            (
                mock_ur_filter
                .return_value
                .exclude
                .return_value
                .delete
                .return_value
            ) = (0, {})

            mock_get_or_create.side_effect = [
                (MagicMock(), True),
                (MagicMock(), False),
            ]

            asignar_roles_usuario(
                self.tecnico_user,
                [
                    self.rol_tecnico,
                    self.rol_tecnico,
                ],
            )

            self.assertEqual(
                mock_get_or_create.call_count,
                2,
            )

            for llamada in mock_get_or_create.call_args_list:
                self.assertEqual(
                    llamada.kwargs,
                    {
                        "usuario": self.tecnico_user,
                        "rol": self.rol_tecnico,
                    },
                )

    def test_21_cambio_de_rol_modifica_permisos_efectivos(
        self,
    ):
        """
        21. Cambiar rol modifica permisos efectivos.
        """
        with patch.object(
            Permiso.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .distinct
                .return_value
                .order_by
                .return_value
            ) = [self.permiso_cat]

            perms_solicitante = (
                obtener_permisos_usuario(
                    self.solicitante_user
                )
            )

            self.assertEqual(
                len(perms_solicitante),
                1,
            )
            self.assertEqual(
                perms_solicitante[0].codigo,
                "CATALOGO_CONSULTAR",
            )

        with patch.object(
            Permiso.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .distinct
                .return_value
                .order_by
                .return_value
            ) = [
                self.permiso_cat,
                self.permiso_ot,
            ]

            perms_tecnico = obtener_permisos_usuario(
                self.solicitante_user
            )

            self.assertEqual(
                len(perms_tecnico),
                2,
            )
            self.assertIn(
                self.permiso_ot,
                perms_tecnico,
            )

    def test_22_id_de_rol_inexistente_es_rechazado_controladamente(
        self,
    ):
        """
        22. ID de rol inexistente genera
        RolNoEncontradoError.
        """
        with patch.object(
            Rol.objects,
            "get",
            side_effect=Rol.DoesNotExist,
        ):
            with self.assertRaises(
                RolNoEncontradoError
            ):
                asignar_roles_usuario(
                    self.tecnico_user,
                    [99999],
                )


class RbacPermisosTests(RbacTestBase):
    """
    Pruebas sobre gestión de permisos asociados a roles (RolPermiso).
    """

    def test_24_administrador_puede_agregar_un_permiso_existente_al_rol(
        self,
    ):
        """
        24. Administrador puede asociar permiso al rol.
        """
        with patch.object(
            RolPermiso.objects,
            "get_or_create",
        ) as mock_get_or_create:
            mock_get_or_create.return_value = (
                MagicMock(),
                True,
            )

            relacion = asignar_permiso_a_rol(
                self.rol_tecnico,
                self.permiso_cat,
            )

            self.assertIsNotNone(
                relacion
            )

    def test_25_se_crea_rol_permiso_correctamente(
        self,
    ):
        """
        25. RolPermiso se crea con rol y permiso.
        """
        with patch.object(
            RolPermiso.objects,
            "get_or_create",
        ) as mock_get_or_create:
            mock_get_or_create.return_value = (
                MagicMock(),
                True,
            )

            asignar_permiso_a_rol(
                self.rol_tecnico,
                self.permiso_cat,
            )

            mock_get_or_create.assert_called_once_with(
                rol=self.rol_tecnico,
                permiso=self.permiso_cat,
            )

    def test_26_administrador_puede_retirar_permiso_del_rol(
        self,
    ):
        """
        26. Administrador puede retirar permiso del rol.
        """
        with patch.object(
            RolPermiso.objects,
            "filter",
        ) as mock_rp_filter:
            (
                mock_rp_filter
                .return_value
                .delete
                .return_value
            ) = (1, {})

            resultado = retirar_permiso_de_rol(
                self.rol_tecnico,
                self.permiso_ot,
            )

            self.assertTrue(
                resultado
            )

    def test_27_retirar_permiso_elimina_rol_permiso_pero_no_permiso(
        self,
    ):
        """
        27. Se elimina RolPermiso pero no Permiso.
        """
        with (
            patch.object(
                RolPermiso.objects,
                "filter",
            ) as mock_rp_filter,
            patch.object(
                Permiso.objects,
                "filter",
            ) as mock_p_filter,
        ):
            (
                mock_rp_filter
                .return_value
                .delete
                .return_value
            ) = (1, {})

            retirar_permiso_de_rol(
                self.rol_tecnico,
                self.permiso_ot,
            )

            (
                mock_rp_filter
                .return_value
                .delete
                .assert_called_once()
            )

            (
                mock_p_filter
                .return_value
                .delete
                .assert_not_called()
            )

    def test_28_cambio_afecta_permisos_efectivos_de_usuarios_con_dicho_rol(
        self,
    ):
        """
        28. Cambio de RolPermiso afecta permisos efectivos.
        """
        with patch.object(
            Permiso.objects,
            "filter",
        ) as mock_filter:
            (
                mock_filter
                .return_value
                .distinct
                .return_value
                .order_by
                .return_value
            ) = [self.permiso_cat]

            permisos = obtener_permisos_usuario(
                self.tecnico_user
            )

            self.assertNotIn(
                self.permiso_ot,
                permisos,
            )
            self.assertIn(
                self.permiso_cat,
                permisos,
            )

    def test_29_permiso_inexistente_es_rechazado(
        self,
    ):
        """
        29. Permiso inexistente genera
        PermisoNoEncontradoError.
        """
        with patch.object(
            Permiso.objects,
            "get",
            side_effect=Permiso.DoesNotExist,
        ):
            with self.assertRaises(
                PermisoNoEncontradoError
            ):
                asignar_permiso_a_rol(
                    self.rol_tecnico,
                    99999,
                )
