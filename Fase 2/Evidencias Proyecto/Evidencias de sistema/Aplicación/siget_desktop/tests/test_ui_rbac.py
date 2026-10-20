"""
Pruebas de interfaz gráfica PySide6 y validación visual de RBAC.
Se ejecutan mediante el backend de plataforma 'offscreen' para funcionar
de manera headless en entornos de integración continua o terminales sin display físico.
"""

import os
import sys
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from siget_desktop.auth.session import current_session
from siget_desktop.ui.main_window import MainWindow
from siget_desktop.ui.views.activos_view import ActivosView
from siget_desktop.ui.views.dashboard_view import DashboardView
from siget_desktop.ui.views.solicitudes_view import SolicitudesView
from siget_desktop.ui.views.usuarios_view import UsuariosView

# Instancia global de QApplication para toda la ejecución de pruebas
_qapp = QApplication.instance() or QApplication(sys.argv)


class UiRbacTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()

    def tearDown(self):
        current_session.clear()

    def test_dashboard_muestra_roles_y_permisos(self):
        current_session.update_user_info({
            "id_usuario": 1,
            "nombre_completo": "Laura Técnico",
            "correo": "laura@siget.cl",
            "roles": ["Técnico de soporte"],
            "permisos": ["CATALOGO_CONSULTAR", "TICKET_ATENDER"],
            "acceso_escritorio": True,
        })
        dash = DashboardView()
        self.assertEqual(dash.lbl_nombre.text(), "Laura Técnico")
        self.assertEqual(dash.lbl_correo.text(), "laura@siget.cl")
        # Debe haber al menos 1 badge de rol
        self.assertTrue(dash.layout_badges.count() >= 1)
        # Debe haber al menos 2 permisos listados
        self.assertTrue(dash.layout_lista_perm.count() >= 2)

    def test_activos_view_rbac_boton_nuevo_activo(self):
        # Para técnico: deshabilitado
        current_session.update_user_info({
            "id_usuario": 2,
            "roles": ["Técnico de soporte"],
            "acceso_escritorio": True,
        })
        view = ActivosView()
        view.actualizar_permisos_ui()
        self.assertFalse(view.btn_nuevo_activo.isEnabled())

        # Para administrador: habilitado
        current_session.update_user_info({
            "id_usuario": 3,
            "roles": ["Administrador del sistema"],
            "acceso_escritorio": True,
        })
        view.actualizar_permisos_ui()
        self.assertFalse(view.btn_nuevo_activo.isEnabled())

    def test_solicitudes_view_rbac_botones_accion(self):
        # Técnico
        current_session.update_user_info({
            "id_usuario": 2,
            "roles": ["Técnico de soporte"],
            "acceso_escritorio": True,
        })
        view = SolicitudesView()
        view.actualizar_permisos_ui()
        self.assertFalse(view.btn_aprobar.isEnabled())
        self.assertFalse(view.btn_rechazar.isEnabled())
        self.assertFalse(view.btn_entregar.isEnabled())

        # Administrador
        current_session.update_user_info({
            "id_usuario": 3,
            "roles": ["Administrador del sistema"],
            "acceso_escritorio": True,
        })
        view.actualizar_permisos_ui()
        self.assertFalse(view.btn_aprobar.isEnabled())
        self.assertFalse(view.btn_rechazar.isEnabled())
        self.assertFalse(view.btn_entregar.isEnabled())

    def test_usuarios_view_bloqueo_rbac_para_tecnico(self):
        current_session.update_user_info({
            "id_usuario": 2,
            "roles": ["Técnico de soporte"],
            "acceso_escritorio": True,
        })
        view = UsuariosView()
        self.assertFalse(view.panel_bloqueo.isHidden())
        self.assertTrue(view.contenedor_admin.isHidden())
        self.assertFalse(view.btn_actualizar.isEnabled())

    def test_usuarios_view_habilitado_para_administrador(self):
        current_session.update_user_info({
            "id_usuario": 3,
            "roles": ["Administrador del sistema"],
            "acceso_escritorio": True,
        })
        view = UsuariosView()
        self.assertTrue(view.panel_bloqueo.isHidden())
        self.assertFalse(view.contenedor_admin.isHidden())
        self.assertTrue(view.btn_actualizar.isEnabled())

    def test_main_window_sidebar_rbac(self):
        # Técnico: ítem Usuarios inhabilitado
        current_session.update_user_info({
            "id_usuario": 2,
            "nombre_completo": "Técnico Juan",
            "roles": ["Técnico de soporte"],
            "acceso_escritorio": True,
        })
        win = MainWindow()
        win.actualizar_sesion()
        item_usuarios = win.sidebar.item(4)
        self.assertEqual(item_usuarios.flags(), Qt.ItemFlag.NoItemFlags)

        # Administrador: ítem Usuarios habilitado
        current_session.update_user_info({
            "id_usuario": 3,
            "nombre_completo": "Admin Carlos",
            "roles": ["Administrador del sistema"],
            "acceso_escritorio": True,
        })
        win.actualizar_sesion()
        self.assertTrue(bool(item_usuarios.flags() & Qt.ItemFlag.ItemIsEnabled))

    def test_cierre_sesion_limpia_tablas_y_credenciales(self):
        current_session.set_tokens("token_test", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 3,
            "roles": ["Administrador del sistema"],
            "acceso_escritorio": True,
        })
        win = MainWindow()
        win.actualizar_sesion()

        # Simular filas en las tablas
        win.view_activos.tabla.setRowCount(5)
        win.view_solicitudes.tabla.setRowCount(3)
        self.assertTrue(current_session.is_authenticated())

        # Ejecutar cierre de sesión
        win._cerrar_sesion()

        self.assertFalse(current_session.is_authenticated())
        self.assertEqual(win.view_activos.tabla.rowCount(), 0)
        self.assertEqual(win.view_solicitudes.tabla.rowCount(), 0)


if __name__ == "__main__":
    unittest.main()
