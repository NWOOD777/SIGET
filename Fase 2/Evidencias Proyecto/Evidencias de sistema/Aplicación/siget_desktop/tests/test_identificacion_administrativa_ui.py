"""El RUT solo se muestra en la consulta administrativa elegida."""
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.usuarios_dialogs import DetalleAccesoUsuarioDialog
from siget_desktop.ui.views.usuarios_view import UsuariosView

APP = QApplication.instance() or QApplication([])


class IdentificacionAdministrativaUiTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token-prueba", 3600)
        current_session.update_user_info({"id_usuario": 1, "roles": ["Administrador del sistema"], "acceso_escritorio": True})

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def test_lista_no_tiene_columna_rut_y_la_ficha_lo_identifica_separadamente(self):
        self.assertNotIn("RUT", UsuariosView.COLUMNAS)
        with patch("siget_desktop.ui.dialogs.usuarios_dialogs.ApiWorker"):
            d = DetalleAccesoUsuarioDialog(2)
        d._on_datos({"nombres": "Cuenta", "apellidos": "Institucional", "rut": "22222222-2", "roles": [], "permisos_efectivos": []})
        self.assertNotIn("22222222-2", d.lbl_titulo.text())
        self.assertEqual(d.lbl_identificacion.text(), "RUT institucional: 22222222-2")

    def test_cancelar_correccion_no_inicia_escritura_y_confirmar_la_envia(self):
        modulo = "siget_desktop.ui.dialogs.usuarios_dialogs"
        with patch(f"{modulo}.ApiWorker") as worker, patch(f"{modulo}.confirmar_operacion", return_value=False) as confirmar:
            d = DetalleAccesoUsuarioDialog(2)
            d._on_datos({"rut": "22222222-2", "roles": [], "permisos_efectivos": []})
            worker.reset_mock()
            d.input_rut_correccion.setText("11.111.111-1")
            d._actualizar_rut()
            worker.assert_not_called()
            self.assertTrue(d.btn_actualizar_rut.isEnabled())
            confirmar.return_value = True
            d._actualizar_rut()
            from siget_desktop.api.services import actualizar_identificacion_usuario
            worker.assert_called_once_with(actualizar_identificacion_usuario, id_usuario=2, rut="11.111.111-1")
            self.assertFalse(d.btn_actualizar_rut.isEnabled())
            d._actualizar_rut()
            self.assertEqual(worker.call_count, 1)
