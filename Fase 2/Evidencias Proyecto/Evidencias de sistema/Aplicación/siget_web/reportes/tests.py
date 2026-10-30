from datetime import datetime, timedelta, timezone

from types import SimpleNamespace

from unittest.mock import patch
from typing import cast

from django.test import SimpleTestCase

from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework.response import Response

from reportes.services import obtener_metricas_reportes


class MetricasReportesTests(SimpleTestCase):

    @patch("reportes.services.OrdenTrabajo.objects.filter")
    @patch("reportes.services.Ticket.objects.filter")
    def test_cumplimiento_sla_y_tiempo_promedio(
        self, mock_tickets_filter, mock_orden_filter
    ):

        inicio = datetime(2026, 10, 20, tzinfo=timezone.utc)

        prioridad = SimpleNamespace(sla=SimpleNamespace(tiempo_resolucion_horas=4))

        tickets = [
            SimpleNamespace(
                fecha_creacion=inicio,
                fecha_resolucion=inicio + timedelta(hours=2),
                id_prioridad=prioridad,
            ),
            SimpleNamespace(
                fecha_creacion=inicio,
                fecha_resolucion=inicio + timedelta(hours=6),
                id_prioridad=prioridad,
            ),
        ]

        mock_tickets_filter.return_value.select_related.return_value.order_by.return_value = (
            tickets
        )

        mock_orden_filter.return_value.first.return_value = None

        resultado = obtener_metricas_reportes(
            fecha_inicio=inicio.date(),
            fecha_fin=inicio.date(),
        )

        self.assertEqual(resultado["total_tickets_resueltos"], 2)

        self.assertEqual(resultado["tickets_dentro_sla"], 1)

        self.assertEqual(resultado["tickets_fuera_sla"], 1)

        self.assertEqual(resultado["porcentaje_cumplimiento_sla"], 50.0)

        self.assertEqual(resultado["tiempo_promedio_resolucion_horas"], 4.0)

    @patch("reportes.services.Ticket.objects.filter")
    def test_metricas_sin_tickets_resueltos(self, mock_tickets_filter):

        inicio = datetime(2026, 10, 20, tzinfo=timezone.utc)

        mock_tickets_filter.return_value.select_related.return_value.order_by.return_value = (
            []
        )

        resultado = obtener_metricas_reportes(
            fecha_inicio=inicio.date(),
            fecha_fin=inicio.date(),
        )

        self.assertEqual(resultado["total_tickets_resueltos"], 0)

        self.assertEqual(resultado["tickets_evaluados_sla"], 0)

        self.assertEqual(resultado["tickets_dentro_sla"], 0)

        self.assertEqual(resultado["tickets_fuera_sla"], 0)

        self.assertEqual(resultado["porcentaje_cumplimiento_sla"], 0)

        self.assertEqual(resultado["tiempo_promedio_resolucion_horas"], 0)


class AccesoDashboardReportesTests(SimpleTestCase):

    def test_usuario_no_autenticado_no_puede_consultar_reportes(self):

        cliente = APIClient()

        respuesta = cast(
            Response,
            cliente.get(
                reverse("dashboard-reportes"),
                {
                    "fecha_inicio": "2026-10-01",
                    "fecha_fin": "2026-10-29",
                },
            ),
        )

        self.assertIn(respuesta.status_code, [401, 403])


class AccesoTecnicoDashboardTests(SimpleTestCase):

    @patch("usuarios.permissions.es_administrador", return_value=False)
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_tecnico_no_puede_consultar_reportes(
        self, mock_usuario_actual, mock_es_administrador
    ):

        mock_usuario_actual.return_value = SimpleNamespace(activo=True)

        cliente = APIClient()

        respuesta = cast(
            Response,
            cliente.get(
                reverse("dashboard-reportes"),
                {
                    "fecha_inicio": "2026-10-01",
                    "fecha_fin": "2026-10-29",
                },
            ),
        )

        self.assertEqual(respuesta.status_code, 403)

        mock_es_administrador.assert_called_once()


