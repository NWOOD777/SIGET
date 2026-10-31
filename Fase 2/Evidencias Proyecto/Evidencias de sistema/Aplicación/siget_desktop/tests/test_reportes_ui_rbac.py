"""Visibilidad de reportes y limpieza de resultados según el acceso del usuario."""

import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.views.parque_ti_view import ParqueTIView
from siget_desktop.ui.views.reportes_view import ReportesView


class ReportesUIRBACTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ventanas: list[ReportesView] = []

    def tearDown(self):
        for ventana in self.ventanas:
            ventana.close()
        limpiar_widgets()

    def crear_vista_con_permisos(self, autenticado: bool, administrador: bool, permiso: bool):
        with (
            patch.object(current_session, "is_authenticated", return_value=autenticado),
            patch.object(current_session, "is_admin", return_value=administrador),
            patch.object(current_session, "has_permission", return_value=permiso),
            patch.object(ReportesView, "cargar_categorias"),
            patch.object(ParqueTIView, "_iniciar_worker"),
        ):
            vista = ReportesView()
            self.ventanas.append(vista)
            vista.actualizar_permisos_ui()
        return vista

    def test_administrador_autorizado(self):
        vista = self.crear_vista_con_permisos(True, True, True)
        self.assertTrue(vista.panel_bloqueo.isHidden())
        self.assertTrue(vista.contenedor_admin.isVisibleTo(vista))
        self.assertTrue(vista.btn_consultar.isEnabled())

    def test_administrador_sin_permiso(self):
        vista = self.crear_vista_con_permisos(True, True, False)
        self.assertFalse(vista.panel_bloqueo.isHidden())
        self.assertFalse(vista.contenedor_admin.isVisibleTo(vista))

    def test_tecnico_sin_permiso(self):
        vista = self.crear_vista_con_permisos(True, False, False)
        self.assertFalse(vista.panel_bloqueo.isHidden())
        self.assertFalse(vista.contenedor_admin.isVisibleTo(vista))

    def test_usuario_no_autenticado(self):
        vista = self.crear_vista_con_permisos(False, True, True)
        self.assertFalse(vista.panel_bloqueo.isHidden())
        self.assertFalse(vista.contenedor_admin.isVisibleTo(vista))

    def test_revocar_permiso_oculta_las_pestanas_y_limpia_los_dos_reportes(self):
        vista = self.crear_vista_con_permisos(True, True, True)
        vista._datos_reportes = {"total_tickets_resueltos": 2}
        vista.view_parque_ti._datos = {"total_activos": 3}
        with (
            patch.object(current_session, "is_authenticated", return_value=True),
            patch.object(current_session, "is_admin", return_value=True),
            patch.object(current_session, "has_permission", return_value=False),
        ):
            vista.actualizar_permisos_ui()
        self.assertFalse(vista.contenedor_admin.isVisibleTo(vista))
        self.assertFalse(vista.view_parque_ti.isVisibleTo(vista))
        self.assertFalse(vista.panel_bloqueo.isHidden())
        self.assertIsNone(vista._datos_reportes)
        self.assertIsNone(vista.view_parque_ti._datos)


if __name__ == "__main__":
    unittest.main()
