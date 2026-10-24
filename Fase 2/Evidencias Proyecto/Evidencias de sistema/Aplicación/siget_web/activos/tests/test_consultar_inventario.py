
from unittest.mock import patch

from django.db.models import Q

from activos.models import Activo
from activos.views import ActivoListCreateView
from usuarios.services import ROL_TECNICO

from .helpers import (
    ActivosTestBase,
    crear_request_con_sesion,
    obtener_data_list,
)


class ConsultarInventarioTests(ActivosTestBase):
    """Pruebas de consulta de inventario."""

    def consultar(self, parametros=None):
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/",
            usuario_id=2,
            roles=[ROL_TECNICO],
            data=parametros or {},
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
            queryset = mock_sr.return_value.order_by.return_value
            queryset.filter.return_value = queryset
            queryset.__iter__.return_value = [self.activo]
            queryset.__len__.return_value = 1

            response = view(request)

        return response, queryset

    def test_01_listar_inventario(self):
        response, _ = self.consultar()

        self.assertEqual(response.status_code, 200)
        data = obtener_data_list(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["codigo_inventario"], "ACT-0010")

    def test_02_buscar_por_codigo(self):
        response, queryset = self.consultar({"search": "ACT-0010"})

        self.assertEqual(response.status_code, 200)
        queryset.filter.assert_called()
        self.assertTrue(
            any(
                isinstance(call.args[0], Q)
                for call in queryset.filter.call_args_list
            )
        )

    def test_03_buscar_por_numero_de_serie(self):
        response, queryset = self.consultar({"search": "SN-DELL-9999"})

        self.assertEqual(response.status_code, 200)
        queryset.filter.assert_called()

    def test_04_buscar_por_id_numerico(self):
        response, queryset = self.consultar({"search": "10"})

        self.assertEqual(response.status_code, 200)
        queryset.filter.assert_called()

        criterios = queryset.filter.call_args.args[0]
        self.assertIsInstance(criterios, Q)
        self.assertIn(("id_activo", 10), criterios.children)

    def test_05_filtrar_por_categoria(self):
        response, queryset = self.consultar({"tipo": "Notebook"})

        self.assertEqual(response.status_code, 200)
        queryset.filter.assert_called_with(
            id_modelo__id_categoria__nombre__iexact="Notebook"
        )

    def test_06_filtrar_por_ubicacion_nombre(self):
        response, queryset = self.consultar(
            {"ubicacion": "Departamento TI"}
        )

        self.assertEqual(response.status_code, 200)
        queryset.filter.assert_called_with(
            id_ubicacion__nombre_area__iexact="Departamento TI"
        )

    def test_07_filtrar_por_ubicacion_id(self):
        response, queryset = self.consultar({"ubicacion": "1"})

        self.assertEqual(response.status_code, 200)
        queryset.filter.assert_called_with(id_ubicacion__id_ubicacion=1)

    def test_08_filtrar_por_estado(self):
        response, queryset = self.consultar({"estado": "Disponible"})

        self.assertEqual(response.status_code, 200)
        queryset.filter.assert_called_with(
            id_estado_activo__nombre__iexact="Disponible"
        )

    def test_09_combinar_filtros(self):
        response, queryset = self.consultar(
            {
                "search": "Dell",
                "tipo": "Notebook",
                "ubicacion": "1",
                "estado": "Disponible",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(queryset.filter.call_count, 4)

    def test_10_usuario_no_autenticado_recibe_403(self):
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/",
            usuario_id=None,
        )

        view = ActivoListCreateView.as_view()

        with patch(
            "activos.permissions.obtener_usuario_actual",
            return_value=None,
        ):
            response = view(request)

        self.assertEqual(response.status_code, 403)

    def test_11_usuario_sin_rol_ni_permiso_recibe_403(self):
        request = crear_request_con_sesion(
            self.factory,
            "GET",
            "/api/activos/",
            usuario_id=3,
            roles=[],
        )

        view = ActivoListCreateView.as_view()

        with (
            patch(
                "activos.permissions.obtener_usuario_actual",
                return_value=self.solicitante_user,
            ),
            patch("activos.permissions.es_administrador", return_value=False),
            patch("activos.permissions.usuario_tiene_rol", return_value=False),
            patch("activos.permissions.usuario_tiene_permiso", return_value=False),
        ):
            response = view(request)

        self.assertEqual(response.status_code, 403)
