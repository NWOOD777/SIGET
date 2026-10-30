from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from rest_framework.response import Response
from rest_framework.test import APIClient


from datetime import date
from decimal import Decimal

from reportes.parque_ti_services import (
    MENSAJE_SIN_ACTIVOS,
    obtener_reporte_parque_ti,
)


class SeguridadParqueTITests(SimpleTestCase):

    def setUp(self):
        self.cliente = APIClient(HTTP_HOST="localhost")
        self.url = reverse("reporte-parque-ti")
        self.parametros = {
            "fecha_inicio": "2026-01-01",
            "fecha_fin": "2026-10-30",
        }

    def test_usuario_no_autenticado(self):
        respuesta = cast(
            Response,
            self.cliente.get(self.url, self.parametros),
        )

        self.assertIn(respuesta.status_code, [401, 403])

    @patch(
        "usuarios.permissions.es_administrador",
        return_value=False,
    )
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_tecnico_no_puede_consultar(
        self,
        mock_usuario_actual,
        mock_es_administrador,
    ):
        mock_usuario_actual.return_value = SimpleNamespace(
            activo=True,
        )

        respuesta = cast(
            Response,
            self.cliente.get(self.url, self.parametros),
        )

        self.assertEqual(respuesta.status_code, 403)
        mock_es_administrador.assert_called_once()

    @patch(
        "usuarios.permissions.usuario_tiene_permiso",
        return_value=False,
    )
    @patch(
        "usuarios.permissions.es_administrador",
        return_value=True,
    )
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_administrador_sin_permiso(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
    ):
        mock_usuario_actual.return_value = SimpleNamespace(
            activo=True,
        )

        respuesta = cast(
            Response,
            self.cliente.get(self.url, self.parametros),
        )

        self.assertEqual(respuesta.status_code, 403)

        mock_tiene_permiso.assert_called_once_with(
            mock_usuario_actual.return_value,
            "REPORTES_CONSULTAR",
        )

    @patch("reportes.views.obtener_reporte_parque_ti")
    @patch(
        "usuarios.permissions.usuario_tiene_permiso",
        return_value=True,
    )
    @patch(
        "usuarios.permissions.es_administrador",
        return_value=True,
    )
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_administrador_autorizado(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
        mock_reporte,
    ):
        mock_usuario_actual.return_value = SimpleNamespace(
            activo=True,
        )

        mock_reporte.return_value = {
            "total_activos": 8,
            "valor_total_adquisicion": "12161221.00",
            "distribucion_estados": [
                {
                    "estado": "Asignado",
                    "cantidad": 1,
                },
                {
                    "estado": "En reparación",
                    "cantidad": 3,
                },
                {
                    "estado": "En revisión",
                    "cantidad": 3,
                },
                {
                    "estado": "Dado de baja",
                    "cantidad": 1,
                },
            ],
            "costos_repuestos": "0.00",
            "incluir_costos": False,
            "sin_resultados": False,
            "mensaje": None,
        }

        respuesta = cast(
            Response,
            self.cliente.get(self.url, self.parametros),
        )

        self.assertEqual(respuesta.status_code, 200)

        self.assertIsNotNone(respuesta.data)

        datos = respuesta.json()

        self.assertEqual(
            datos["total_activos"],
            8,
        )

        self.assertEqual(
            datos["valor_total_adquisicion"],
            "12161221.00",
        )

        mock_reporte.assert_called_once()


