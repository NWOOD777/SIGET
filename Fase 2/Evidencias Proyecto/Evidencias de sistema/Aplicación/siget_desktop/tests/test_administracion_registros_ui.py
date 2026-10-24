"""Confirmación, permisos, envío asíncrono y selección de equipos del escritorio."""
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from siget_desktop.api import services
from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.views.activos_view import ActivosView
from siget_desktop.ui.views.solicitudes_view import SolicitudesView
from siget_desktop.ui.views.usuarios_view import UsuariosView

APP = QApplication.instance() or QApplication([])


class AdministracionRegistrosUiTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token-prueba", 3600)
        current_session.update_user_info({"id_usuario": 1, "roles": ["Administrador del sistema"], "acceso_escritorio": True})

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def activos(self):
        vista = ActivosView()
        vista._on_datos_cargados([{"id_activo": 8, "codigo_inventario": "ACT-0008", "numero_serie": "SN8"}])
        vista.tabla.selectRow(0)
        return vista

    def usuarios(self):
        vista = UsuariosView()
        vista._on_datos([{"id_usuario": 2, "nombres": "Usuario", "activo": True}])
        vista.tabla.selectRow(0)
        return vista

    def test_cancelar_eliminacion_de_activo_no_llama_api(self):
        vista = self.activos()
        with patch("siget_desktop.ui.views.activos_view.confirmar_operacion", return_value=False), patch("siget_desktop.ui.views.activos_view.ApiWorker") as worker:
            vista._eliminar_seleccionado()
            worker.assert_not_called()
        self.assertEqual(vista.tabla.rowCount(), 1)

    def test_eliminar_activo_envia_id_una_vez_y_recupera_controles_ante_error(self):
        vista = self.activos()
        with patch("siget_desktop.ui.views.activos_view.confirmar_operacion", return_value=True), patch("siget_desktop.ui.views.activos_view.ApiWorker") as worker:
            vista._eliminar_seleccionado()
            vista._eliminar_seleccionado()
            self.assertEqual(worker.call_count, 1)
            self.assertEqual(worker.call_args.kwargs, {"id_activo": 8})
            self.assertFalse(vista.btn_eliminar.isEnabled())
            vista._terminar_eliminacion(Exception("Activo con movimientos"), current_session.generation)
        self.assertTrue(vista.btn_eliminar.isEnabled())
        self.assertEqual(vista.tabla.rowCount(), 1)
        self.assertIn("movimientos", vista.lbl_mensaje.text())

    def test_cancelar_eliminar_o_desactivar_usuario_no_llama_api(self):
        vista = self.usuarios()
        with patch("siget_desktop.ui.views.usuarios_view.confirmar_operacion", return_value=False), patch("siget_desktop.ui.views.usuarios_view.ApiWorker") as worker:
            vista._eliminar_seleccionado()
            vista._cambiar_estado_seleccionado()
            worker.assert_not_called()

    def test_usuario_envia_eliminacion_o_estado_con_id_seleccionado(self):
        for eliminar, activo in ((True, True), (False, True), (False, False)):
            vista = self.usuarios()
            vista._usuarios_cargados[0]["activo"] = activo
            with patch("siget_desktop.ui.views.usuarios_view.confirmar_operacion", return_value=True), patch("siget_desktop.ui.views.usuarios_view.ApiWorker") as worker:
                vista._administrar_seleccionado(eliminar)
                esperado = {"id_usuario": 2} if eliminar else {"id_usuario": 2, "activo": not activo}
                self.assertEqual(worker.call_args.kwargs, esperado)
                self.assertFalse(vista.btn_cambiar_estado.isEnabled())
                vista._terminar_administracion(Exception("Registro protegido"), current_session.generation)
            self.assertTrue(vista.btn_cambiar_estado.isEnabled())

    def test_propia_cuenta_no_ofrece_baja_y_tecnico_no_elimina(self):
        vista = self.usuarios()
        vista._usuarios_cargados[0]["id_usuario"] = 1
        vista._on_seleccion_cambiada()
        self.assertFalse(vista.btn_eliminar.isEnabled())
        self.assertFalse(vista.btn_cambiar_estado.isEnabled())
        with patch("siget_desktop.ui.views.usuarios_view.ApiWorker") as worker:
            vista._eliminar_seleccionado()
            vista._cambiar_estado_seleccionado()
            worker.assert_not_called()
        activos = self.activos()
        current_session.roles = ["Técnico de soporte"]
        activos.actualizar_permisos_ui()
        self.assertFalse(activos.btn_eliminar.isEnabled())
        with patch("siget_desktop.ui.views.activos_view.ApiWorker") as worker:
            activos._eliminar_seleccionado()
            worker.assert_not_called()

    def test_historial_permite_elegir_equipo_sin_conocer_ids(self):
        vista = SolicitudesView()
        with patch("siget_desktop.ui.views.solicitudes_view.ApiWorker") as worker:
            vista.tabs.setCurrentIndex(2)
            worker.assert_called_once()
            vista._equipos_historial_cargados([{"codigo_inventario": "ACT-0008", "numero_serie": "SN8", "modelo": "Modelo"}], current_session.generation)
            self.assertIn("SN8", vista.combo_equipo_historial.itemText(1))
            vista._seleccionar_equipo_historial(1)
            self.assertEqual(worker.call_args.kwargs, {"search": "ACT-0008"})
            self.assertEqual(vista.input_search_historial.text(), "ACT-0008")

    def test_respuesta_de_sesion_anterior_no_modifica_selector(self):
        vista = SolicitudesView()
        anterior = current_session.generation
        current_session.set_tokens("otro-token", 3600)
        vista._equipos_historial_cargados([{"codigo_inventario": "PRIVADO"}], anterior)
        self.assertEqual(vista.combo_equipo_historial.count(), 1)

    def test_historial_muestra_quien_registro_el_cambio_de_estado(self):
        vista = SolicitudesView()
        vista._on_historial_cargado({"activo": {"codigo_inventario": "ACT-0008"}, "movimientos": [{"tipo": "cambio_estado", "fecha": "2026-10-24", "estado": "En revisión", "registrado_por": {"nombres": "Administrador", "apellidos": "Prueba"}}]})
        item = vista.tabla_historial.item(0, 2)
        assert item is not None
        self.assertIn("Administrador", item.text())

    def test_contratos_de_las_tres_operaciones_administrativas(self):
        with patch.object(services.api_client, "delete", return_value=None) as borrar:
            self.assertEqual(services.eliminar_activo(8), {})
            borrar.assert_called_once_with("/api/activos/8/")
        with patch.object(services.api_client, "delete", return_value=None) as borrar:
            self.assertEqual(services.eliminar_usuario(2), {})
            borrar.assert_called_once_with("/api/usuarios/2/")
        with patch.object(services.api_client, "patch", return_value={"id_usuario": 2, "activo": False}) as actualizar:
            self.assertFalse(services.cambiar_estado_usuario(2, False)["activo"])
            actualizar.assert_called_once_with("/api/usuarios/2/", json={"activo": False})
