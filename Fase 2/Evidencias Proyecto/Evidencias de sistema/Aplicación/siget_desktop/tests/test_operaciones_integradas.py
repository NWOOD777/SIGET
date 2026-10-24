"""
Pruebas unitarias para las operaciones REST integradas y los diálogos de la interfaz PySide6.
Valida contratos de datos enviados y recibidos, validaciones de formularios,
controles de roles RBAC y tratamiento de respuestas exitosas o errores del backend.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QMessageBox

from siget_desktop.api import services
from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.activos_dialogs import (
    DetalleModificarActivoDialog,
    RegistrarActivoDialog,
)
from siget_desktop.ui.dialogs.asignaciones_dialogs import (
    DetalleAsignacionDialog,
    RegistrarDevolucionDialog,
)
from siget_desktop.ui.dialogs.solicitudes_dialogs import (
    DetalleSolicitudDialog,
    RechazarSolicitudDialog,
    RegistrarEntregaDialog,
)
from siget_desktop.ui.dialogs.tickets_dialogs import (
    DetalleTicketDialog,
)
from siget_desktop.ui.dialogs.usuarios_dialogs import (
    AprovisionarUsuarioDialog,
    CatalogoRolesPermisosDialog,
    DetalleAccesoUsuarioDialog,
    GestionarRolesUsuarioDialog,
)
from siget_desktop.ui.views.solicitudes_view import SolicitudesView
from siget_desktop.ui.views.tickets_view import TicketsView

_qapp = QApplication.instance() or QApplication(sys.argv)


class ServicesTests(unittest.TestCase):
    """Verifica que las funciones de servicio llamen a los endpoints REST con los métodos y payloads correspondientes."""

    @patch("siget_desktop.api.services.api_client")
    def test_servicios_usuarios_rbac(self, mock_client: MagicMock):
        mock_client.post.return_value = {"id_usuario": 10, "correo": "nuevo@siget.cl"}
        res = services.aprovisionar_usuario("Ana", "Pérez", "ana@siget.cl", "11.111.111-1", "Técnico de soporte")
        self.assertEqual(res["id_usuario"], 10)
        mock_client.post.assert_called_with("/api/usuarios/aprovisionar/", json={
            "nombres": "Ana", "apellidos": "Pérez", "correo": "ana@siget.cl",
            "rut": "11.111.111-1", "rol": "Técnico de soporte",
        })

        mock_client.get.return_value = {"roles": ["Técnico de soporte"], "permisos_efectivos": []}
        acceso = services.obtener_acceso_usuario(10)
        self.assertIn("roles", acceso)
        mock_client.get.assert_called_with("/api/usuarios/10/acceso/")

        mock_client.get.return_value = [{"id_rol": 1, "nombre": "Administrador del sistema"}]
        roles = services.listar_roles_rbac()
        self.assertEqual(len(roles), 1)
        mock_client.get.assert_called_with("/api/usuarios/roles/")

        mock_client.post.return_value = {"id_usuario": 10}
        services.actualizar_roles_usuario(10, ["Administrador del sistema"])
        mock_client.post.assert_called_with("/api/usuarios/10/roles/", json={"roles": ["Administrador del sistema"]})

        mock_client.delete.return_value = {"mensaje": "Rol retirado"}
        services.retirar_rol_usuario(10, 2)
        mock_client.delete.assert_called_with("/api/usuarios/10/roles/2/")

        mock_client.post.return_value = {"mensaje": "Permiso asignado"}
        services.asignar_permiso_rol(1, codigo="REPORTES_CONSULTAR")
        mock_client.post.assert_called_with("/api/usuarios/roles/1/permisos/", json={"codigo": "REPORTES_CONSULTAR"})

        mock_client.delete.return_value = {"mensaje": "Permiso retirado"}
        services.retirar_permiso_rol(1, 5)
        mock_client.delete.assert_called_with("/api/usuarios/roles/1/permisos/5/")

    @patch("siget_desktop.api.services.api_client")
    def test_servicios_activos(self, mock_client: MagicMock):
        mock_client.post.return_value = {"id_activo": 5, "codigo_inventario": "ACT-000005"}
        res = services.crear_activo({"numero_serie": "SN123", "id_modelo": 1, "id_ubicacion": 1})
        self.assertEqual(res["codigo_inventario"], "ACT-000005")
        mock_client.post.assert_called_with("/api/activos/", json={"numero_serie": "SN123", "id_modelo": 1, "id_ubicacion": 1})

        mock_client.get.return_value = {"id_activo": 5}
        services.obtener_activo(5)
        mock_client.get.assert_called_with("/api/activos/5/")

        mock_client.patch.return_value = {"id_activo": 5}
        services.actualizar_activo(5, {"valor_adquisicion": 500000}, parcial=True)
        mock_client.patch.assert_called_with("/api/activos/5/", json={"valor_adquisicion": 500000})

        mock_client.get.return_value = []
        services.listar_marcas_activos()
        mock_client.get.assert_called_with("/api/activos/marcas/")
        services.listar_modelos_activos()
        mock_client.get.assert_called_with("/api/activos/modelos/")
        services.listar_ubicaciones_activos()
        mock_client.get.assert_called_with("/api/activos/ubicaciones/")
        services.listar_estados_activos()
        mock_client.get.assert_called_with("/api/activos/estados/")

    @patch("siget_desktop.api.services.api_client")
    def test_servicios_solicitudes_y_asignaciones(self, mock_client: MagicMock):
        mock_client.get.return_value = {"id_solicitud": 3}
        services.obtener_solicitud(3)
        mock_client.get.assert_called_with("/api/solicitudes-asignacion/3/")

        mock_client.post.return_value = {"id_solicitud": 3, "estado": "Aprobada"}
        services.aprobar_solicitud(3)
        mock_client.post.assert_called_with("/api/solicitudes-asignacion/3/aprobar/")

        mock_client.post.return_value = {"id_solicitud": 3, "estado": "Rechazada"}
        services.rechazar_solicitud(3, "Falta justificación")
        mock_client.post.assert_called_with("/api/solicitudes-asignacion/3/rechazar/", json={"motivo_rechazo": "Falta justificación"})

        mock_client.post.return_value = {"id_asignacion": 1}
        services.registrar_entrega_solicitud(3, id_activo=12, fecha_devolucion_prevista="2026-12-31")
        mock_client.post.assert_called_with("/api/solicitudes-asignacion/3/entregar/", json={
            "id_activo": 12, "fecha_devolucion_prevista": "2026-12-31",
        })

        mock_client.get.return_value = {"id_asignacion": 1}
        services.obtener_asignacion(1)
        mock_client.get.assert_called_with("/api/asignaciones/1/")

        mock_client.post.return_value = {"id_asignacion": 1, "id_ticket_asociado": None}
        services.registrar_devolucion_asignacion(1, condicion_fisica="Buen estado", motivo_devolucion="Fin contrato")
        mock_client.post.assert_called_with("/api/asignaciones/1/devolucion/", json={
            "condicion_fisica": "Buen estado",
            "motivo_devolucion": "Fin contrato",
        })

    @patch("siget_desktop.api.services.api_client")
    def test_servicios_tickets(self, mock_client: MagicMock):
        mock_client.get.return_value = {"id_ticket": 8}
        services.obtener_ticket(8)
        mock_client.get.assert_called_with("/api/tickets/8/")

        mock_client.get.return_value = []
        services.listar_prioridades_tickets()
        mock_client.get.assert_called_with("/api/tickets/prioridades/")
        services.listar_estados_tickets()
        mock_client.get.assert_called_with("/api/tickets/estados/")
        services.listar_sla_tickets()
        mock_client.get.assert_called_with("/api/tickets/sla/")


class DialogsTests(unittest.TestCase):
    """Verifica las validaciones de campos y el comportamiento de los diálogos."""

    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token_test", expires_in=3600)
        for module in ("activos", "asignaciones", "solicitudes", "tickets", "usuarios"):
            mocked = patch(f"siget_desktop.ui.dialogs.{module}_dialogs.ApiWorker")
            mocked.start()
            self.addCleanup(mocked.stop)

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def test_aprovisionar_usuario_dialog_validaciones(self):
        diag = AprovisionarUsuarioDialog()
        # Campos vacíos
        diag._ejecutar_aprovisionamiento()
        self.assertFalse(diag.lbl_mensaje.isHidden())
        self.assertIn("obligatorios", diag.lbl_mensaje.text())

        # Correo inválido
        diag.input_nombres.setText("Rodrigo")
        diag.input_apellidos.setText("López")
        diag.input_rut.setText("18.765.432-1")
        diag.input_correo.setText("correo_invalido_sin_arroba")
        diag._ejecutar_aprovisionamiento()
        self.assertFalse(diag.lbl_mensaje.isHidden())
        self.assertIn("correo válida", diag.lbl_mensaje.text())

    def test_gestionar_roles_dialog_validar_al_menos_un_rol(self):
        diag = GestionarRolesUsuarioDialog(id_usuario=5, roles_actuales=["Técnico de soporte"])
        diag.chk_solicitante.setChecked(False)
        diag.chk_tecnico.setChecked(False)
        diag.chk_admin.setChecked(False)
        diag._guardar()
        self.assertFalse(diag.lbl_mensaje.isHidden())
        self.assertIn("al menos un rol", diag.lbl_mensaje.text())

    def test_rechazar_solicitud_dialog_requiere_motivo(self):
        diag = RechazarSolicitudDialog(id_solicitud=4)
        diag._rechazar()
        self.assertFalse(diag.lbl_mensaje.isHidden())
        self.assertIn("motivo de rechazo", diag.lbl_mensaje.text())

    def test_escritorio_no_expone_registro_manual_de_tickets(self):
        from siget_desktop.ui.dialogs import tickets_dialogs
        self.assertFalse(hasattr(tickets_dialogs, "RegistrarTicketDialog"))
        self.assertFalse(hasattr(services, "crear_ticket"))

    @patch("siget_desktop.ui.dialogs.usuarios_dialogs.obtener_acceso_usuario")
    def test_detalle_acceso_usuario_dialog(self, mock_obtener: MagicMock):
        mock_obtener.return_value = {
            "nombres": "Pedro", "apellidos": "Gómez", "rut": "12.345.678-9",
            "roles": [{"id_rol": 2, "nombre": "Técnico de soporte", "descripcion": "Soporte"}],
            "permisos_efectivos": [{"codigo": "ACTIVO_VER", "nombre": "Ver activo", "descripcion": "Desc"}],
        }
        diag = DetalleAccesoUsuarioDialog(id_usuario=1)
        diag._on_datos(mock_obtener.return_value)
        self.assertIn("Pedro Gómez", diag.lbl_titulo.text())
        self.assertEqual(diag.tabla_permisos.rowCount(), 1)

    @patch("siget_desktop.ui.dialogs.usuarios_dialogs.listar_roles_rbac")
    def test_catalogo_roles_permisos_dialog(self, mock_roles: MagicMock):
        mock_roles.return_value = [
            {"id_rol": 1, "nombre": "Admin", "permisos": [{"id_permiso": 1, "codigo": "PERM_1", "nombre": "P1", "descripcion": "D1"}]}
        ]
        diag = CatalogoRolesPermisosDialog()
        diag._on_roles_cargados(mock_roles.return_value)
        self.assertEqual(diag.combo_roles.count(), 1)
        self.assertEqual(diag.tabla_permisos.rowCount(), 1)

    @patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker")
    def test_registrar_activo_dialog_inputs(self, mock_worker: MagicMock):
        diag = RegistrarActivoDialog()
        diag.combo_modelo.addItem("Modelo Test", 1)
        diag.combo_ubicacion.addItem("Bodega Central", 1)
        diag.input_serie.setText("SN-TEST-123")
        diag.input_valor.setText("600000")
        diag._guardar()
        mock_worker.assert_called()

    def test_detalle_modificar_activo_dialog_campos(self):
        diag = DetalleModificarActivoDialog(id_activo=1)
        diag._on_datos_cargados({
            "activo": {"id_activo": 1, "codigo_inventario": "ACT-000001", "numero_serie": "SN1", "estado": "Disponible"},
            "ubicaciones": [{"id_ubicacion": 1, "nombre_area": "Oficina"}],
            "estados": [{"id_estado_activo": 1, "nombre": "Disponible"}],
        })
        self.assertEqual(diag.lbl_codigo.text(), "ACT-000001")

    def test_detalle_solicitud_dialog(self):
        diag = DetalleSolicitudDialog(id_solicitud=5)
        diag._on_datos({
            "id_solicitud": 5,
            "id_categoria": 1, "categoria": {"nombre": "Notebook"},
            "id_usuario": 1, "solicitante": {"nombres": "Juan", "apellidos": "Pérez", "correo": "j@s.cl", "rut": "1-9"},
            "id_estado_solicitud": 1, "estado": {"nombre": "Pendiente"},
            "motivo": "Equipo de trabajo",
        })
        self.assertEqual(diag.lbl_categoria.text(), "Notebook")

    def test_registrar_entrega_dialog_requiere_activo(self):
        diag = RegistrarEntregaDialog(solicitud={"id_solicitud": 2, "id_categoria": 1, "categoria": {"nombre": "Notebook"}, "id_usuario": 1, "solicitante": {"nombres": "A"}})
        diag.combo_activos.clear()
        diag._ejecutar_entrega()
        self.assertFalse(diag.lbl_mensaje.isHidden())

    def test_detalle_asignacion_dialog(self):
        diag = DetalleAsignacionDialog(id_asignacion=3)
        diag._on_datos({
            "id_asignacion": 3,
            "id_activo": 1, "activo": {"codigo_inventario": "ACT-001", "numero_serie": "S1"},
            "id_solicitud": 1, "solicitud": {"id_usuario": 1, "solicitante": {"nombres": "Luis"}},
            "id_estado_asignacion": 1, "estado": {"nombre": "Activa"},
        })
        self.assertIn("ACT-001", diag.lbl_titulo.text())

    @patch("siget_desktop.ui.dialogs.asignaciones_dialogs.QMessageBox.question")
    @patch("siget_desktop.ui.dialogs.asignaciones_dialogs.ApiWorker")
    def test_registrar_devolucion_dialog(self, mock_worker: MagicMock, confirmar: MagicMock):
        diag = RegistrarDevolucionDialog(asignacion={"id_asignacion": 4, "id_activo": 1, "activo": {"codigo_inventario": "ACT-004"}})
        diag.combo_condicion.setCurrentIndex(0)
        diag.combo_motivo.setCurrentText("Otro")

        # Un motivo personalizado vacío no debe abrir la confirmación ni enviar datos.
        diag._registrar()
        self.assertIn("Especifica el motivo", diag.lbl_mensaje.text())
        confirmar.assert_not_called()
        mock_worker.assert_not_called()

        diag.input_otro.setText("Fin de proyecto")
        confirmar.return_value = QMessageBox.StandardButton.No
        diag._registrar()
        mock_worker.assert_not_called()

        confirmar.return_value = QMessageBox.StandardButton.Yes
        diag._registrar()
        mock_worker.assert_called_once_with(
            services.registrar_devolucion_asignacion,
            id_asignacion=4,
            condicion_fisica="Buen estado",
            motivo_devolucion="Fin de proyecto",
            observaciones=None,
            id_ticket_asociado=None,
        )
        mock_worker.return_value.start.assert_called_once()

    def test_detalle_ticket_dialog(self):
        diag = DetalleTicketDialog(id_ticket=12)
        diag._on_datos({
            "id_ticket": 12,
            "codigo_ticket": "TCK-000012",
            "asunto": "Falla impresora",
            "descripcion": "No responde",
            "estado": {"nombre": "Abierto"},
        })
        self.assertEqual(diag.lbl_asunto.text(), "Falla impresora")


class ViewsIntegrationTests(unittest.TestCase):
    """Verifica el control de acciones y pestañas en las vistas operativas."""

    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token_test", expires_in=3600)

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def test_solicitudes_view_pestanas_y_seleccion(self):
        view = SolicitudesView()
        self.assertEqual(view.tabs.count(), 3)
        self.assertEqual(view.tabs.tabText(0), "Solicitudes de asignación")
        self.assertEqual(view.tabs.tabText(1), "Asignaciones y devoluciones")
        self.assertEqual(view.tabs.tabText(2), "Historial y Trazabilidad")
        self.assertIs(view.tabs.widget(2), view.tab_historial)

        # Sin selección, botones deshabilitados
        self.assertFalse(view.btn_ver_detalle_sol.isEnabled())
        self.assertFalse(view.btn_aprobar.isEnabled())
        self.assertFalse(view.btn_rechazar.isEnabled())
        self.assertFalse(view.btn_entregar.isEnabled())

        # Administrador con solicitud Pendiente
        current_session.update_user_info({
            "id_usuario": 1,
            "roles": ["Administrador del sistema"],
            "acceso_escritorio": True,
        })
        view._solicitudes_cargadas = [
            {"id_solicitud": 1, "id_estado_solicitud": 1, "estado": {"nombre": "Pendiente"}},
            {"id_solicitud": 2, "id_estado_solicitud": 1, "estado": {"nombre": "Aprobada"}},
        ]
        view.tabla.setRowCount(2)
        view.tabla.selectRow(0)
        view._on_seleccion_solicitud_cambiada()
        self.assertTrue(view.btn_aprobar.isEnabled())
        self.assertTrue(view.btn_rechazar.isEnabled())
        self.assertFalse(view.btn_entregar.isEnabled())

        # Seleccionar solicitud Aprobada
        view.tabla.selectRow(1)
        view._on_seleccion_solicitud_cambiada()
        self.assertFalse(view.btn_aprobar.isEnabled())
        self.assertFalse(view.btn_rechazar.isEnabled())

        # Técnico con solicitud Aprobada
        current_session.update_user_info({
            "id_usuario": 2,
            "roles": ["Técnico de soporte"],
            "acceso_escritorio": True,
        })
        view.actualizar_permisos_ui()
        view.tabla.selectRow(1)
        view._on_seleccion_solicitud_cambiada()
        self.assertTrue(view.btn_entregar.isEnabled())

    def test_asignaciones_devolucion_rbac_tecnico(self):
        view = SolicitudesView()
        current_session.update_user_info({
            "id_usuario": 2,
            "roles": ["Técnico de soporte"],
            "acceso_escritorio": True,
        })
        view._asignaciones_cargadas = [
            {"id_asignacion": 10, "id_estado_asignacion": 1, "estado": {"nombre": "Activa"}, "fecha_finalizacion": None},
            {"id_asignacion": 11, "id_estado_asignacion": 1, "estado": {"nombre": "Finalizada"}, "fecha_finalizacion": "2026-10-15"},
        ]
        view.tabla_asignaciones.setRowCount(2)

        # Asignación activa seleccionada: técnico puede devolver
        view.tabla_asignaciones.selectRow(0)
        view._on_seleccion_asignacion_cambiada()
        self.assertTrue(view.btn_devolver.isEnabled())

        # Asignación finalizada seleccionada: devolver inhabilitado
        view.tabla_asignaciones.selectRow(1)
        view._on_seleccion_asignacion_cambiada()
        self.assertFalse(view.btn_devolver.isEnabled())

    def test_tickets_view_habilitacion_registro_y_bloqueo_atencion(self):
        current_session.update_user_info({
            "id_usuario": 2,
            "roles": ["Técnico de soporte"],
            "acceso_escritorio": True,
        })
        view = TicketsView()
        view.actualizar_permisos_ui()
        self.assertFalse(hasattr(view, "btn_nuevo_ticket"))
        self.assertFalse(view.btn_atender.isEnabled())
        self.assertIn("no está disponible", view.btn_atender.toolTip())

        # Seleccionar un ticket permite consultar su detalle, sin habilitar atención.
        view._tickets_cargados = [{"id_ticket": 1}]
        view.tabla.setRowCount(1)
        view.tabla.selectRow(0)
        self.assertTrue(view.btn_ver_detalle.isEnabled())
        self.assertFalse(view.btn_atender.isEnabled())


if __name__ == "__main__":
    unittest.main()
