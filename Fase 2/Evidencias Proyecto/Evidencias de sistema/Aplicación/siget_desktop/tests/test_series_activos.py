"""Validación del formato de números de serie del escritorio."""
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit

from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.activos_dialogs import DetalleModificarActivoDialog, RegistrarActivoDialog
from siget_desktop.ui.inputs import NumeroSerieLineEdit

APP = QApplication.instance() or QApplication([])


class SeriesActivosTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token-prueba", 3600)
        current_session.update_user_info({"id_usuario": 1, "roles": ["Administrador del sistema"], "acceso_escritorio": True})

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def test_escribir_espacios_no_los_inserta(self):
        campo = NumeroSerieLineEdit()
        QTest.keyClicks(campo, "SN 123 456")
        self.assertEqual(campo.text(), "SN123456")

    def test_pegado_invalido_no_modifica_la_serie(self):
        campo = NumeroSerieLineEdit()
        for texto in ("SN 123", " SN123", "SN123 ", "SN\t123", "SN\n123", "SN\r123", "SN\u00a0123", "SN\u2003123", "***", "SN[123]", "SN;123", "SN\"123", "SN,123", "SN--123", "-SN123", "SN\u200b123"):
            for metodo in (campo.paste, lambda: QTest.keyClick(campo, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier), lambda: QLineEdit.paste(campo)):
                with self.subTest(texto=repr(texto), metodo=metodo):
                    campo.setText("SERIE-ORIGINAL")
                    campo.selectAll()
                    QApplication.clipboard().setText(texto)
                    metodo()
                    self.assertEqual(campo.text(), "SERIE-ORIGINAL")

    def test_acepta_series_numericas_y_alfanumericas(self):
        campo = NumeroSerieLineEdit()
        for texto in ("949423442", "PG01GTB2", "SN-LNV-2026-9988", "aB12_34/56.78"):
            campo.selectAll()
            QApplication.clipboard().setText(texto)
            campo.paste()
            self.assertEqual(campo.text(), texto)

    def test_guardar_rechaza_espacios_aunque_el_texto_se_asigne_por_codigo(self):
        with patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker") as worker:
            dialogo = RegistrarActivoDialog()
            dialogo.input_serie.setText("notebook ultra cara")
            worker.reset_mock()
            dialogo._guardar()
            worker.assert_not_called()
            self.assertIn("espacios", dialogo.lbl_mensaje.text())

    def test_caracteres_invalidos_no_se_escriben(self):
        campo = NumeroSerieLineEdit()
        QTest.keyClicks(campo, "*[];,+!\"'()<>?={}:\\")
        self.assertEqual(campo.text(), "")
        QTest.keyClicks(campo, "SN--123")
        self.assertEqual(campo.text(), "SN-123")

    def test_serie_invalida_no_se_envia_al_crear_ni_actualizar(self):
        with patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker") as worker:
            nuevo = RegistrarActivoDialog()
            detalle = DetalleModificarActivoDialog(id_activo=1)
            detalle._activo_datos = {"numero_serie": "SN123"}
            for serie in ("***", "SN[123]", "SN--123", "-SN123", "SN123-", "SN/", "a" * 101):
                for dialogo, guardar in ((nuevo, nuevo._guardar), (detalle, detalle._guardar_cambios)):
                    with self.subTest(serie=serie, dialogo=type(dialogo).__name__):
                        # setText conserva texto inválido recibido desde código; guardar debe rechazarlo.
                        dialogo.input_serie.setMaxLength(200)
                        dialogo.input_serie.setText(serie)
                        worker.reset_mock()
                        guardar()
                        worker.assert_not_called()
                        self.assertIn("Ingrese", dialogo.lbl_mensaje.text())

    def test_editar_otro_campo_conserva_una_serie_preexistente(self):
        with patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker") as worker:
            dialogo = DetalleModificarActivoDialog(id_activo=1)
            dialogo._activo_datos = {"numero_serie": "SERIE ANTIGUA", "valor_adquisicion": "100.00"}
            dialogo.input_serie.setText("SERIE ANTIGUA")
            dialogo.input_valor.setText("200")
            worker.reset_mock()
            with patch("siget_desktop.ui.dialogs.activos_dialogs.confirmar_operacion", return_value=False) as confirmar:
                dialogo._guardar_cambios()
            confirmar.assert_called_once()
            worker.assert_not_called()
