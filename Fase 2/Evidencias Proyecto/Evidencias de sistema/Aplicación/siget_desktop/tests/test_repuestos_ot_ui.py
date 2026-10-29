"""Sesión, confirmaciones y presentación de repuestos asociados a una OT."""
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.common import SessionDialog
from siget_desktop.ui.dialogs.gestionar_repuestos_ot_dialog import GestionarRepuestosOTDialog, formato_clp
from siget_desktop.ui.workers import ApiWorker

APP = QApplication.instance() or QApplication([])
MODULO = "siget_desktop.ui.dialogs.gestionar_repuestos_ot_dialog"


class RepuestosOTUiTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token-pruebas", 3600)
        current_session.update_user_info({"id_usuario": 2, "roles": ["Técnico de soporte"], "permisos": ["TICKET_ATENDER"], "acceso_escritorio": True})
        self.start = patch.object(ApiWorker, "start").start()
        self.addCleanup(patch.stopall)
        self.dialogo = GestionarRepuestosOTDialog(1, "OT-0001", "En Reparación")

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()
        for worker in list(ApiWorker._activos):
            if not worker.isRunning():
                worker._liberar()

    def completar_carga(self, estado="En Reparación"):
        worker = self.dialogo._worker
        assert worker is not None
        worker.signals.finished.emit({"estado_ot": estado, "repuestos": [], "resumen": {"costo_total_repuestos": "0.00"}})

    def seleccionar(self):
        self.completar_carga()
        self.dialogo._busqueda_completada([{"id_repuesto": 4, "codigo_repuesto": "REP-0004", "nombre": "Memoria", "stock_actual": 5, "precio_unitario": "15000.51"}])
        self.dialogo.combo_repuestos.setCurrentIndex(1)

    def test_no_redondea_los_centavos(self):
        self.assertEqual(formato_clp("15000.51"), "$15.000,51")
        self.assertEqual(formato_clp("123456789012.34"), "$123.456.789.012,34")
        self.assertEqual(formato_clp("NaN"), "—")

    def test_ot_completada_solo_muestra_consulta(self):
        self.completar_carga("Completada")
        self.assertTrue(self.dialogo.formulario.isHidden())
        self.assertTrue(self.dialogo.btn_anular.isHidden())
        self.assertFalse(self.dialogo.btn_asignar.isEnabled())

    def test_cancelar_confirmacion_no_envia_operacion(self):
        self.seleccionar()
        with patch(MODULO + ".confirmar_operacion", return_value=False) as confirmar:
            self.dialogo._asignar_repuesto()
        confirmar.assert_called_once()
        self.assertIsNone(self.dialogo._worker)

    def test_no_habilita_otra_operacion_mientras_se_guarda(self):
        self.seleccionar()
        with patch(MODULO + ".confirmar_operacion", return_value=True):
            self.dialogo._asignar_repuesto()
        worker = self.dialogo._worker
        self.assertTrue(self.dialogo._mutando)
        self.assertFalse(self.dialogo.btn_asignar.isEnabled())
        self.dialogo._actualizar_costo_estimado()
        self.assertFalse(self.dialogo.btn_asignar.isEnabled())
        self.dialogo.reject()
        self.assertFalse(self.dialogo._closed)
        self.assertIs(self.dialogo._worker, worker)

    def test_resultado_tardio_no_rellena_un_dialogo_cerrado(self):
        self.assertIsInstance(self.dialogo, SessionDialog)
        worker = self.dialogo._worker
        assert worker is not None
        self.dialogo.reject()
        worker.signals.finished.emit({"repuestos": [{"nombre_repuesto": "Dato privado"}]})
        self.assertEqual(self.dialogo.tabla.rowCount(), 0)

    def test_cambio_de_sesion_descarta_resultados_y_bloquea_operaciones(self):
        worker = self.dialogo._worker
        assert worker is not None
        current_session.clear()
        current_session.set_tokens("otra-sesion", 3600)
        current_session.update_user_info({"roles": ["Técnico de soporte"]})
        worker.signals.finished.emit({"repuestos": [{"nombre_repuesto": "Dato privado"}]})
        self.assertEqual(self.dialogo.tabla.rowCount(), 0)
        self.assertFalse(self.dialogo._puede_consultar())

    def test_cierre_de_sesion_cierra_el_dialogo_incluso_durante_guardado(self):
        self.seleccionar()
        with patch(MODULO + ".confirmar_operacion", return_value=True):
            self.dialogo._asignar_repuesto()
        current_session.clear()
        self.dialogo._check_session()
        self.assertTrue(self.dialogo._closed)
