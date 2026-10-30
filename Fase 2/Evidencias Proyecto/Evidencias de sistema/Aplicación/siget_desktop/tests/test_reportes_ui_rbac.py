import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from siget_desktop.auth.session import current_session
from siget_desktop.ui.views.reportes_view import ReportesView


class ReportesUIRBACTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = QApplication.instance() or QApplication([])

    def crear_vista_con_permisos(
        self,
        autenticado: bool,
        administrador: bool,
        permiso: bool,
    ):
        vista = ReportesView()

        with (
            patch.object(current_session, "is_authenticated", return_value=autenticado),
            patch.object(current_session, "is_admin", return_value=administrador),
            patch.object(current_session, "has_permission", return_value=permiso),
        ):
            vista.actualizar_permisos_ui()

        return vista

    def test_administrador_autorizado(self):
        vista = self.crear_vista_con_permisos(True, True, True)

        self.assertTrue(vista.panel_bloqueo.isHidden())
        self.assertFalse(vista.contenedor_admin.isHidden())
        self.assertTrue(vista.btn_consultar.isEnabled())

        vista.close()

    def test_administrador_sin_permiso(self):
        vista = self.crear_vista_con_permisos(True, True, False)

        self.assertFalse(vista.panel_bloqueo.isHidden())
        self.assertTrue(vista.contenedor_admin.isHidden())

        vista.close()

    def test_tecnico_sin_permiso(self):
        vista = self.crear_vista_con_permisos(True, False, False)

        self.assertFalse(vista.panel_bloqueo.isHidden())
        self.assertTrue(vista.contenedor_admin.isHidden())

        vista.close()

    def test_usuario_no_autenticado(self):
        vista = self.crear_vista_con_permisos(False, True, True)

        self.assertFalse(vista.panel_bloqueo.isHidden())
        self.assertTrue(vista.contenedor_admin.isHidden())

        vista.close()


if __name__ == "__main__":
    unittest.main()