class AdministradorSinPermisoReportesTests(SimpleTestCase):

    @patch("usuarios.permissions.usuario_tiene_permiso", return_value=False)
    @patch("usuarios.permissions.es_administrador", return_value=True)
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_administrador_sin_permiso_no_puede_consultar(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
    ):

        mock_usuario_actual.return_value = SimpleNamespace(activo=True)

        cliente = APIClient()

        respuesta = cast(
            Response,
            cliente.get(
                reverse("dashboard-reportes"),
                {
                    "fecha_inicio": "2026-10-01",
                    "fecha_fin": "2026-10-29",
                },
            ),
        )

        self.assertEqual(respuesta.status_code, 403)

        mock_es_administrador.assert_called_once()

        mock_tiene_permiso.assert_called_once_with(
            mock_usuario_actual.return_value,
            "REPORTES_CONSULTAR",
        )


class UsuarioInactivoReportesTests(SimpleTestCase):

    @patch("usuarios.permissions.es_administrador")
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_usuario_inactivo_no_puede_consultar_reportes(
        self, mock_usuario_actual, mock_es_administrador
    ):

        mock_usuario_actual.return_value = SimpleNamespace(activo=False)

        cliente = APIClient()

        respuesta = cast(
            Response,
            cliente.get(
                reverse("dashboard-reportes"),
                {
                    "fecha_inicio": "2026-10-01",
                    "fecha_fin": "2026-10-29",
                },
            ),
        )

        self.assertEqual(respuesta.status_code, 403)

        mock_es_administrador.assert_not_called()


class ValidacionFechasReportesTests(SimpleTestCase):

    @patch("usuarios.permissions.usuario_tiene_permiso", return_value=True)
    @patch("usuarios.permissions.es_administrador", return_value=True)
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_fechas_obligatorias(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
    ):

        mock_usuario_actual.return_value = SimpleNamespace(activo=True)

        cliente = APIClient()

        respuesta = cast(Response, cliente.get(reverse("dashboard-reportes")))

        self.assertEqual(respuesta.status_code, 400)

        self.assertIn(
            "Debe indicar fecha_inicio y fecha_fin",
            str(respuesta.data),
        )


class FormatoFechasReportesTests(SimpleTestCase):

    @patch("usuarios.permissions.usuario_tiene_permiso", return_value=True)
    @patch("usuarios.permissions.es_administrador", return_value=True)
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_formato_fecha_invalido(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
    ):

        mock_usuario_actual.return_value = SimpleNamespace(activo=True)

        cliente = APIClient()

        respuesta = cast(
            Response,
            cliente.get(
                reverse("dashboard-reportes"),
                {
                    "fecha_inicio": "fecha-invalida",
                    "fecha_fin": "2026-10-29",
                },
            ),
        )

        self.assertEqual(respuesta.status_code, 400)

        self.assertIn(
            "Las fechas deben tener formato YYYY-MM-DD",
            str(respuesta.data),
        )


class FechasInvertidasReportesTests(SimpleTestCase):

    @patch("usuarios.permissions.usuario_tiene_permiso", return_value=True)
    @patch("usuarios.permissions.es_administrador", return_value=True)
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_fecha_inicio_posterior_a_fecha_fin(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
    ):

        mock_usuario_actual.return_value = SimpleNamespace(activo=True)

        cliente = APIClient()

        respuesta = cast(
            Response,
            cliente.get(
                reverse("dashboard-reportes"),
                {
                    "fecha_inicio": "2026-10-29",
                    "fecha_fin": "2026-10-01",
                },
            ),
        )

        self.assertEqual(respuesta.status_code, 400)

        self.assertIn(
            "La fecha inicial no puede superar la fecha final",
            str(respuesta.data),
        )


