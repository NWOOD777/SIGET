"""
Pruebas unitarias para Aprovisionamiento de Usuarios y consistencia Auth0/PostgreSQL (E1-H3).
Cubre validaciones de formato, validación de RUT (módulo 11), detección de duplicados,
creación de identidades externas en Auth0, vinculación en PostgreSQL, registro en
bitacora_auditoria y ejecución de transacción compensatoria ante fallos parciales.
"""

from unittest.mock import MagicMock, patch

from django.db import DatabaseError

from usuarios.models import BitacoraAuditoria, Rol, Usuario, UsuarioRol
from usuarios.services import (
    ROL_TECNICO,
    AccesoDenegadoError,
    AprovisionamientoError,
    Auth0ManagementError,
    AuthRecoverConnectionError,
    DuplicadoUsuarioError,
    ErrorAprovisionamientoPostgreSQLError,
    RolNoEncontradoError,
    aprovisionar_usuario,
    crear_usuario_auth0,
    generar_password_transitoria,
    solicitar_recuperacion_acceso,
    validar_rut_chileno,
)

from .helpers import RbacTestBase, crear_mock_usuario


class AprovisionamientoE1H3Tests(RbacTestBase):
    """
    Suite de pruebas del servicio de aprovisionamiento administrativo y consistencia externa.
    """

    def setUp(self):
        super().setUp()
        self.datos_validos = {
            "nombres": "Nicolás",
            "apellidos": "Madariaga",
            "correo": "n.madariaga@duocuc.cl",
            "rut": "18.234.567-8",
            "rol": ROL_TECNICO,
        }

    # =========================================================================
    # 1. Validación de RUT chileno (Módulo 11)
    # =========================================================================

    def test_01_rut_valido_normaliza_correctamente(self):
        """
        1. RUT con formato válido y DV correcto se normaliza sin puntos y con guión.
        """
        # 18.234.567-8 es válido
        # Calculo DV para 18234567:
        # 7*2 + 6*3 + 5*4 + 4*5 + 3*6 + 2*7 + 8*2 + 1*3 = 14+18+20+20+18+14+16+3 = 123
        # 123 % 11 = 2 -> 11 - 2 = 9 (esperado 9).
        self.assertEqual(validar_rut_chileno("11.111.111-1"), "11111111-1")
        self.assertEqual(validar_rut_chileno("11.111.112-K"), "11111112-K")
        self.assertEqual(validar_rut_chileno("11111112k"), "11111112-K")

    def test_02_rut_invalido_formato_o_dv_es_rechazado(self):
        """
        2. RUT con formato inválido o dígito verificador incorrecto lanza ValueError.
        """
        with self.assertRaises(ValueError) as ctx:
            validar_rut_chileno("11.111.111-9")  # DV incorrecto (debe ser K)
        self.assertIn("Dígito verificador inválido", str(ctx.exception))

        with self.assertRaises(ValueError):
            validar_rut_chileno("abc-1")

        with self.assertRaises(ValueError):
            validar_rut_chileno("")

    # =========================================================================
    # 2. Control de Acceso RBAC en Aprovisionamiento
    # =========================================================================

    def test_03_aprovisionamiento_falla_si_ejecutor_no_es_administrador(self):
        """
        3. Solo el Administrador del sistema puede aprovisionar.
        Usuario solicitante y Técnico de soporte son rechazados con AccesoDenegadoError.
        """
        with patch("usuarios.services.es_administrador", return_value=False):
            with self.assertRaises(AccesoDenegadoError) as ctx:
                aprovisionar_usuario(self.tecnico_user, self.datos_validos)
            self.assertIn(
                "exclusivo para el Administrador del sistema", str(ctx.exception)
            )

        with patch("usuarios.services.es_administrador", return_value=False):
            with self.assertRaises(AccesoDenegadoError):
                aprovisionar_usuario(self.solicitante_user, self.datos_validos)

    def test_04_aprovisionamiento_falla_si_admin_es_nulo(self):
        """
        4. Si no se proporciona usuario ejecutor, se deniega la operación.
        """
        with self.assertRaises(AccesoDenegadoError):
            aprovisionar_usuario(None, self.datos_validos)

    # =========================================================================
    # 3. Validación de Campos Obligatorios y Roles
    # =========================================================================

    def test_05_aprovisionamiento_falla_si_faltan_campos_obligatorios(self):
        """
        5. Faltar nombres, apellidos, correo, rut o rol genera AprovisionamientoError.
        """
        datos_incompletos = dict(self.datos_validos)
        datos_incompletos["correo"] = ""

        with patch("usuarios.services.es_administrador", return_value=True):
            with self.assertRaises(AprovisionamientoError) as ctx:
                aprovisionar_usuario(self.admin_user, datos_incompletos)
            self.assertIn("correo' es obligatorio", str(ctx.exception))

    def test_06_aprovisionamiento_falla_si_formato_correo_invalido(self):
        """
        6. Correo sin '@' o con espacios es rechazado.
        """
        datos_correo_invalido = dict(self.datos_validos)
        datos_correo_invalido["correo"] = "correo-invalido-sin-arroba"

        with patch("usuarios.services.es_administrador", return_value=True):
            with self.assertRaises(AprovisionamientoError) as ctx:
                aprovisionar_usuario(self.admin_user, datos_correo_invalido)
            self.assertIn("formato del correo", str(ctx.exception))

    def test_07_aprovisionamiento_falla_si_rol_no_es_oficial(self):
        """
        7. Rol no perteneciente a ROLES_OFICIALES genera RolNoEncontradoError.
        """
        datos_rol_invalido = dict(self.datos_validos)
        datos_rol_invalido["rol"] = "Superusuario Inventado"

        with patch("usuarios.services.es_administrador", return_value=True):
            with self.assertRaises(RolNoEncontradoError) as ctx:
                aprovisionar_usuario(self.admin_user, datos_rol_invalido)
            self.assertIn("no es un rol oficial válido", str(ctx.exception))

    # =========================================================================
    # 4. Detección de Duplicados en PostgreSQL
    # =========================================================================

    def test_08_aprovisionamiento_falla_si_correo_duplicado_en_postgresql(self):
        """
        8. Si el correo ya existe en PostgreSQL, se rechaza sin consultar Auth0.
        """
        with (
            patch("usuarios.services.es_administrador", return_value=True),
            patch.object(Rol.objects, "get", return_value=self.rol_tecnico),
            patch("usuarios.services.validar_rut_chileno", return_value="11111111-K"),
            patch.object(Usuario.objects, "filter") as mock_filter,
            patch("usuarios.services.crear_usuario_auth0") as mock_auth0,
        ):
            mock_filter.return_value.exists.return_value = True

            with self.assertRaises(DuplicadoUsuarioError) as ctx:
                aprovisionar_usuario(self.admin_user, self.datos_validos)

            self.assertIn(
                "Ya existe un usuario registrado con el correo", str(ctx.exception)
            )
            mock_auth0.assert_not_called()

    def test_09_aprovisionamiento_falla_si_rut_duplicado_en_postgresql(self):
        """
        9. Si el RUT ya existe en PostgreSQL, se rechaza con DuplicadoUsuarioError.
        """
        with (
            patch("usuarios.services.es_administrador", return_value=True),
            patch.object(Rol.objects, "get", return_value=self.rol_tecnico),
            patch("usuarios.services.validar_rut_chileno", return_value="11111111-K"),
            patch.object(Usuario.objects, "filter") as mock_filter,
            patch("usuarios.services.crear_usuario_auth0") as mock_auth0,
        ):
            # Primera llamada para correo=False, segunda para rut=True
            mock_filter.return_value.exists.side_effect = [False, True]

            with self.assertRaises(DuplicadoUsuarioError) as ctx:
                aprovisionar_usuario(self.admin_user, self.datos_validos)

            self.assertIn(
                "Ya existe un usuario registrado con el RUT", str(ctx.exception)
            )
            mock_auth0.assert_not_called()

    # =========================================================================
    # 5. Flujo Exitoso (Happy Path) y Auditoría
    # =========================================================================

    def test_10_aprovisionamiento_exitoso_crea_identidad_en_auth0_y_postgresql(self):
        """
        10. Flujo exitoso:
        - Crea identidad en Auth0 mediante Management API.
        - Persiste Usuario en PostgreSQL vinculando 'identificador_externo' con sub de Auth0.
        - No almacena contraseñas en PostgreSQL.
        - Asigna rol inicial mediante UsuarioRol.
        - Registra evento en bitacora_auditoria.
        """
        auth0_mock_resp = {
            "user_id": "auth0|64f0a9b8c1234567890",
            "email": "n.madariaga@duocuc.cl",
            "name": "Nicolás Madariaga",
        }
        nuevo_usuario_mock = crear_mock_usuario(
            id_usuario=99,
            identificador_externo="auth0|64f0a9b8c1234567890",
            correo="n.madariaga@duocuc.cl",
            rut="11111111-K",
            nombres="Nicolás",
            apellidos="Madariaga",
        )

        with (
            patch("usuarios.services.es_administrador", return_value=True),
            patch.object(Rol.objects, "get", return_value=self.rol_tecnico),
            patch("usuarios.services.validar_rut_chileno", return_value="11111111-K"),
            patch.object(Usuario.objects, "filter") as mock_filter,
            patch(
                "usuarios.services.crear_usuario_auth0", return_value=auth0_mock_resp
            ) as mock_auth0,
            patch.object(
                Usuario.objects, "create", return_value=nuevo_usuario_mock
            ) as mock_user_create,
            patch.object(UsuarioRol.objects, "create") as mock_rol_create,
            patch.object(BitacoraAuditoria.objects, "create") as mock_audit_create,
            patch(
                "usuarios.services.solicitar_recuperacion_acceso", return_value=True
            ) as mock_invitacion,
        ):
            mock_filter.return_value.exists.return_value = False

            usuario_creado = aprovisionar_usuario(
                admin_usuario=self.admin_user,
                datos=self.datos_validos,
                direccion_ip="192.168.1.100",
            )

            self.assertEqual(usuario_creado.id_usuario, 99)
            self.assertEqual(
                usuario_creado.identificador_externo, "auth0|64f0a9b8c1234567890"
            )

            # Verifica creación en Auth0
            mock_auth0.assert_called_once_with(
                email="n.madariaga@duocuc.cl",
                password=None,
                nombres="Nicolás",
                apellidos="Madariaga",
            )

            # Verifica persistencia en PostgreSQL
            mock_user_create.assert_called_once_with(
                identificador_externo="auth0|64f0a9b8c1234567890",
                proveedor_identidad="Auth0",
                rut="11111111-K",
                nombres="Nicolás",
                apellidos="Madariaga",
                correo="n.madariaga@duocuc.cl",
                activo=True,
            )

            # Verifica rol asignado
            mock_rol_create.assert_called_once_with(
                usuario=nuevo_usuario_mock,
                rol=self.rol_tecnico,
            )

            # Verifica registro en bitacora_auditoria
            mock_audit_create.assert_called_once()
            audit_kwargs = mock_audit_create.call_args[1]
            self.assertEqual(audit_kwargs["modulo"], "USUARIOS")
            self.assertEqual(audit_kwargs["accion"], "APROVISIONAR_USUARIO")
            self.assertEqual(audit_kwargs["id_usuario"], self.admin_user)
            self.assertEqual(audit_kwargs["direccion_ip"], "192.168.1.100")

            # Verifica disparo de invitación inicial al correo del usuario
            mock_invitacion.assert_called_once_with("n.madariaga@duocuc.cl")

    # =========================================================================
    # 6. Manejo de Fallos y Transacción Compensatoria
    # =========================================================================

    def test_11_error_en_auth0_aborta_sin_persistir_en_postgresql(self):
        """
        11. Si Auth0 falla al crear la identidad (ej: error 502/timeout),
        el servicio lanza Auth0ManagementError y no persiste nada en PostgreSQL.
        """
        with (
            patch("usuarios.services.es_administrador", return_value=True),
            patch.object(Rol.objects, "get", return_value=self.rol_tecnico),
            patch("usuarios.services.validar_rut_chileno", return_value="11111111-K"),
            patch.object(Usuario.objects, "filter") as mock_filter,
            patch(
                "usuarios.services.crear_usuario_auth0",
                side_effect=Auth0ManagementError("Auth0 indisponible"),
            ),
            patch.object(Usuario.objects, "create") as mock_user_create,
            patch.object(UsuarioRol.objects, "create") as mock_rol_create,
        ):
            mock_filter.return_value.exists.return_value = False

            with self.assertRaises(Auth0ManagementError):
                aprovisionar_usuario(self.admin_user, self.datos_validos)

            mock_user_create.assert_not_called()
            mock_rol_create.assert_not_called()

    def test_12_operacion_compensatoria_revierte_auth0_si_postgresql_falla(self):
        """
        12. ESCENARIO CRÍTICO DE CONSISTENCIA DISTRIBUIDA:
        1. Auth0 crea la cuenta externamente (user_id = 'auth0|test_comp_123').
        2. PostgreSQL falla al guardar el registro (DatabaseError).
        3. El sistema ejecuta la OPERACIÓN COMPENSATORIA eliminando la cuenta en Auth0.
        4. Lanza ErrorAprovisionamientoPostgreSQLError controlado.
        """
        auth0_mock_resp = {"user_id": "auth0|test_comp_123"}

        with (
            patch("usuarios.services.es_administrador", return_value=True),
            patch.object(Rol.objects, "get", return_value=self.rol_tecnico),
            patch("usuarios.services.validar_rut_chileno", return_value="11111111-K"),
            patch.object(Usuario.objects, "filter") as mock_filter,
            patch(
                "usuarios.services.crear_usuario_auth0", return_value=auth0_mock_resp
            ),
            patch.object(
                Usuario.objects,
                "create",
                side_effect=DatabaseError("Fallo de conexión a PostgreSQL"),
            ),
            patch("usuarios.services.eliminar_usuario_auth0") as mock_compensacion,
        ):
            mock_filter.return_value.exists.return_value = False

            with self.assertRaises(ErrorAprovisionamientoPostgreSQLError) as ctx:
                aprovisionar_usuario(self.admin_user, self.datos_validos)

            self.assertIn("Se revirtió la cuenta en Auth0", str(ctx.exception))
            # Comprueba que la operación compensatoria fue invocada con el ID externo
            mock_compensacion.assert_called_once_with("auth0|test_comp_123")

    # =========================================================================
    # 7. Credenciales Iniciales e Invitación de Primer Acceso (E1-H3)
    # =========================================================================

    def test_13_password_transitoria_aleatoria_segura_no_persistida_ni_expuesta(self):
        """
        13. La contraseña técnica inicial:
        - Es aleatoria y de alta entropía generada criptográficamente con secrets.
        - Cumple con requisitos de complejidad (longitud >= 25, mayúsculas, minúsculas, dígitos, símbolos).
        - Genera valores distintos en cada invocación.
        - El modelo Usuario de PostgreSQL NO almacena contraseñas (campo inexistente).
        """
        passwords = [generar_password_transitoria() for _ in range(10)]
        self.assertEqual(len(set(passwords)), 10, "Cada contraseña transitoria debe ser única.")

        for pwd in passwords:
            self.assertGreaterEqual(len(pwd), 25)
            self.assertTrue(any(c.isupper() for c in pwd), "Debe contener mayúsculas")
            self.assertTrue(any(c.islower() for c in pwd), "Debe contener minúsculas")
            self.assertTrue(any(c.isdigit() for c in pwd), "Debe contener dígitos")
            self.assertTrue(any(c in "!@#$%^&*()_+-=" for c in pwd), "Debe contener símbolos")

        # Verificar que el modelo Usuario no tiene campo password
        self.assertFalse(hasattr(Usuario, "password"))

    @patch("usuarios.services.requests.post")
    @patch("usuarios.services.obtener_token_management_api", return_value="mock_mgmt_token")
    def test_14_creacion_auth0_asigna_app_metadata_invitacion_pendiente(
        self, mock_token, mock_post
    ):
        """
        14. Al invocar crear_usuario_auth0, el payload enviado a POST /api/v2/users:
        - Incluye app_metadata: {'invitacion_pendiente': True}.
        - Incluye una contraseña técnica transitoria.
        - Incluye email_verified=True y user_metadata con nombres/apellidos.
        """
        mock_resp = MagicMock(ok=True, status_code=201)
        mock_resp.json.return_value = {
            "user_id": "auth0|user_test_metadata",
            "email": "test.meta@duocuc.cl",
        }
        mock_post.return_value = mock_resp

        resultado = crear_usuario_auth0(
            email="test.meta@duocuc.cl",
            nombres="Meta",
            apellidos="Test",
        )

        self.assertEqual(resultado["user_id"], "auth0|user_test_metadata")
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]

        self.assertEqual(payload["email"], "test.meta@duocuc.cl")
        self.assertTrue(payload["email_verified"])
        self.assertEqual(
            payload["app_metadata"],
            {"invitacion_pendiente": True},
        )
        self.assertEqual(
            payload["user_metadata"],
            {"nombres": "Meta", "apellidos": "Test"},
        )
        self.assertIn("password", payload)
        self.assertGreaterEqual(len(payload["password"]), 20)

    def test_15_aprovisionamiento_inicia_flujo_invitacion_configurar_contrasena(self):
        """
        15. El flujo completo de aprovisionamiento invoca automáticamente
        solicitar_recuperacion_acceso(correo) para disparar el correo de configuración.
        """
        auth0_mock_resp = {"user_id": "auth0|test_invitacion_flow"}
        nuevo_usuario_mock = crear_mock_usuario(
            id_usuario=101,
            identificador_externo="auth0|test_invitacion_flow",
            correo="n.madariaga@duocuc.cl",
            rut="11111111-K",
            nombres="Nicolás",
            apellidos="Madariaga",
        )

        with (
            patch("usuarios.services.es_administrador", return_value=True),
            patch.object(Rol.objects, "get", return_value=self.rol_tecnico),
            patch("usuarios.services.validar_rut_chileno", return_value="11111111-K"),
            patch.object(Usuario.objects, "filter") as mock_filter,
            patch(
                "usuarios.services.crear_usuario_auth0", return_value=auth0_mock_resp
            ),
            patch.object(Usuario.objects, "create", return_value=nuevo_usuario_mock),
            patch.object(UsuarioRol.objects, "create"),
            patch.object(BitacoraAuditoria.objects, "create"),
            patch("usuarios.services.solicitar_recuperacion_acceso") as mock_invitacion,
        ):
            mock_filter.return_value.exists.return_value = False

            usuario = aprovisionar_usuario(self.admin_user, self.datos_validos)

            self.assertEqual(usuario.id_usuario, 101)
            mock_invitacion.assert_called_once_with("n.madariaga@duocuc.cl")

    def test_16_fallo_en_inicio_invitacion_manejado_controladamente(self):
        """
        16. Si solicitar_recuperacion_acceso falla (ej. timeout o error de red de Auth0):
        - La cuenta en PostgreSQL y Auth0 NO se revierte (el aprovisionamiento ya fue consistente).
        - La excepción se captura y registra en log de advertencia en forma controlada.
        - aprovisionar_usuario retorna el usuario creado sin lanzar excepción no controlada.
        - No se invoca la operación compensatoria (eliminar_usuario_auth0).
        """
        auth0_mock_resp = {"user_id": "auth0|test_error_mail_ok"}
        nuevo_usuario_mock = crear_mock_usuario(
            id_usuario=102,
            identificador_externo="auth0|test_error_mail_ok",
            correo="n.madariaga@duocuc.cl",
            rut="11111111-K",
            nombres="Nicolás",
            apellidos="Madariaga",
        )

        with (
            patch("usuarios.services.es_administrador", return_value=True),
            patch.object(Rol.objects, "get", return_value=self.rol_tecnico),
            patch("usuarios.services.validar_rut_chileno", return_value="11111111-K"),
            patch.object(Usuario.objects, "filter") as mock_filter,
            patch(
                "usuarios.services.crear_usuario_auth0", return_value=auth0_mock_resp
            ),
            patch.object(Usuario.objects, "create", return_value=nuevo_usuario_mock),
            patch.object(UsuarioRol.objects, "create"),
            patch.object(BitacoraAuditoria.objects, "create"),
            patch(
                "usuarios.services.solicitar_recuperacion_acceso",
                side_effect=AuthRecoverConnectionError("Error de red simulado"),
            ),
            patch("usuarios.services.eliminar_usuario_auth0") as mock_compensacion,
            patch("usuarios.services.logger.warning") as mock_log_warning,
        ):
            mock_filter.return_value.exists.return_value = False

            # No debe propagar la excepción hacia arriba
            usuario = aprovisionar_usuario(self.admin_user, self.datos_validos)

            self.assertEqual(usuario.id_usuario, 102)
            mock_compensacion.assert_not_called()
            mock_log_warning.assert_called_once()
            log_args = mock_log_warning.call_args[0]
            self.assertIn("no se pudo enviar el correo de invitación", log_args[0])

    @patch("usuarios.services.requests.post")
    def test_17_recuperacion_posterior_no_se_confunde_con_invitacion_inicial(
        self, mock_post
    ):
        """
        17. El flujo de recuperación posterior de contraseña (E1-H2) reutiliza
        solicitar_recuperacion_acceso sin alterar app_metadata.
        La diferenciación de contenido ('Configure su contraseña' vs 'Restablezca su contraseña')
        recae en el template de correo condicionado por app_metadata.invitacion_pendiente,
        el cual es desactivado por la Action Post-Login tras el primer acceso.
        """
        mock_resp = MagicMock(ok=True, status_code=200)
        mock_post.return_value = mock_resp

        resultado = solicitar_recuperacion_acceso("usuario.existente@duocuc.cl")

        self.assertTrue(resultado)
        mock_post.assert_called_once()
        url, kwargs = mock_post.call_args
        self.assertIn("/dbconnections/change_password", url[0])
        payload = kwargs["json"]
        self.assertEqual(payload["email"], "usuario.existente@duocuc.cl")
        # No se transmiten secretos ni metadatos en la Authentication API pública
        self.assertNotIn("client_secret", payload)
        self.assertNotIn("app_metadata", payload)
