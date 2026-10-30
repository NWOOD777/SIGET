"""Pruebas del servicio de reportes del escritorio."""

import unittest
from datetime import date
from unittest.mock import patch

from siget_desktop.api.reportes_services import obtener_dashboard_reportes


class ReportesServicesTests(unittest.TestCase):

    @patch("siget_desktop.api.reportes_services.api_client.get")
    def test_consultar_dashboard_con_fechas(self, mock_get):
        mock_get.return_value = {
            "total_tickets_resueltos": 2,
            "fallas_recurrentes": [],
            "componentes_reemplazados": [],
            "tasas_fallas_por_categoria": [],
        }

        resultado = obtener_dashboard_reportes(
            fecha_inicio=date(2026, 10, 1),
            fecha_fin=date(2026, 10, 29),
        )

        mock_get.assert_called_once_with(
            "/api/reportes/dashboard/",
            params={
                "fecha_inicio": "2026-10-01",
                "fecha_fin": "2026-10-29",
            },
        )

        self.assertEqual(resultado["total_tickets_resueltos"], 2)

        if __name__ == "__main__":
            unittest.main()

    @patch("siget_desktop.api.reportes_services.api_client.get")
    def test_consultar_dashboard_por_categoria(self, mock_get):
        mock_get.return_value = {
            "total_tickets_resueltos": 1,
            "fallas_recurrentes": [],
            "componentes_reemplazados": [],
            "tasas_fallas_por_categoria": [],
        }

        obtener_dashboard_reportes(
            fecha_inicio=date(2026, 10, 1),
            fecha_fin=date(2026, 10, 29),
            id_categoria=1,
        )

        mock_get.assert_called_once_with(
            "/api/reportes/dashboard/",
            params={
                "fecha_inicio": "2026-10-01",
                "fecha_fin": "2026-10-29",
                "id_categoria": "1",
            },
        )

    def test_rechazar_fechas_invertidas(self):
        with self.assertRaises(ValueError):
            obtener_dashboard_reportes(
                fecha_inicio=date(2026, 10, 29),
                fecha_fin=date(2026, 10, 1),
            )

    def test_rechazar_categoria_invalida(self):
        for categoria in [0, -1, "1", True]:
            with self.subTest(categoria=categoria):
                with self.assertRaises(ValueError):
                    obtener_dashboard_reportes(
                        fecha_inicio=date(2026, 10, 1),
                        fecha_fin=date(2026, 10, 29),
                        id_categoria=categoria,
                    )
