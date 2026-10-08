"""
Pruebas unitarias para el comando de gestión Django primer_admin (Bootstrap inicial de SIGET).

Cubre exhaustivamente:
1. Creación exitosa del primer Administrador.
2. Se crea identidad Auth0 mediante mock.
3. Se crea Usuario local.
4. Se crea UsuarioRol con Administrador del sistema.
5. No se persiste contraseña localmente.
6. No se imprime ni expone contraseña transitoria en salida.
7. Se dispara recuperación/configuración inicial en Auth0.
8. Correo inválido rechazado con CommandError.
9. Usuario local duplicado rechazado (por correo o RUT).
10. Rol Administrador inexistente en base de datos rechazado.
11. Si ya existe Administrador local, comando aborta por defecto.
12. Fallo en Auth0 aborta sin mutar PostgreSQL.
13. Fallo en PostgreSQL dispara compensación en Auth0.
14. Fallo en envío de correo de invitación se maneja controladamente sin revertir la cuenta.
15. Auditoría se registra con acción PRIMER_ADMIN.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError

from usuarios.models import BitacoraAuditoria, Rol, Usuario, UsuarioRol
from usuarios.services import (
    ROL_ADMINISTRADOR,
    Auth0ManagementError,
    AuthRecoverConnectionError,
    DuplicadoUsuarioError,
)

from .helpers import RbacTestBase, crear_mock_usuario


class PrimerAdminCommandTests(RbacTestBase):
    """
    Suite de pruebas para el comando de gestión `primer_admin` y el servicio `bootstrap_primer_admin`.
    """

    def setUp(self):
        super().setUp()
        self.email_valido = "admin.bootstrap@siget.cl"
        self.rut_valido = "11.111.111-1"
        self.rut_normalizado = "11111111-1"
        self.auth0_sub = "auth0|admin_bootstrap_sub_999"

        self.mock_admin_creado = crear_mock_usuario(
            id_usuario=999,
            identificador_externo=self.auth0_sub,
            correo=self.email_valido,
            rut=self.rut_normalizado,
            nombres="Super",
            apellidos="Admin",
        )

    # =========================================================================
    # 1. Creación exitosa y orquestación integral (Puntos 1, 2, 3, 4, 7, 15)
    # =========================================================================

    def test_01_creacion_exitosa_primer_admin(self):
        """
        1. Creación exitosa del primer Administrador del sistema:
        - Se crea identidad Auth0 mediante mock.
        - Se crea Usuario local en PostgreSQL.
        - Se crea UsuarioRol asociando 'Administrador del sistema'.
        - Se dispara solicitar_recuperacion_acceso.
        - Se registra auditoría con acción PRIMER_ADMIN.
        """
        out = StringIO()
        err = StringIO()

        with (
            patch.object(
                UsuarioRol.objects, "filter"
            ) as mock_rol_filter,
            patch.object(Rol.objects, "get", return_value=self.rol_admin),
            patch("usuarios.services.validar_rut_chileno", return_value=self.rut_normalizado),
            patch.object(Usuario.objects, "filter") as mock_user_filter,
            patch(
                "usuarios.services.crear_usuario_auth0",
                return_value={"user_id": self.auth0_sub},
            ) as mock_auth0_crear,
            patch.object(
                Usuario.objects, "create", return_value=self.mock_admin_creado
            ) as mock_user_create,
            patch.object(UsuarioRol.objects, "create") as mock_rol_create,
            patch.object(BitacoraAuditoria.objects, "create") as mock_audit_create,
            patch(
                "usuarios.services.solicitar_recuperacion_acceso", return_value=True
            ) as mock_invitacion,
        ):
            # No existen administradores previos ni usuarios duplicados
            mock_rol_filter.return_value.exists.return_value = False
            mock_user_filter.return_value.exists.return_value = False

            call_command(
                "primer_admin",
                email=self.email_valido,
                rut=self.rut_valido,
                nombres="Super",
                apellidos="Admin",
                stdout=out,
                stderr=err,
            )

            # 2. Verifica creación en Auth0
            mock_auth0_crear.assert_called_once_with(
                email=self.email_valido,
                password=None,
                nombres="Super",
                apellidos="Admin",
            )

            # 3. Verifica persistencia en PostgreSQL
            mock_user_create.assert_called_once_with(
                identificador_externo=self.auth0_sub,
                proveedor_identidad="Auth0",
                rut=self.rut_normalizado,
                nombres="Super",
                apellidos="Admin",
                correo=self.email_valido,
                activo=True,
            )

            # 4. Verifica rol Administrador asignado
            mock_rol_create.assert_called_once_with(
                usuario=self.mock_admin_creado,
                rol=self.rol_admin,
            )

            # 7. Verifica disparo de recuperación/configuración de contraseña
            mock_invitacion.assert_called_once_with(self.email_valido)

            # 15. Verifica auditoría registrada
            mock_audit_create.assert_called_once()
            audit_kwargs = mock_audit_create.call_args[1]
            self.assertEqual(audit_kwargs["modulo"], "USUARIOS")
            self.assertEqual(audit_kwargs["accion"], "PRIMER_ADMIN")
            self.assertEqual(audit_kwargs["id_usuario"], self.mock_admin_creado)
            self.assertEqual(audit_kwargs["id_registro_afectado"], 999)

            output = out.getvalue()
            self.assertIn("Primer Administrador creado correctamente.", output)
            self.assertIn(self.email_valido, output)
            self.assertIn(ROL_ADMINISTRADOR, output)
            self.assertIn("Se solicitó el envío del correo", output)

    # =========================================================================
    # 2. Seguridad de Credenciales (Puntos 5 y 6)
    # =========================================================================

    def test_02_no_se_persiste_contrasena_localmente(self):
        """
        5. El modelo Usuario de PostgreSQL no tiene campo password y no se persiste credencial.
        """
        self.assertFalse(hasattr(Usuario, "password"))

    def test_03_no_se_imprime_contrasena_ni_secretos(self):
        """
        6. La salida del comando jamás muestra la contraseña transitoria, tokens ni secrets.
        """
        out = StringIO()
        err = StringIO()

        with (
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
            patch.object(Rol.objects, "get", return_value=self.rol_admin),
            patch("usuarios.services.validar_rut_chileno", return_value=self.rut_normalizado),
            patch.object(Usuario.objects, "filter") as mock_user_filter,
            patch(
                "usuarios.services.crear_usuario_auth0",
                return_value={"user_id": self.auth0_sub},
            ),
            patch.object(Usuario.objects, "create", return_value=self.mock_admin_creado),
            patch.object(UsuarioRol.objects, "create"),
            patch.object(BitacoraAuditoria.objects, "create"),
            patch("usuarios.services.solicitar_recuperacion_acceso", return_value=True),
        ):
            mock_rol_filter.return_value.exists.return_value = False
            mock_user_filter.return_value.exists.return_value = False

            call_command(
                "primer_admin",
                email=self.email_valido,
                rut=self.rut_valido,
                stdout=out,
                stderr=err,
            )

            full_output = out.getvalue() + err.getvalue()
            self.assertNotIn("password", full_output.lower())
            self.assertNotIn("secret", full_output.lower())
            self.assertNotIn("token", full_output.lower())
            self.assertNotIn("Siget_", full_output)

    # =========================================================================
    # 3. Validaciones Previas (Puntos 8, 9, 10, 11)
    # =========================================================================

    def test_04_correo_invalido_es_rechazado(self):
        """
        8. Si el correo tiene un formato inválido (sin @ o dominio), se rechaza con CommandError.
        """
        with (
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
            patch.object(Rol.objects, "get", return_value=self.rol_admin),
        ):
            mock_rol_filter.return_value.exists.return_value = False

            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "primer_admin",
                    email="correo_invalido",
                    rut=self.rut_valido,
                )
            self.assertIn("formato del correo electrónico es inválido", str(ctx.exception))

    def test_05_rut_invalido_es_rechazado(self):
        """
        Valida que un RUT con dígito verificador inválido lance CommandError.
        """
        with (
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
            patch.object(Rol.objects, "get", return_value=self.rol_admin),
        ):
            mock_rol_filter.return_value.exists.return_value = False

            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "primer_admin",
                    email=self.email_valido,
                    rut="11.111.111-9",  # DV incorrecto
                )
            self.assertIn("Dígito verificador inválido", str(ctx.exception))

    def test_06_usuario_local_duplicado_correo_es_rechazado(self):
        """
        9. Si ya existe un Usuario local con el mismo correo, se rechaza.
        """
        with (
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
            patch.object(Rol.objects, "get", return_value=self.rol_admin),
            patch("usuarios.services.validar_rut_chileno", return_value=self.rut_normalizado),
            patch.object(Usuario.objects, "filter") as mock_user_filter,
        ):
            mock_rol_filter.return_value.exists.return_value = False
            # Simula que existe por correo
            mock_user_filter.return_value.exists.side_effect = [True, False]

            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "primer_admin",
                    email=self.email_valido,
                    rut=self.rut_valido,
                )
            self.assertIn("Ya existe un usuario registrado con el correo", str(ctx.exception))

    def test_07_usuario_local_duplicado_rut_es_rechazado(self):
        """
        9b. Si ya existe un Usuario local con el mismo RUT, se rechaza.
        """
        with (
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
            patch.object(Rol.objects, "get", return_value=self.rol_admin),
            patch("usuarios.services.validar_rut_chileno", return_value=self.rut_normalizado),
            patch.object(Usuario.objects, "filter") as mock_user_filter,
        ):
            mock_rol_filter.return_value.exists.return_value = False
            # Correo no duplicado, RUT duplicado
            mock_user_filter.return_value.exists.side_effect = [False, True]

            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "primer_admin",
                    email=self.email_valido,
                    rut=self.rut_valido,
                )
            self.assertIn("Ya existe un usuario registrado con el RUT", str(ctx.exception))

    def test_08_rol_administrador_inexistente_es_rechazado(self):
        """
        10. Si el rol 'Administrador del sistema' no existe en la base de datos, aborta.
        """
        with (
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
            patch.object(Rol.objects, "get", side_effect=Rol.DoesNotExist),
        ):
            mock_rol_filter.return_value.exists.return_value = False

            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "primer_admin",
                    email=self.email_valido,
                    rut=self.rut_valido,
                )
            self.assertIn("no existe en la base de datos", str(ctx.exception))

    def test_09_si_ya_existe_administrador_comando_aborta(self):
        """
        11. Si ya existe al menos un usuario con rol 'Administrador del sistema',
        el comando aborta inmediatamente indicando que está destinado únicamente al bootstrap inicial.
        """
        with patch.object(UsuarioRol.objects, "filter") as mock_rol_filter:
            mock_rol_filter.return_value.exists.return_value = True

            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "primer_admin",
                    email=self.email_valido,
                    rut=self.rut_valido,
                )

            self.assertIn(
                "Ya existe al menos un Administrador del sistema. El comando primer_admin está destinado únicamente al bootstrap inicial.",
                str(ctx.exception),
            )

    # =========================================================================
    # 4. Fallos y Consistencia Distribuida (Puntos 12, 13, 14)
    # =========================================================================

    def test_10_fallo_auth0_no_muta_postgresql(self):
        """
        12. Si Auth0 falla al crear la identidad externa, no se inserta ningún registro en PostgreSQL.
        """
        with (
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
            patch.object(Rol.objects, "get", return_value=self.rol_admin),
            patch("usuarios.services.validar_rut_chileno", return_value=self.rut_normalizado),
            patch.object(Usuario.objects, "filter") as mock_user_filter,
            patch(
                "usuarios.services.crear_usuario_auth0",
                side_effect=Auth0ManagementError("Auth0 API no disponible"),
            ),
            patch.object(Usuario.objects, "create") as mock_user_create,
            patch.object(UsuarioRol.objects, "create") as mock_rol_create,
        ):
            mock_rol_filter.return_value.exists.return_value = False
            mock_user_filter.return_value.exists.return_value = False

            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "primer_admin",
                    email=self.email_valido,
                    rut=self.rut_valido,
                )

            self.assertIn("Auth0 API no disponible", str(ctx.exception))
            mock_user_create.assert_not_called()
            mock_rol_create.assert_not_called()

    def test_11_fallo_postgresql_dispara_compensacion_auth0(self):
        """
        13. Si Auth0 crea la cuenta pero PostgreSQL falla (DatabaseError),
        se ejecuta la operación compensatoria en Auth0 eliminando la identidad externa.
        """
        with (
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
            patch.object(Rol.objects, "get", return_value=self.rol_admin),
            patch("usuarios.services.validar_rut_chileno", return_value=self.rut_normalizado),
            patch.object(Usuario.objects, "filter") as mock_user_filter,
            patch(
                "usuarios.services.crear_usuario_auth0",
                return_value={"user_id": self.auth0_sub},
            ),
            patch.object(
                Usuario.objects, "create", side_effect=DatabaseError("Fallo de conexión SQL")
            ),
            patch("usuarios.services.eliminar_usuario_auth0") as mock_compensacion,
        ):
            mock_rol_filter.return_value.exists.return_value = False
            mock_user_filter.return_value.exists.return_value = False

            with self.assertRaises(CommandError) as ctx:
                call_command(
                    "primer_admin",
                    email=self.email_valido,
                    rut=self.rut_valido,
                )

            self.assertIn("Se revirtió la cuenta en Auth0", str(ctx.exception))
            mock_compensacion.assert_called_once_with(self.auth0_sub)

    def test_12_fallo_correo_no_revierte_cuenta_y_muestra_advertencia(self):
        """
        14. Si el envío del correo de configuración de contraseña falla:
        - La cuenta en Auth0 y PostgreSQL NO se revierte (consistencia lograda).
        - No se dispara compensación.
        - Se informa claramente que la cuenta fue creada pero el correo no pudo despacharse.
        """
        out = StringIO()
        err = StringIO()

        with (
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
            patch.object(Rol.objects, "get", return_value=self.rol_admin),
            patch("usuarios.services.validar_rut_chileno", return_value=self.rut_normalizado),
            patch.object(Usuario.objects, "filter") as mock_user_filter,
            patch(
                "usuarios.services.crear_usuario_auth0",
                return_value={"user_id": self.auth0_sub},
            ),
            patch.object(Usuario.objects, "create", return_value=self.mock_admin_creado),
            patch.object(UsuarioRol.objects, "create"),
            patch.object(BitacoraAuditoria.objects, "create"),
            patch(
                "usuarios.services.solicitar_recuperacion_acceso",
                side_effect=AuthRecoverConnectionError("Timeout de red en Auth0"),
            ),
            patch("usuarios.services.eliminar_usuario_auth0") as mock_compensacion,
        ):
            mock_rol_filter.return_value.exists.return_value = False
            mock_user_filter.return_value.exists.return_value = False

            # El comando finaliza exitosamente respecto a la creación del usuario
            call_command(
                "primer_admin",
                email=self.email_valido,
                rut=self.rut_valido,
                stdout=out,
                stderr=err,
            )

            # No se revierte
            mock_compensacion.assert_not_called()

            output = out.getvalue()
            self.assertIn("Primer Administrador creado correctamente.", output)
            self.assertIn("Advertencia: No se pudo solicitar el correo", output)

    def test_13_valores_por_defecto_nombres_y_apellidos(self):
        """
        Verifica que si no se pasan nombres ni apellidos, se apliquen los valores por defecto
        'Administrador' y 'del Sistema'.
        """
        with (
            patch.object(UsuarioRol.objects, "filter") as mock_rol_filter,
            patch.object(Rol.objects, "get", return_value=self.rol_admin),
            patch("usuarios.services.validar_rut_chileno", return_value=self.rut_normalizado),
            patch.object(Usuario.objects, "filter") as mock_user_filter,
            patch(
                "usuarios.services.crear_usuario_auth0",
                return_value={"user_id": self.auth0_sub},
            ) as mock_auth0_crear,
            patch.object(
                Usuario.objects, "create", return_value=self.mock_admin_creado
            ) as mock_user_create,
            patch.object(UsuarioRol.objects, "create"),
            patch.object(BitacoraAuditoria.objects, "create"),
            patch("usuarios.services.solicitar_recuperacion_acceso", return_value=True),
        ):
            mock_rol_filter.return_value.exists.return_value = False
            mock_user_filter.return_value.exists.return_value = False

            call_command(
                "primer_admin",
                email=self.email_valido,
                rut=self.rut_valido,
            )

            mock_auth0_crear.assert_called_once_with(
                email=self.email_valido,
                password=None,
                nombres="Administrador",
                apellidos="del Sistema",
            )
            _, create_kwargs = mock_user_create.call_args
            self.assertEqual(create_kwargs["nombres"], "Administrador")
            self.assertEqual(create_kwargs["apellidos"], "del Sistema")