class CategoriaInvalidaReportesTests(SimpleTestCase):

    @patch("usuarios.permissions.usuario_tiene_permiso", return_value=True)
    @patch("usuarios.permissions.es_administrador", return_value=True)
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_categoria_invalida(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
    ):

        mock_usuario_actual.return_value = SimpleNamespace(activo=True)

        cliente = APIClient()

        for categoria in ["abc", "0", "-1"]:

            with self.subTest(categoria=categoria):

                respuesta = cast(
                    Response,
                    cliente.get(
                        reverse("dashboard-reportes"),
                        {
                            "fecha_inicio": "2026-10-01",
                            "fecha_fin": "2026-10-29",
                            "id_categoria": categoria,
                        },
                    ),
                )

                self.assertEqual(respuesta.status_code, 400)

                datos = respuesta.data
                assert datos is not None
                self.assertIn("id_categoria", datos)


class AdministradorAutorizadoReportesTests(SimpleTestCase):

    @patch("reportes.views.Ticket.objects.filter")
    @patch(
        "reportes.views.obtener_tasa_fallas_por_categoria",
        return_value=[],
    )
    @patch(
        "reportes.views.obtener_componentes_reemplazados",
        return_value=[],
    )
    @patch(
        "reportes.views.obtener_fallas_recurrentes",
        return_value=[],
    )
    @patch("reportes.views.obtener_metricas_reportes")
    @patch("usuarios.permissions.usuario_tiene_permiso", return_value=True)
    @patch("usuarios.permissions.es_administrador", return_value=True)
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_administrador_autorizado_puede_consultar_reportes(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
        mock_metricas,
        mock_fallas,
        mock_componentes,
        mock_tasas,
        mock_tickets,
    ):

        mock_usuario_actual.return_value = SimpleNamespace(activo=True)

        mock_metricas.return_value = {
            "total_tickets_resueltos": 2,
            "porcentaje_cumplimiento_sla": 50.0,
        }

        mock_tickets.return_value.exists.return_value = True

        cliente = APIClient()

        respuesta = cast(
            Response,
            cliente.get(
                reverse("dashboard-reportes"),
                {
                    "fecha_inicio": "2026-10-01",
                    "fecha_fin": "2026-10-29",
                },
            ),
        )

        self.assertEqual(respuesta.status_code, 200)

        datos = respuesta.data
        assert datos is not None
        self.assertEqual(datos["total_tickets_resueltos"], 2)

        self.assertEqual(datos["porcentaje_cumplimiento_sla"], 50.0)

        mock_tiene_permiso.assert_called_once_with(
            mock_usuario_actual.return_value,
            "REPORTES_CONSULTAR",
        )


class DashboardSinRegistrosTests(SimpleTestCase):

    @patch("reportes.views.Ticket.objects.filter")
    @patch("reportes.views.obtener_tasa_fallas_por_categoria", return_value=[])
    @patch("reportes.views.obtener_componentes_reemplazados", return_value=[])
    @patch("reportes.views.obtener_fallas_recurrentes", return_value=[])
    @patch("reportes.views.obtener_metricas_reportes")
    @patch("usuarios.permissions.usuario_tiene_permiso", return_value=True)
    @patch("usuarios.permissions.es_administrador", return_value=True)
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_dashboard_sin_registros(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
        mock_metricas,
        mock_fallas,
        mock_componentes,
        mock_tasas,
        mock_tickets,
    ):

        mock_usuario_actual.return_value = SimpleNamespace(activo=True)

        mock_metricas.return_value = {
            "total_tickets_resueltos": 0,
            "porcentaje_cumplimiento_sla": 0,
            "tiempo_promedio_resolucion_horas": 0,
        }

        mock_tickets.return_value.exists.return_value = False

        cliente = APIClient()

        respuesta = cast(
            Response,
            cliente.get(
                reverse("dashboard-reportes"),
                {
                    "fecha_inicio": "2020-01-01",
                    "fecha_fin": "2020-12-31",
                },
            ),
        )

        self.assertEqual(respuesta.status_code, 200)

        datos = respuesta.data
        assert datos is not None
        self.assertEqual(datos["total_tickets_resueltos"], 0)

        self.assertEqual(
            datos["mensaje"],
            "No existen registros para el período especificado",
        )