class CalculosParqueTITests(SimpleTestCase):

    def setUp(self):
        self.fecha_inicio = date(2026, 1, 1)
        self.fecha_fin = date(2026, 10, 30)

    @patch("reportes.parque_ti_services.Activo.objects.filter")
    def test_total_valorizacion_y_distribucion(self, mock_filtrar):

        activos = mock_filtrar.return_value
        activos.count.return_value = 8
        activos.aggregate.return_value = {"total": Decimal("12161221.00")}

        activos.values.return_value.annotate.return_value.order_by.return_value = [
            {"id_estado_activo__nombre": "Asignado", "cantidad": 1},
            {"id_estado_activo__nombre": "Dado de baja", "cantidad": 1},
            {"id_estado_activo__nombre": "En reparación", "cantidad": 3},
            {"id_estado_activo__nombre": "En revisión", "cantidad": 3},
        ]

        resultado = obtener_reporte_parque_ti(
            self.fecha_inicio,
            self.fecha_fin,
        )

        self.assertEqual(resultado["total_activos"], 8)
        self.assertEqual(
            resultado["valor_total_adquisicion"],
            "12161221.00",
        )
        self.assertEqual(
            sum(estado["cantidad"] for estado in resultado["distribucion_estados"]),
            8,
        )
        self.assertFalse(resultado["sin_resultados"])

    @patch("reportes.parque_ti_services.Activo.objects.filter")
    def test_filtro_por_departamento(self, mock_filtrar):

        activos = mock_filtrar.return_value
        filtrados = activos.filter.return_value

        filtrados.count.return_value = 4
        filtrados.aggregate.return_value = {"total": Decimal("12121221.00")}
        filtrados.values.return_value.annotate.return_value.order_by.return_value = [
            {"id_estado_activo__nombre": "Asignado", "cantidad": 4}
        ]

        resultado = obtener_reporte_parque_ti(
            self.fecha_inicio,
            self.fecha_fin,
            id_ubicacion=1,
        )

        activos.filter.assert_called_once_with(id_ubicacion_id=1)
        self.assertEqual(resultado["total_activos"], 4)
        self.assertEqual(
            resultado["valor_total_adquisicion"],
            "12121221.00",
        )

    @patch("reportes.parque_ti_services.Activo.objects.filter")
    def test_sin_activos(self, mock_filtrar):

        activos = mock_filtrar.return_value
        activos.count.return_value = 0

        resultado = obtener_reporte_parque_ti(
            self.fecha_inicio,
            self.fecha_fin,
        )

        self.assertEqual(resultado["total_activos"], 0)
        self.assertTrue(resultado["sin_resultados"])
        self.assertEqual(
            resultado["mensaje"],
            MENSAJE_SIN_ACTIVOS,
        )
        self.assertEqual(resultado["distribucion_estados"], [])

    @patch("reportes.parque_ti_services.OrdenRepuesto.objects.filter")
    @patch("reportes.parque_ti_services.Activo.objects.filter")
    def test_costos_repuestos(
        self,
        mock_activos_filter,
        mock_repuestos_filter,
    ):

        activos = mock_activos_filter.return_value
        activos.count.return_value = 2
        activos.aggregate.return_value = {"total": Decimal("1500000.00")}
        activos.values.return_value.annotate.return_value.order_by.return_value = [
            {"id_estado_activo__nombre": "Asignado", "cantidad": 2}
        ]

        repuestos = mock_repuestos_filter.return_value
        repuestos.aggregate.return_value = {"total": Decimal("85000.00")}

        resultado = obtener_reporte_parque_ti(
            self.fecha_inicio,
            self.fecha_fin,
            incluir_costos=True,
        )

        self.assertEqual(
            resultado["costos_repuestos"],
            "85000.00",
        )
        self.assertTrue(resultado["incluir_costos"])

        filtros = mock_repuestos_filter.call_args.kwargs

        self.assertFalse(filtros["anulado"])
        self.assertEqual(
            filtros["id_orden__id_estado_ot__nombre"],
            "Completada",
        )
        self.assertEqual(
            filtros["id_orden__cierre_tecnico__fecha_cierre__date__gte"],
            self.fecha_inicio,
        )
        self.assertEqual(
            filtros["id_orden__cierre_tecnico__fecha_cierre__date__lte"],
            self.fecha_fin,
        )

    def test_fecha_inicio_posterior_a_fecha_fin(self):

        with self.assertRaises(ValueError):
            obtener_reporte_parque_ti(
                date(2026, 10, 30),
                date(2026, 1, 1),
            )
