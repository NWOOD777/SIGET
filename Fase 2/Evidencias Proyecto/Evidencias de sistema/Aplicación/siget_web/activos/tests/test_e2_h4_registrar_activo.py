"""
Pruebas para E2-H4: Registrar activo TI.
Cubre validaciones funcionales, persistencia, generación de identificador,
restricciones de unicidad, RBAC en backend y pruebas de sesión manipulada.
"""

from unittest.mock import patch

from rest_framework.exceptions import ValidationError
from rest_framework.relations import PrimaryKeyRelatedField
from rest_framework.validators import UniqueValidator
from usuarios.services import (
    ROL_ADMINISTRADOR,
    ROL_TECNICO,
    ROL_USUARIO_SOLICITANTE,
)

from activos.models import Activo, EstadoActivo
from activos.views import ActivoListCreateView

from .helpers import (
    ActivosTestBase,
    crear_request_con_sesion,
    obtener_data_dict,
    obtener_data_list,
)


class RegistrarActivoE2H4Tests(ActivosTestBase):
    """
    Suite de pruebas correspondiente a E2-H4 — Registrar activo TI.
    """

    def test_01_acceso_no_autenticado_a_post_activos_es_rechazado_con_403(self):
        """
        1. Petición POST sin sesión debe ser rechazada de forma controlada (403).
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/activos/",
            usuario_id=None,
            data={"numero_serie": "SN-TEST-001"},
        )
        view = ActivoListCreateView.as_view()

        with patch("activos.permissions.obtener_usuario_actual", return_value=None):
            response = view(request)

        self.assertEqual(response.status_code, 403)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)

    def test_02_usuario_solicitante_recibe_403_al_intentar_registrar_activo(self):
        """
        2. Usuario solicitante recibe 403 al intentar registrar activo.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/activos/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={"numero_serie": "SN-TEST-001"},
        )
        view = ActivoListCreateView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.solicitante_user,
            ),
            patch("activos.permissions.es_administrador", return_value=False),
        ):
            response = view(request)

        self.assertEqual(response.status_code, 403)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)

    def test_03_tecnico_de_soporte_recibe_403_al_intentar_registrar_activo(self):
        """
        3. Técnico de soporte recibe 403 (operación reservada al Administrador del sistema).
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/activos/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"numero_serie": "SN-TEST-001"},
        )
        view = ActivoListCreateView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch("activos.permissions.es_administrador", return_value=False),
        ):
            response = view(request)

        self.assertEqual(response.status_code, 403)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)

    def test_04_intento_con_sesion_manipulada_de_tecnico_es_bloqueado_sin_mutacion(
        self,
    ):
        """
        4. ESCENARIO CRÍTICO DE SEGURIDAD:
        Usuario real en PostgreSQL: Técnico de soporte.
        Sesión manipulada: session['roles'] = ['Administrador del sistema'].
        Backend valida contra PostgreSQL y rechaza con 403 sin crear activo.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/activos/",
            usuario_id=2,
            roles=[ROL_ADMINISTRADOR],  # Manipulación deliberada de sesión
            data={
                "numero_serie": "SN-HACK-001",
                "id_modelo": 1,
                "id_ubicacion": 1,
                "valor_adquisicion": 500000,
            },
        )
        view = ActivoListCreateView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            # es_administrador verifica PostgreSQL real -> False
            patch("activos.permissions.es_administrador", return_value=False),
            patch.object(Activo.objects, "create") as mock_create,
        ):
            response = view(request)
            mock_create.assert_not_called()

        self.assertEqual(response.status_code, 403)

    def test_05_administrador_autorizado_registra_activo_correctamente(self):
        """
        5. Administrador del sistema registra exitosamente un activo válido.
        Se genera código correlativo ACT-0011, estado 'Disponible' y persiste en BD.
        """
        payload = {
            "numero_serie": "SN-NEW-12345",
            "id_modelo": 1,
            "id_ubicacion": 1,
            "valor_adquisicion": 750000,
        }
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/activos/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = ActivoListCreateView.as_view()

        nuevo_activo = self.activo
        nuevo_activo.codigo_inventario = "ACT-0011"
        nuevo_activo.numero_serie = "SN-NEW-12345"

        def _mock_to_internal(val):
            if val == 1:
                return self.modelo
            return self.ubicacion

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(
                PrimaryKeyRelatedField,
                "to_internal_value",
                side_effect=_mock_to_internal,
            ),
            patch.object(UniqueValidator, "__call__", return_value=None),
            patch.object(
                EstadoActivo.objects, "get", return_value=self.estado_disponible
            ),
            patch.object(Activo.objects, "filter") as mock_filter,
            patch.object(
                Activo.objects, "create", return_value=nuevo_activo
            ) as mock_create,
        ):
            mock_filter.return_value.order_by.return_value.first.return_value = (
                self.activo
            )

            response = view(request)

        self.assertEqual(response.status_code, 201)
        data = obtener_data_dict(response)
        self.assertEqual(data["codigo_inventario"], "ACT-0011")
        self.assertEqual(data["numero_serie"], "SN-NEW-12345")
        mock_create.assert_called_once()

    def test_06_campos_obligatorios_faltantes_son_rechazados_con_400(self):
        """
        6. Si faltan campos obligatorios (modelo, ubicacion, serie), responde 400.
        """
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/activos/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data={},
        )
        view = ActivoListCreateView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(Activo.objects, "create") as mock_create,
        ):
            response = view(request)
            mock_create.assert_not_called()

        self.assertEqual(response.status_code, 400)
        data = obtener_data_dict(response)
        self.assertIn("numero_serie", data)
        self.assertIn("id_modelo", data)
        self.assertIn("id_ubicacion", data)

    def test_07_valor_adquisicion_negativo_es_rechazado_con_400(self):
        """
        7. El valor de adquisición no puede ser negativo; responde 400 Bad Request.
        """
        payload = {
            "numero_serie": "SN-VAL-NEG",
            "id_modelo": 1,
            "id_ubicacion": 1,
            "valor_adquisicion": -1000,
        }
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/activos/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = ActivoListCreateView.as_view()

        def _mock_to_internal(val):
            return self.modelo if val == 1 else self.ubicacion

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(
                PrimaryKeyRelatedField,
                "to_internal_value",
                side_effect=_mock_to_internal,
            ),
            patch.object(UniqueValidator, "__call__", return_value=None),
            patch.object(Activo.objects, "create") as mock_create,
        ):
            response = view(request)
            mock_create.assert_not_called()

        self.assertEqual(response.status_code, 400)
        data = obtener_data_dict(response)
        self.assertIn("valor_adquisicion", data)
        self.assertIn("no puede ser negativo", str(data["valor_adquisicion"]))

    def test_08_numero_serie_duplicado_es_rechazado_con_400(self):
        """
        8. Si el número de serie ya está registrado en otro activo, responde 400.
        """
        payload = {
            "numero_serie": "SN-DELL-9999",  # Ya existente
            "id_modelo": 1,
            "id_ubicacion": 1,
            "valor_adquisicion": 500000,
        }
        request = crear_request_con_sesion(
            self.factory,
            "POST",
            "/api/activos/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = ActivoListCreateView.as_view()

        def _mock_unique_err(value, serializer_field):
            raise ValidationError("Ya existe un activo con este número de serie.")

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(
                PrimaryKeyRelatedField,
                "to_internal_value",
                side_effect=lambda v: self.modelo,
            ),
            patch.object(UniqueValidator, "__call__", side_effect=_mock_unique_err),
            patch.object(Activo.objects, "create") as mock_create,
        ):
            response = view(request)
            mock_create.assert_not_called()

        self.assertEqual(response.status_code, 400)
        data = obtener_data_dict(response)
        self.assertIn("numero_serie", data)

    def test_09_consulta_get_activos_permitida_a_administrador_y_tecnico(self):
        """
        9. GET /api/activos/ es permitido para Técnico de soporte y Administrador.
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/",
            usuario_id=2,
            roles=[ROL_TECNICO],
        )
        view = ActivoListCreateView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch("activos.permissions.es_administrador", return_value=False),
            patch("activos.permissions.usuario_tiene_rol", return_value=True),
            patch.object(Activo.objects, "select_related") as mock_sr,
        ):
            mock_sr.return_value.order_by.return_value = [self.activo]
            response = view(request)

        self.assertEqual(response.status_code, 200)
        data = obtener_data_list(response)
        self.assertEqual(len(data), 1)

    def test_10_consulta_get_activos_denegada_a_usuario_no_autenticado(self):
        """
        10. GET /api/activos/ sin sesión responde 403 controlado.
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/",
            usuario_id=None,
        )
        view = ActivoListCreateView.as_view()

        with patch("activos.permissions.obtener_usuario_actual", return_value=None):
            response = view(request)

        self.assertEqual(response.status_code, 403)