class FiltroCategoriaReportesTests(SimpleTestCase):

    @patch("reportes.views.Ticket.objects.filter")
    @patch("reportes.views.obtener_tasa_fallas_por_categoria", return_value=[])
    @patch("reportes.views.obtener_componentes_reemplazados", return_value=[])
    @patch("reportes.views.obtener_fallas_recurrentes", return_value=[])
    @patch("reportes.views.obtener_metricas_reportes")
    @patch("usuarios.permissions.usuario_tiene_permiso", return_value=True)
    @patch("usuarios.permissions.es_administrador", return_value=True)
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_filtro_categoria_se_aplica_a_reportes(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
        mock_metricas,
        mock_fallas,
        mock_componentes,
        mock_tasas,
        mock_tickets,
    ):

        from datetime import date

        mock_usuario_actual.return_value = SimpleNamespace(activo=True)

        mock_metricas.return_value = {"total_tickets_resueltos": 1}

        mock_tickets.return_value.filter.return_value.exists.return_value = True

        cliente = APIClient()

        respuesta = cast(
            Response,
            cliente.get(
                reverse("dashboard-reportes"),
                {
                    "fecha_inicio": "2026-10-01",
                    "fecha_fin": "2026-10-29",
                    "id_categoria": "1",
                },
            ),
        )

        self.assertEqual(respuesta.status_code, 200)

        parametros = {
            "fecha_inicio": date(2026, 10, 1),
            "fecha_fin": date(2026, 10, 29),
            "id_categoria": 1,
        }

        mock_metricas.assert_called_once_with(**parametros)

        mock_fallas.assert_called_once_with(**parametros)

        mock_componentes.assert_called_once_with(**parametros)

        mock_tasas.assert_called_once_with(**parametros)

        mock_tickets.return_value.filter.assert_called_once_with(
            id_activo__id_modelo__id_categoria_id=1
        )


class FiltroFechasReportesTests(SimpleTestCase):

    @patch("reportes.views.Ticket.objects.filter")
    @patch("reportes.views.obtener_tasa_fallas_por_categoria", return_value=[])
    @patch("reportes.views.obtener_componentes_reemplazados", return_value=[])
    @patch("reportes.views.obtener_fallas_recurrentes", return_value=[])
    @patch("reportes.views.obtener_metricas_reportes")
    @patch("usuarios.permissions.usuario_tiene_permiso", return_value=True)
    @patch("usuarios.permissions.es_administrador", return_value=True)
    @patch("usuarios.permissions.obtener_usuario_actual")
    def test_filtro_fechas_se_aplica_a_reportes(
        self,
        mock_usuario_actual,
        mock_es_administrador,
        mock_tiene_permiso,
        mock_metricas,
        mock_fallas,
        mock_componentes,
        mock_tasas,
        mock_tickets,
    ):

        from datetime import date

        mock_usuario_actual.return_value = SimpleNamespace(activo=True)

        mock_metricas.return_value = {"total_tickets_resueltos": 1}

        mock_tickets.return_value.exists.return_value = True

        cliente = APIClient()

        respuesta = cast(
            Response,
            cliente.get(
                reverse("dashboard-reportes"),
                {
                    "fecha_inicio": "2026-10-01",
                    "fecha_fin": "2026-10-29",
                },
            ),
        )

        self.assertEqual(respuesta.status_code, 200)

        parametros = {
            "fecha_inicio": date(2026, 10, 1),
            "fecha_fin": date(2026, 10, 29),
            "id_categoria": None,
        }

        mock_metricas.assert_called_once_with(**parametros)

        mock_fallas.assert_called_once_with(**parametros)

        mock_componentes.assert_called_once_with(**parametros)

        mock_tasas.assert_called_once_with(**parametros)

        mock_tickets.assert_called_once_with(
            fecha_creacion__date__gte=date(2026, 10, 1),
            fecha_creacion__date__lte=date(2026, 10, 29),
        )
