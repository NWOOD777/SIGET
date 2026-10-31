"""Lectura de teclado HID y selección de equipos sin registrar operaciones."""

import unittest
from typing import Any
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from siget_desktop.api.services import identificar_activo
from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.asignaciones_dialogs import RegistrarDevolucionDialog
from siget_desktop.ui.dialogs.ordenes_trabajo_dialogs import CrearOrdenTrabajoDialog
from siget_desktop.ui.dialogs.solicitudes_dialogs import RegistrarEntregaDialog
from siget_desktop.ui.identificar_activo import IdentificarActivoWidget

_app = QApplication.instance() or QApplication([])
FICHA = {"id_activo": 7, "codigo_inventario": "ACT-0007", "numero_serie": "00001234", "modelo": "Portátil", "marca": "Marca", "estado": "Disponible"}


class Senales(QObject):
    finished = Signal(object)
    error = Signal(object)


class WorkerDiferido:
    creados: list = []

    def __init__(self, funcion, *args, **kwargs):
        self.signals = Senales()
        self.funcion, self.args, self.kwargs = funcion, args, kwargs
        self.creados.append(self)

    def start(self):
        pass


class LecturaHIDTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token-prueba", expires_in=3600)
        WorkerDiferido.creados.clear()
        parche = patch("siget_desktop.ui.identificar_activo.ApiWorker", WorkerDiferido)
        parche.start()
        self.addCleanup(parche.stop)

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def leer(self, widget, texto="ACT-0007", sufijo=Qt.Key.Key_Return) -> Any:
        widget.input.selectAll()
        QTest.keyClicks(widget.input, texto)
        QTest.keyClick(widget.input, sufijo)
        return WorkerDiferido.creados[-1] if WorkerDiferido.creados else None

    def test_enter_tab_y_enter_numerico_resuelven_una_ficha(self):
        for sufijo in (Qt.Key.Key_Return, Qt.Key.Key_Tab, Qt.Key.Key_Enter):
            with self.subTest(sufijo=sufijo):
                widget = IdentificarActivoWidget()
                recibido = Mock()
                widget.identificado.connect(recibido)
                worker = self.leer(widget, sufijo=sufijo)
                self.assertIsNotNone(worker)
                self.assertEqual(worker.args, ("ACT-0007",))
                worker.signals.finished.emit(FICHA)
                recibido.assert_called_once_with(FICHA)
                self.assertIn("00001234", widget.lbl_ficha.text())
                self.assertFalse(widget.en_consulta)

    def test_ingreso_manual_conserva_ceros_y_busca_con_boton(self):
        widget = IdentificarActivoWidget()
        QTest.keyClicks(widget.input, "00001234")
        self.assertFalse(WorkerDiferido.creados)
        widget.btn_buscar.click()
        self.assertEqual(WorkerDiferido.creados[-1].args, ("00001234",))

    def test_entrada_invalida_y_pegado_no_buscan_identificador_truncado(self):
        widget = IdentificarActivoWidget()
        for texto in ("ACT 0007", "https://malicioso/7", "A" * 102):
            self.leer(widget, texto)
            self.assertFalse(WorkerDiferido.creados)
        for texto in ("ACT-0007\n", "ACT-0007\t", "A" * 101):
            QApplication.clipboard().setText(texto)
            QTest.keyClick(widget.input, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(widget.input.text(), "")
            self.assertFalse(WorkerDiferido.creados)

    def test_doble_terminador_y_resultado_antiguo(self):
        widget = IdentificarActivoWidget()
        anterior = self.leer(widget)
        QTest.keyClick(widget.input, Qt.Key.Key_Enter)
        self.assertEqual(len(WorkerDiferido.creados), 1)
        nuevo = self.leer(widget, "NO-REGISTRADO")
        anterior.signals.finished.emit(FICHA)
        self.assertIsNone(widget.activo)
        nuevo.signals.error.emit(RuntimeError("Código no registrado"))
        self.assertIsNone(widget.activo)
        self.assertIn("no registrado", widget.lbl_ficha.text())

    def test_resultados_despues_de_cerrar_o_cambiar_sesion_se_ignoran(self):
        for cerrar in (False, True):
            widget = IdentificarActivoWidget()
            worker = self.leer(widget)
            if cerrar:
                setattr(widget, "_closed", True)
            else:
                current_session.clear()
            worker.signals.finished.emit(FICHA)
            self.assertIsNone(widget.activo)
            current_session.set_tokens("otro-token", expires_in=3600)

    @patch("siget_desktop.ui.dialogs.solicitudes_dialogs.ApiWorker")
    def test_entrega_autocompleta_y_error_borra_seleccion_sin_escritura(self, worker_dialogo):
        dialogo = RegistrarEntregaDialog({"id_solicitud": 4, "categoria": {"nombre": "Notebook"}})
        worker = self.leer(dialogo.lector_activo)
        self.assertFalse(dialogo.btn_entregar.isEnabled())
        self.assertEqual(worker.kwargs["id_solicitud"], 4)
        worker.signals.finished.emit(FICHA)
        self.assertIn("ACT-0007", dialogo.equipo_identificado.text())
        self.assertTrue(dialogo.btn_entregar.isEnabled())
        worker = self.leer(dialogo.lector_activo, "OTRO-0008")
        worker.signals.error.emit(RuntimeError("Categoría incompatible"))
        self.assertEqual(dialogo.equipo_identificado.text(), "")
        self.assertFalse(dialogo.btn_entregar.isEnabled())
        dialogo._ejecutar_entrega()
        worker_dialogo.assert_not_called()

    @patch("siget_desktop.ui.dialogs.asignaciones_dialogs.ApiWorker")
    def test_devolucion_solo_habilita_equipo_verificado(self, worker_dialogo):
        dialogo = RegistrarDevolucionDialog({"id_asignacion": 3, "activo": FICHA, "id_activo": 7})
        worker = self.leer(dialogo.lector_activo)
        self.assertEqual(worker.kwargs["id_asignacion"], 3)
        worker.signals.finished.emit(FICHA)
        self.assertTrue(dialogo.btn_confirmar.isEnabled())
        worker = self.leer(dialogo.lector_activo, "OTRO-0008")
        worker.signals.error.emit(RuntimeError("No corresponde a esta devolución"))
        self.assertFalse(dialogo.btn_confirmar.isEnabled())
        dialogo._registrar()
        worker_dialogo.assert_not_called()

    @patch("siget_desktop.ui.dialogs.ordenes_trabajo_dialogs.ApiWorker")
    @patch("siget_desktop.ui.dialogs.ordenes_trabajo_dialogs.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
    def test_operacion_tecnica_filtra_y_completa_ticket_al_confirmar(self, pregunta, worker_dialogo):
        dialogo = CrearOrdenTrabajoDialog()
        worker = self.leer(dialogo.lector_activo)
        worker.signals.finished.emit(FICHA)
        ticket = {"id_ticket": 2, "codigo_ticket": "TCK-0002", "asunto": "Falla", "activo": FICHA, "estado": {"nombre": "Abierto"}}
        dialogo._on_tickets_cargados(
            {
                "tickets": [ticket, {**ticket, "id_ticket": 3, "activo": {**FICHA, "id_activo": 8}}],
                "ordenes": [],
                "activos_revision": [FICHA, {"id_activo": 8}],
            }
        )
        self.assertEqual(dialogo.lista_tickets.count(), 1)
        self.assertTrue(dialogo.btn_continuar.isEnabled())
        self.assertIsNone(dialogo._ticket_confirmado)
        dialogo._confirmar_ticket()
        assert dialogo._ticket_confirmado is not None
        self.assertEqual(dialogo._ticket_confirmado["id_ticket"], 2)
        self.assertIn("ACT-0007", dialogo.lbl_confirmacion.text())
        self.assertEqual(worker_dialogo.call_count, 1)

    @patch("siget_desktop.api.services.api_client")
    def test_servicio_consulta_con_contexto_y_no_escribe(self, cliente):
        cliente.get.return_value = FICHA
        self.assertEqual(identificar_activo("ACT-0007", id_solicitud=4), FICHA)
        cliente.get.assert_called_once_with("/api/activos/identificar/", params={"identificador": "ACT-0007", "id_solicitud": 4})
        cliente.post.assert_not_called()

    @patch("siget_desktop.ui.dialogs.ordenes_trabajo_dialogs.ApiWorker")
    def test_varios_tickets_requieren_eleccion_y_codigo_desconocido_limpia(self, _worker):
        dialogo = CrearOrdenTrabajoDialog()
        ticket = {"id_ticket": 2, "codigo_ticket": "TCK-0002", "asunto": "Falla", "activo": FICHA}
        dialogo._on_tickets_cargados({"tickets": [ticket, {**ticket, "id_ticket": 3}], "ordenes": [], "activos_revision": [FICHA]})
        worker = self.leer(dialogo.lector_activo)
        worker.signals.finished.emit(FICHA)
        self.assertEqual(dialogo.lista_tickets.count(), 2)
        self.assertFalse(dialogo.btn_continuar.isEnabled())
        dialogo.lista_tickets.setCurrentRow(1)
        self.assertTrue(dialogo.btn_continuar.isEnabled())
        worker = self.leer(dialogo.lector_activo, "DESCONOCIDO")
        worker.signals.error.emit(RuntimeError("No registrado"))
        self.assertEqual(dialogo.lista_tickets.count(), 0)
        self.assertFalse(dialogo.btn_continuar.isEnabled())

    def test_pegado_valido_reemplaza_seleccion_y_conserva_sufijo(self):
        widget = IdentificarActivoWidget()
        widget.input.setText("ACT-0007")
        widget.input.setSelection(4, 4)
        QApplication.clipboard().setText("0010")
        QTest.keyClick(widget.input, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(widget.input.text(), "ACT-0010")
        self.assertFalse(WorkerDiferido.creados)

    @patch("siget_desktop.ui.dialogs.solicitudes_dialogs.ApiWorker")
    def test_respuesta_despues_de_cerrar_dialogo_se_ignora(self, _worker):
        dialogo = RegistrarEntregaDialog({"id_solicitud": 4})
        worker = self.leer(dialogo.lector_activo)
        dialogo.reject()
        worker.signals.finished.emit(FICHA)
        self.assertIsNone(dialogo.lector_activo.activo)
        self.assertFalse(dialogo.btn_entregar.isEnabled())


    @patch("siget_desktop.ui.dialogs.solicitudes_dialogs.ApiWorker")
    @patch("siget_desktop.ui.dialogs.solicitudes_dialogs.confirmar_operacion", return_value=True)
    def test_equipo_solo_lectura_no_permite_entregar_sin_identificar(self, confirmar, worker_dialogo):
        dialogo = RegistrarEntregaDialog({"id_solicitud": 4})
        self.assertTrue(dialogo.equipo_identificado.isReadOnly())
        QTest.keyClicks(dialogo.equipo_identificado, "ACT-0007")
        self.assertEqual(dialogo.equipo_identificado.text(), "")
        dialogo.equipo_identificado.setText("ACT-0007")
        dialogo._ejecutar_entrega()
        self.assertFalse(dialogo.btn_entregar.isEnabled())
        confirmar.assert_not_called()
        worker_dialogo.assert_not_called()

    @patch("siget_desktop.ui.dialogs.solicitudes_dialogs.ApiWorker")
    @patch("siget_desktop.ui.dialogs.solicitudes_dialogs.confirmar_operacion", return_value=True)
    def test_entrega_manual_usa_ficha_validada_y_no_repite_registro(self, confirmar, worker_dialogo):
        dialogo = RegistrarEntregaDialog({"id_solicitud": 4})
        QTest.keyClicks(dialogo.lector_activo.input, "00001234")
        dialogo.lector_activo.btn_buscar.click()
        worker = WorkerDiferido.creados[-1]
        self.assertEqual(worker.args, ("00001234",))
        self.assertEqual(worker.kwargs["id_solicitud"], 4)
        worker.signals.finished.emit(FICHA)
        self.assertTrue(dialogo.btn_entregar.isEnabled())
        QTest.keyClicks(dialogo.equipo_identificado, "OTRO-0008")
        self.assertIn("ACT-0007", dialogo.equipo_identificado.text())
        dialogo._ejecutar_entrega()
        self.assertEqual(worker_dialogo.call_args.kwargs["id_activo"], 7)
        confirmar.assert_called_once()
        self.assertFalse(dialogo.btn_entregar.isEnabled())
        dialogo._ejecutar_entrega()
        worker_dialogo.assert_called_once()


    @patch("siget_desktop.ui.dialogs.ordenes_trabajo_dialogs.ApiWorker")
    @patch("siget_desktop.ui.dialogs.ordenes_trabajo_dialogs.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
    def test_orden_exige_identificar_equipo_y_reinicia_si_cambia(self, _pregunta, worker_dialogo):
        dialogo = CrearOrdenTrabajoDialog()
        ticket = {"id_ticket": 2, "codigo_ticket": "TCK-0002", "activo": FICHA, "asunto": "Falla"}
        dialogo._on_tickets_cargados({"tickets": [ticket], "ordenes": [], "activos_revision": [FICHA]})
        self.assertEqual(dialogo.lista_tickets.count(), 0)
        self.assertFalse(dialogo.input_busqueda.isEnabled())
        self.assertFalse(dialogo.btn_continuar.isEnabled())
        dialogo.input_busqueda.setText("TCK-0002")
        dialogo._filtrar_tickets()
        self.assertEqual(dialogo.lista_tickets.count(), 0)
        worker = self.leer(dialogo.lector_activo)
        worker.signals.finished.emit(FICHA)
        self.assertEqual(dialogo.lista_tickets.count(), 1)
        self.assertTrue(dialogo.input_busqueda.isEnabled())
        dialogo._confirmar_ticket()
        self.assertIsNotNone(dialogo._ticket_confirmado)
        self.assertEqual(dialogo.pasos.currentIndex(), 1)
        dialogo.lector_activo.input.setText("OTRO-0008")
        self.assertIsNone(dialogo._ticket_confirmado)
        self.assertEqual(dialogo.pasos.currentIndex(), 0)
        self.assertEqual(dialogo.lista_tickets.count(), 0)
        self.assertFalse(dialogo.btn_continuar.isEnabled())
        worker_dialogo.assert_called_once()
