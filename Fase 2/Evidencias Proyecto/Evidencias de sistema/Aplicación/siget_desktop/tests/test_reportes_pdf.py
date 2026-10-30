"""Pruebas de generación de informes PDF."""

import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QGuiApplication

from siget_desktop.ui.reportes_pdf import guardar_pdf_reportes


class ReportesPDFTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_generar_pdf_reportes(self):
        datos = {
            "total_tickets_resueltos": 10,
            "tickets_evaluados_sla": 10,
            "tickets_dentro_sla": 8,
            "tickets_fuera_sla": 2,
            "tickets_sin_sla": 0,
            "porcentaje_cumplimiento_sla": 80.0,
            "tiempo_promedio_resolucion_horas": 3.5,
            "fallas_recurrentes": [
                {
                    "falla": "Falla de memoria RAM",
                    "cantidad": 3,
                }
            ],
            "componentes_reemplazados": [
                {
                    "id_repuesto": 1,
                    "repuesto": "Disco SSD",
                    "cantidad": 2,
                }
            ],
            "tasas_fallas_por_categoria": [
                {
                    "categoria": "Notebook",
                    "total_activos": 4,
                    "activos_con_fallas": 3,
                    "tasa_fallas_porcentaje": 75.0,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temporal:
            ruta = str(Path(temporal) / "reporte.pdf")

            guardar_pdf_reportes(
                ruta,
                datos,
                "2026-10-01",
                "2026-10-29",
            )

            archivo = Path(ruta)

            self.assertTrue(archivo.exists())
            self.assertGreater(archivo.stat().st_size, 0)

            with archivo.open("rb") as pdf:
                self.assertEqual(pdf.read(5), b"%PDF-")


if __name__ == "__main__":
    unittest.main()
