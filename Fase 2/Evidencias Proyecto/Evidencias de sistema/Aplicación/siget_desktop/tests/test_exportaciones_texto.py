import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from siget_desktop.ui.parque_ti_excel import guardar_excel_parque_ti
from siget_desktop.ui.reportes_excel import guardar_excel_reportes


class ExportacionesTextoTests(unittest.TestCase):
    def test_datos_de_negocio_se_guardan_como_texto_y_los_montos_como_numeros(self):
        for texto in ("=1+1", "+SUM(A1)", "-1+1", "@SUM(A1)", "\t=1+1", "Modelo normal"):
            with self.subTest(texto=texto), tempfile.TemporaryDirectory() as carpeta:
                soporte = Path(carpeta) / "soporte.xlsx"
                parque = Path(carpeta) / "parque.xlsx"
                guardar_excel_reportes(str(soporte), {
                    "fallas_recurrentes": [{"falla": texto, "cantidad": 2}],
                    "componentes_reemplazados": [{"repuesto": texto, "cantidad": 1}],
                    "tasas_fallas_por_categoria": [{"categoria": texto}],
                }, "2026-01-01", "2026-11-01")
                guardar_excel_parque_ti(str(parque), {
                    "total_activos": 1, "valor_total_adquisicion": "1500",
                    "detalle_equipos": [{"equipo": texto, "estado": texto, "valor_adquisicion": "1500"}],
                    "distribucion_estados": [{"estado": texto, "cantidad": 1}],
                }, "2026-01-01", "2026-11-01", departamento=texto)
                for ruta, hoja, celda in (
                    (soporte, "Fallas recurrentes", "A2"), (soporte, "Componentes reemplazados", "A2"),
                    (soporte, "Tasas por categoria", "A2"), (parque, "Detalle equipos", "A2"),
                    (parque, "Resumen parque TI", "B4"),
                ):
                    libro = load_workbook(ruta, data_only=False)
                    self.assertEqual(libro[hoja][celda].value, texto)
                    self.assertEqual(libro[hoja][celda].data_type, "s")
                    self.assertFalse(any(c.data_type == "f" for h in libro for fila in h for c in fila))
                    libro.close()
                libro = load_workbook(parque)
                self.assertEqual(libro["Detalle equipos"]["C2"].value, 1500)
                self.assertEqual(libro["Detalle equipos"]["C2"].data_type, "n")
                libro.close()
