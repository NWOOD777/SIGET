"""Verifica formato monetario y cancelación de escrituras antes de llamar a la API."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.activos_dialogs import AdministrarCatalogosActivosDialog, RegistrarActivoDialog
from siget_desktop.ui.dialogs.common import SessionDialog, confirmar_operacion, monto_decimal
from siget_desktop.ui.inputs import MontoLineEdit

APP = QApplication.instance() or QApplication([])


class MontosYConfirmacionesTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token-prueba", 3600)
        current_session.update_user_info({"id_usuario": 1, "roles": ["Administrador del sistema"], "acceso_escritorio": True})

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def test_miles_se_formatean_al_escribir_y_conservan_cursor(self):
        campo = MontoLineEdit()
        QTest.keyClicks(campo, "1250000")
        self.assertEqual(campo.text(), "1.250.000")
        self.assertEqual(campo.cursorPosition(), len(campo.text()))
        self.assertEqual(monto_decimal(campo.text()), "1250000.00")
        campo.setText("1234")
        campo.setCursorPosition(1)
        QTest.keyClick(campo, Qt.Key.Key_Delete)
        self.assertEqual(campo.text(), "134")
        campo.setText("1234")
        campo.setCursorPosition(2)
        QTest.keyClick(campo, Qt.Key.Key_Backspace)
        self.assertEqual(campo.text(), "234")

    def test_reemplazo_pegado_y_deshacer_preservan_el_valor(self):
        campo = MontoLineEdit()
        campo.setText("650000.50")
        self.assertEqual(campo.text(), "650.000,50")
        campo.selectAll()
        QTest.keyClicks(campo, "900000")
        self.assertEqual(campo.text(), "900.000")
        QApplication.clipboard().setText("1250000")
        campo.selectAll()
        campo.paste()
        self.assertEqual(campo.text(), "1.250.000")
        QTest.keyClick(campo, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(campo.text(), "900.000")
        QTest.keyClick(campo, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(campo.text(), "1.250.000")

    def test_letras_signos_y_separadores_decimales_no_ingresan_al_campo(self):
        campo = MontoLineEdit()
        QTest.keyClicks(campo, "abc!@#$%&-+ ,.")
        self.assertEqual(campo.text(), "")
        QTest.keyClicks(campo, "12abc34")
        self.assertEqual(campo.text(), "1.234")
        campo.insert("texto")
        self.assertEqual(campo.text(), "1.234")
        campo.selectAll()
        QApplication.clipboard().setText("1.250.000")
        campo.paste()
        self.assertEqual(campo.text(), "1.250.000")
        self.assertEqual(monto_decimal(campo.text()), "1250000.00")

    def test_pegar_monto_invalido_no_lo_convierte_en_otro_valor(self):
        campo = MontoLineEdit()
        campo.setText("750000")
        for invalido in ("1.2345", "1234.00", "1.234,50", "nan", "-10", "texto", "99999999999999"):
            with self.subTest(valor=invalido):
                campo.selectAll()
                QApplication.clipboard().setText(invalido)
                campo.paste()
                self.assertEqual(campo.text(), "750.000")

    def test_cancelar_y_cerrar_confirmacion_no_autorizan_guardar(self):
        padre = SessionDialog()
        for respuesta in (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Close):
            with patch("siget_desktop.ui.dialogs.common.QMessageBox.exec", return_value=respuesta):
                self.assertFalse(confirmar_operacion(padre, "Crear", "Marca: Nueva marca"))
        def comprobar():
            mensaje = next(m for m in padre.findChildren(QMessageBox) if m.text() == "Marca: <texto>")
            self.assertEqual(mensaje.defaultButton(), mensaje.button(QMessageBox.StandardButton.No))
            self.assertEqual(mensaje.textFormat(), Qt.TextFormat.PlainText)
            return QMessageBox.StandardButton.Yes
        with patch("siget_desktop.ui.dialogs.common.QMessageBox.exec", side_effect=comprobar):
            self.assertTrue(confirmar_operacion(padre, "Crear", "Marca: <texto>"))

    def test_cambio_de_sesion_durante_confirmacion_invalida_la_respuesta(self):
        padre = SessionDialog()
        def cerrar():
            current_session.clear()
            return QMessageBox.StandardButton.Yes
        with patch("siget_desktop.ui.dialogs.common.QMessageBox.exec", side_effect=cerrar):
            self.assertFalse(confirmar_operacion(padre, "Crear", "Marca"))

    def test_cancelar_creacion_y_edicion_de_cada_catalogo_no_inicia_worker(self):
        with patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker") as worker:
            dialogo = AdministrarCatalogosActivosDialog()
            dialogo._on_todos_cargados({"todas_marcas": [{"id_marca": 1, "nombre": "Marca"}], "todas_categorias": [{"id_categoria": 1, "nombre": "Categoría"}]})
            casos = [("categoria", dialogo.input_categoria_nombre), ("marca", dialogo.input_marca_nombre), ("ubicacion", dialogo.input_ubicacion_area), ("modelo", dialogo.input_modelo_nombre)]
            for tipo, campo in casos:
                for identificador in (None, 4):
                    with self.subTest(tipo=tipo, editando=identificador):
                        setattr(dialogo, f"_id_{tipo}_editando", identificador)
                        campo.setText("Registro revisable")
                        worker.reset_mock()
                        with patch("siget_desktop.ui.dialogs.common.QMessageBox.exec", return_value=QMessageBox.StandardButton.No):
                            getattr(dialogo, f"_guardar_{tipo}")()
                        worker.assert_not_called()
                        self.assertEqual(campo.text(), "Registro revisable")
                        self.assertFalse(dialogo.progreso.isVisible())

    def test_registro_activo_solo_envia_tras_confirmar_y_con_monto_canonico(self):
        with patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker") as worker:
            dialogo = RegistrarActivoDialog()
            dialogo._on_catalogos({"modelos": [{"id_modelo": 5, "nombre": "Modelo"}], "ubicaciones": [{"id_ubicacion": 6, "nombre_area": "Bodega"}]})
            dialogo.input_serie.setText("SERIE-VALIDA")
            QTest.keyClicks(dialogo.input_valor, "1250000")
            worker.reset_mock()
            with patch("siget_desktop.ui.dialogs.common.QMessageBox.exec", return_value=QMessageBox.StandardButton.No):
                dialogo._guardar()
            worker.assert_not_called()
            self.assertTrue(dialogo.btn_guardar.isEnabled())
            self.assertEqual(dialogo.input_serie.text(), "SERIE-VALIDA")
            with patch("siget_desktop.ui.dialogs.common.QMessageBox.exec", return_value=QMessageBox.StandardButton.Yes):
                dialogo._guardar()
            self.assertEqual(worker.call_args.kwargs["datos"]["valor_adquisicion"], "1250000.00")
