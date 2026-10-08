"""
Pruebas para E2-H5: Modificar activo TI.
Cubre carga/precarga de datos, actualización de campos permitidos,
protección de campos inmutables, validación de serie excluyendo el propio registro,
restricciones RBAC en backend y prevención de escalada de privilegios con sesión manipulada.
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

from activos.models import Activo
from activos.serializers import ActivoSerializer
from activos.views import ActivoDetailView

from .helpers import (
    ActivosTestBase,
    crear_request_con_sesion,
    obtener_data_dict,
)


class ModificarActivoE2H5Tests(ActivosTestBase):
    """
    Suite de pruebas correspondiente a E2-H5 — Modificar activo TI.
    """

    def test_01_acceso_no_autenticado_a_put_es_rechazado_con_403(self):
        """
        1. Petición PUT sin sesión es rechazada con 403 controlado.
        """
        request = crear_request_con_sesion(
            self.factory,
            "PUT",
            "/api/activos/10/",
            usuario_id=None,
            data={"numero_serie": "SN-EDIT-01"},
        )
        view = ActivoDetailView.as_view()

        with patch("activos.permissions.obtener_usuario_actual", return_value=None):
            response = view(request, pk=10)

        self.assertEqual(response.status_code, 403)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)

    def test_02_usuario_solicitante_recibe_403_al_intentar_modificar_activo(self):
        """
        2. Usuario solicitante recibe 403 al intentar modificar activo.
        """
        request = crear_request_con_sesion(
            self.factory,
            "PUT",
            "/api/activos/10/",
            usuario_id=3,
            roles=[ROL_USUARIO_SOLICITANTE],
            data={"numero_serie": "SN-EDIT-01"},
        )
        view = ActivoDetailView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.solicitante_user,
            ),
            patch("activos.permissions.es_administrador", return_value=False),
        ):
            response = view(request, pk=10)

        self.assertEqual(response.status_code, 403)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)

    def test_03_tecnico_de_soporte_recibe_403_al_intentar_modificar_activo(self):
        """
        3. Técnico de soporte recibe 403 (operación reservada a Administrador del sistema).
        """
        request = crear_request_con_sesion(
            self.factory,
            "PUT",
            "/api/activos/10/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data={"numero_serie": "SN-EDIT-01"},
        )
        view = ActivoDetailView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch("activos.permissions.es_administrador", return_value=False),
        ):
            response = view(request, pk=10)

        self.assertEqual(response.status_code, 403)
        data = obtener_data_dict(response)
        self.assertIn("detail", data)

    def test_04_intento_con_sesion_manipulada_de_tecnico_a_administrador_es_bloqueado(
        self,
    ):
        """
        4. ESCENARIO CRÍTICO DE SEGURIDAD:
        Usuario real en PostgreSQL: Técnico de soporte.
        Sesión manipulada: session['roles'] = ['Administrador del sistema'].
        Backend valida en PostgreSQL y deniega acceso (403), sin mutar el activo.
        """
        request = crear_request_con_sesion(
            self.factory,
            "PUT",
            "/api/activos/10/",
            usuario_id=2,
            roles=[ROL_ADMINISTRADOR],  # Sesión manipulada
            data={"numero_serie": "SN-HACKED"},
        )
        view = ActivoDetailView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch("activos.permissions.es_administrador", return_value=False),
            patch.object(ActivoDetailView, "get_object", return_value=self.activo),
        ):
            response = view(request, pk=10)
            self.activo.save.assert_not_called()

        self.assertEqual(response.status_code, 403)

    def test_05_carga_de_activo_existente_precarga_datos_correctamente(self):
        """
        5. GET /api/activos/10/ por usuario autorizado retorna ficha completa del activo para precargar.
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/10/",
            usuario_id=2,
            roles=[ROL_TECNICO],
        )
        view = ActivoDetailView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.tecnico_user,
            ),
            patch("activos.permissions.es_administrador", return_value=False),
            patch("activos.permissions.usuario_tiene_rol", return_value=True),
            patch.object(ActivoDetailView, "get_object", return_value=self.activo),
        ):
            response = view(request, pk=10)

        self.assertEqual(response.status_code, 200)
        data = obtener_data_dict(response)
        self.assertEqual(data["codigo_inventario"], "ACT-0010")
        self.assertEqual(data["numero_serie"], "SN-DELL-9999")
        self.assertEqual(data["modelo"], "Latitude 5520")

    def test_06_consulta_activo_inexistente_retorna_404(self):
        """
        6. GET a un activo que no existe retorna 404 Not Found con mensaje controlado.
        """
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/999/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
        )
        view = ActivoDetailView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(
                ActivoDetailView, "get_object", side_effect=Activo.DoesNotExist
            ),
        ):
            response = view(request, pk=999)

        self.assertEqual(response.status_code, 404)
        data = obtener_data_dict(response)
        self.assertEqual(data["detail"], "Activo no encontrado.")

    def test_07_administrador_modifica_campos_permitidos_exitosamente(self):
        """
        7. Administrador autorizado modifica campos permitidos y los cambios se persisten.
        """
        payload = {
            "numero_serie": "SN-DELL-ACTUALIZADA",
            "id_modelo": 1,
            "id_ubicacion": 1,
            "id_estado_activo": 1,
            "valor_adquisicion": 920000,
        }
        request = crear_request_con_sesion(
            self.factory,
            "PUT",
            "/api/activos/10/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = ActivoDetailView.as_view()

        activo_actualizado = self.activo
        activo_actualizado.numero_serie = "SN-DELL-ACTUALIZADA"
        activo_actualizado.valor_adquisicion = 920000.00

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(ActivoDetailView, "get_object", return_value=self.activo),
            patch.object(ActivoSerializer, "is_valid", return_value=True),
            patch.object(ActivoSerializer, "save", return_value=activo_actualizado),
        ):
            response = view(request, pk=10)

        self.assertEqual(response.status_code, 200)
        data = obtener_data_dict(response)
        self.assertEqual(data["numero_serie"], "SN-DELL-ACTUALIZADA")

    def test_08_campos_inmutables_estan_protegidos_y_no_se_modifican(self):
        """
        8. Intento de modificar 'codigo_inventario' o 'id_activo' es ignorado por read_only_fields.
        """
        payload = {
            "id_activo": 9999,
            "codigo_inventario": "ACT-HACKEADO",
            "fecha_registro": "1990-01-01T00:00:00Z",
            "numero_serie": "SN-DELL-9999",
            "id_modelo": 1,
            "id_ubicacion": 1,
            "valor_adquisicion": 850000,
        }
        request = crear_request_con_sesion(
            self.factory,
            "PUT",
            "/api/activos/10/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = ActivoDetailView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(ActivoDetailView, "get_object", return_value=self.activo),
            patch.object(ActivoSerializer, "is_valid", return_value=True),
            patch.object(ActivoSerializer, "save", return_value=self.activo),
        ):
            response = view(request, pk=10)

        self.assertEqual(response.status_code, 200)
        # El código de inventario no cambia
        self.assertEqual(self.activo.codigo_inventario, "ACT-0010")
        self.assertEqual(self.activo.id_activo, 10)

    def test_09_mantener_el_mismo_numero_de_serie_en_edicion_es_permitido(self):
        """
        9. Enviar el mismo número de serie del registro actual excluye a sí mismo y es válido.
        """
        payload = {
            "numero_serie": "SN-DELL-9999",  # Mismo que self.activo.numero_serie
            "id_modelo": 1,
            "id_ubicacion": 1,
            "valor_adquisicion": 850000,
        }
        request = crear_request_con_sesion(
            self.factory,
            "PUT",
            "/api/activos/10/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = ActivoDetailView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(ActivoDetailView, "get_object", return_value=self.activo),
            patch.object(ActivoSerializer, "is_valid", return_value=True),
            patch.object(ActivoSerializer, "save", return_value=self.activo),
        ):
            response = view(request, pk=10)

        self.assertEqual(response.status_code, 200)

    def test_10_numero_serie_duplicado_de_otro_activo_es_rechazado_con_400(self):
        """
        10. Modificar hacia un número de serie que pertenece a otro activo es rechazado con 400.
        """
        payload = {
            "numero_serie": "SN-DE-OTRO-EQUIPO",
            "id_modelo": 1,
            "id_ubicacion": 1,
            "valor_adquisicion": 850000,
        }
        request = crear_request_con_sesion(
            self.factory,
            "PUT",
            "/api/activos/10/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = ActivoDetailView.as_view()

        def _mock_unique_err(value, serializer_field):
            raise ValidationError("Ya existe un activo con este número de serie.")

        def _mock_to_internal(val):
            return self.modelo if val == 1 else self.ubicacion

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(ActivoDetailView, "get_object", return_value=self.activo),
            patch.object(
                PrimaryKeyRelatedField,
                "to_internal_value",
                side_effect=_mock_to_internal,
            ),
            patch.object(UniqueValidator, "__call__", side_effect=_mock_unique_err),
        ):
            response = view(request, pk=10)
            self.activo.save.assert_not_called()

        self.assertEqual(response.status_code, 400)
        data = obtener_data_dict(response)
        self.assertIn("numero_serie", data)

    def test_11_valor_adquisicion_negativo_en_modificacion_es_rechazado_con_400(self):
        """
        11. Modificar con valor de adquisición negativo es rechazado con 400 Bad Request.
        """
        payload = {
            "numero_serie": "SN-DELL-9999",
            "id_modelo": 1,
            "id_ubicacion": 1,
            "valor_adquisicion": -99,
        }
        request = crear_request_con_sesion(
            self.factory,
            "PUT",
            "/api/activos/10/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = ActivoDetailView.as_view()

        def _mock_to_internal(val):
            return self.modelo if val == 1 else self.ubicacion

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(ActivoDetailView, "get_object", return_value=self.activo),
            patch.object(
                PrimaryKeyRelatedField,
                "to_internal_value",
                side_effect=_mock_to_internal,
            ),
            patch.object(UniqueValidator, "__call__", return_value=None),
        ):
            response = view(request, pk=10)
            self.activo.save.assert_not_called()

        self.assertEqual(response.status_code, 400)
        data = obtener_data_dict(response)
        self.assertIn("valor_adquisicion", data)

    def test_12_patch_parcial_modifica_solo_campos_enviados(self):
        """
        12. PATCH parcial actualiza solo el campo enviado sin requerir todos los campos obligatorios.
        """
        payload = {
            "valor_adquisicion": 770000,
        }
        request = crear_request_con_sesion(
            self.factory,
            "PATCH",
            "/api/activos/10/",
            usuario_id=1,
            roles=[ROL_ADMINISTRADOR],
            data=payload,
        )
        view = ActivoDetailView.as_view()

        activo_actualizado = self.activo
        activo_actualizado.valor_adquisicion = 770000.00

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.admin_user,
            ),
            patch("activos.permissions.es_administrador", return_value=True),
            patch.object(ActivoDetailView, "get_object", return_value=self.activo),
            patch.object(ActivoSerializer, "is_valid", return_value=True),
            patch.object(ActivoSerializer, "save", return_value=activo_actualizado),
        ):
            response = view(request, pk=10)

        self.assertEqual(response.status_code, 200)
        data = obtener_data_dict(response)
        self.assertEqual(str(data["valor_adquisicion"]), "770000.00")
