"""Visibilidad de controles administrativos y técnicos en las vistas compartidas."""
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.activos_dialogs import DetalleModificarActivoDialog
from siget_desktop.ui.views.activos_view import ActivosView
from siget_desktop.ui.views.solicitudes_view import SolicitudesView

APP = QApplication.instance() or QApplication([])


class VisibilidadPerfilesUiTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token-pruebas", 3600)
        self.perfil()

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def perfil(self, rol="Técnico de soporte", permisos=None):
        current_session.update_user_info({"id_usuario": 2, "roles": [rol], "permisos": permisos if permisos is not None else ["TICKET_ATENDER"], "acceso_escritorio": True})

    def test_tecnico_solo_ve_detalle_de_activo_y_no_mantenedores(self):
        with patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker") as worker:
            dialogo = DetalleModificarActivoDialog(1)
            with patch("siget_desktop.ui.dialogs.activos_dialogs.obtener_activo", return_value={"codigo_inventario": "ACT-0001"}) as obtener, patch("siget_desktop.ui.dialogs.activos_dialogs.listar_modelos_activos") as catalogos:
                self.assertEqual(worker.call_args.args[0]()["activo"]["codigo_inventario"], "ACT-0001")
                obtener.assert_called_once_with(1)
                catalogos.assert_not_called()
        self.assertTrue(dialogo.panel_edicion.isHidden())
        self.assertTrue(dialogo.btn_guardar.isHidden())
        vista = ActivosView()
        vista.actualizar_permisos_ui()
        self.assertTrue(vista.btn_nuevo_activo.isHidden())
        self.assertTrue(vista.btn_catalogos.isHidden())
        self.perfil("Administrador del sistema", [])
        with patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker"):
            self.assertFalse(DetalleModificarActivoDialog(1).panel_edicion.isHidden())


    def test_solicitudes_oculta_acciones_del_otro_perfil_y_explica_la_entrega(self):
        vista = SolicitudesView()
        self.assertTrue(vista.btn_aprobar.isHidden())
        self.assertTrue(vista.btn_rechazar.isHidden())
        self.assertFalse(vista.btn_entregar.isHidden())
        self.assertFalse(vista.btn_devolver.isHidden())
        self.assertIn("solicitudes aprobadas", vista.lbl_descripcion_solicitudes.text())
        vista._solicitudes_cargadas = [{"id_solicitud": 1, "estado": {"nombre": "Aprobada"}}]
        vista.tabla.setRowCount(1)
        vista.tabla.selectRow(0)
        self.assertTrue(vista.btn_entregar.isEnabled())
        self.perfil("Administrador del sistema", ["TICKET_ASIGNAR"])
        vista.actualizar_permisos_ui()
        self.assertFalse(vista.btn_aprobar.isHidden())
        self.assertTrue(vista.btn_entregar.isHidden())
        self.assertTrue(vista.btn_devolver.isHidden())
