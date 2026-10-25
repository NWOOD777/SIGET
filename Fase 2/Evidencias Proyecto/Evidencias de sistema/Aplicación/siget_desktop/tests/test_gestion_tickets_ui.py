"""Atención, asignación y transiciones de tickets desde el escritorio."""
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from siget_desktop.api import services
from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.gestion_ticket_dialog import GestionarTicketDialog
from siget_desktop.ui.views.tickets_view import TicketsView

APP = QApplication.instance() or QApplication([])
MODULO = "siget_desktop.ui.dialogs.gestion_ticket_dialog"
ESTADOS = [{"id_estado_ticket": n, "nombre": nombre} for n, nombre in enumerate(["Abierto", "En Proceso", "En Espera", "Resuelto", "Cerrado"], 1)]


class GestionTicketsUiTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token-pruebas", 3600)
        self.perfil()
        self.worker = patch(f"{MODULO}.ApiWorker").start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def perfil(self, rol="Técnico de soporte", permisos=None):
        current_session.update_user_info({"id_usuario": 2, "roles": [rol], "permisos": permisos if permisos is not None else ["TICKET_ATENDER"], "acceso_escritorio": True})

    def dialogo(self, estado="Abierto", responsable=None):
        dialogo = GestionarTicketDialog(1)
        dialogo._on_datos({"ticket": {"id_ticket": 1, "codigo_ticket": "TCK-0001", "asunto": "Soporte", "estado": {"nombre": estado}, "id_tecnico_asignado": responsable}, "estados": ESTADOS, "usuarios": [{"id_usuario": 3, "nombres": "Técnico", "apellidos": "Disponible", "activo": True, "roles": ["Técnico de soporte"]}]})
        self.worker.reset_mock()
        return dialogo

    def test_tomar_requiere_confirmacion_y_no_duplica_envio_mientras_espera(self):
        dialogo = self.dialogo()
        self.assertTrue(dialogo.btn_tomar.isEnabled())
        self.assertTrue(dialogo.panel_asignacion.isHidden())
        self.assertFalse(dialogo.btn_atencion.isEnabled())
        with patch(f"{MODULO}.confirmar_operacion", return_value=False) as confirmar:
            dialogo._tomar()
            self.worker.assert_not_called()
            confirmar.return_value = True
            dialogo._tomar()
            self.worker.assert_called_once_with(services.tomar_ticket, id_ticket=1)
            dialogo._tomar()
            self.assertEqual(self.worker.call_count, 1)
            self.assertFalse(dialogo.btn_tomar.isEnabled())

    def test_responsable_puede_atender_y_cambiar_solo_a_estados_permitidos(self):
        dialogo = self.dialogo("En Proceso", 2)
        self.assertTrue(dialogo.btn_atencion.isEnabled())
        self.assertEqual({dialogo.combo_estado.itemText(n) for n in range(dialogo.combo_estado.count())}, {"En Espera", "Resuelto"})
        with patch(f"{MODULO}.confirmar_operacion", return_value=True):
            dialogo._registrar_atencion()
            self.worker.assert_not_called()
            dialogo.input_mensaje.setPlainText("Se revisó la conexión.")
            dialogo._registrar_atencion()
            self.worker.assert_called_once_with(services.registrar_atencion_ticket, id_ticket=1, mensaje="Se revisó la conexión.")
        dialogo._on_error(RuntimeError("Sin conexión"))
        self.assertTrue(dialogo.btn_atencion.isEnabled())
        self.assertIn("Sin conexión", dialogo.lbl_mensaje.text())

    def test_cambio_de_estado_se_envia_con_id_del_catalogo_y_motivo(self):
        dialogo = self.dialogo("Abierto", 2)
        dialogo.input_mensaje.setPlainText("Comienza el diagnóstico.")
        with patch(f"{MODULO}.confirmar_operacion", return_value=True):
            dialogo._cambiar_estado()
        self.worker.assert_called_once_with(services.cambiar_estado_ticket, id_ticket=1, id_estado_ticket=2, mensaje="Comienza el diagnóstico.")

    def test_resuelto_solo_ofrece_cierre_y_cerrado_no_admite_escritura(self):
        dialogo = self.dialogo("Resuelto", 2)
        self.assertFalse(dialogo.btn_atencion.isEnabled())
        self.assertEqual(dialogo.combo_estado.currentText(), "Cerrado")
        self.assertTrue(dialogo.btn_estado.isEnabled())
        cerrado = self.dialogo("Cerrado", 2)
        self.assertFalse(cerrado.btn_estado.isEnabled())
        self.assertFalse(cerrado.btn_atencion.isEnabled())
        self.assertTrue(cerrado.btn_tomar.isHidden())

    def test_otro_tecnico_no_puede_atender_ni_reasignar(self):
        dialogo = self.dialogo("En Proceso", 3)
        self.assertFalse(dialogo.btn_atencion.isEnabled())
        self.assertFalse(dialogo.btn_estado.isEnabled())
        self.assertTrue(dialogo.panel_asignacion.isHidden())
        dialogo._registrar_atencion()
        dialogo._asignar()
        self.worker.assert_not_called()

    def test_admin_solo_asigna_y_exige_motivo(self):
        self.perfil("Administrador del sistema", ["TICKET_ASIGNAR"])
        dialogo = self.dialogo()
        self.assertTrue(dialogo.panel_atencion.isHidden())
        self.assertFalse(dialogo.panel_asignacion.isHidden())
        with patch(f"{MODULO}.confirmar_operacion", return_value=True):
            dialogo._asignar()
            self.worker.assert_not_called()
            dialogo.input_mensaje.setPlainText("Asignación por especialidad.")
            dialogo._asignar()
        self.worker.assert_called_once_with(services.asignar_ticket, id_ticket=1, id_tecnico_asignado=3, motivo="Asignación por especialidad.")

    def test_sin_permiso_no_aparecen_acciones_y_admin_no_ve_atender(self):
        self.perfil(permisos=[])
        vista = TicketsView()
        self.assertTrue(vista.btn_atender.isHidden())
        self.assertTrue(vista.btn_asignar.isHidden())
        self.perfil("Administrador del sistema", ["TICKET_ASIGNAR"])
        vista.actualizar_permisos_ui()
        self.assertTrue(vista.btn_atender.isHidden())
        self.assertFalse(vista.btn_asignar.isHidden())

    def test_al_guardar_recarga_y_al_cerrar_sesion_descarta_respuestas(self):
        dialogo = self.dialogo("Abierto", 2)
        with patch.object(dialogo, "_cargar_datos") as cargar:
            dialogo._on_operacion({})
            self.assertTrue(dialogo.hubo_cambios)
            cargar.assert_called_once()
        dialogo._cargar_datos()
        callback = self.worker.return_value.signals.finished.connect.call_args.args[0]
        current_session.clear()
        callback({"ticket": {"asunto": "Respuesta tardía"}})
        self.assertNotIn("Respuesta tardía", dialogo.lbl_titulo.text())

    def test_boton_atender_abre_la_gestion_del_ticket_y_actualiza_el_listado(self):
        vista = TicketsView()
        vista._on_datos_cargados([{"id_ticket": 1, "estado": {"nombre": "Abierto"}, "id_tecnico_asignado": None}])
        vista.tabla.selectRow(0)
        with patch("siget_desktop.ui.views.tickets_view.GestionarTicketDialog") as dialogo, patch.object(vista, "cargar_tickets") as cargar, patch("siget_desktop.ui.views.tickets_view.notificar_cambio") as notificar:
            dialogo.return_value.hubo_cambios = True
            vista.btn_atender.click()
            dialogo.assert_called_once_with(1, vista)
            dialogo.return_value.exec.assert_called_once()
            cargar.assert_called_once()
            notificar.assert_called_once_with(vista)

    def test_servicios_utilizan_los_contratos_existentes_sin_acceder_a_postgres(self):
        with patch("siget_desktop.api.services.api_client") as cliente:
            cliente.post.return_value = cliente.patch.return_value = {"id_ticket": 1}
            services.tomar_ticket(1)
            cliente.post.assert_called_with("/api/tickets/1/tomar/", json={})
            services.registrar_atencion_ticket(1, "Detalle")
            cliente.post.assert_called_with("/api/tickets/1/atenciones/", json={"mensaje": "Detalle"})
            services.cambiar_estado_ticket(1, 2, "Motivo")
            cliente.patch.assert_called_with("/api/tickets/1/estado/", json={"id_estado_ticket": 2, "mensaje": "Motivo"})
            services.asignar_ticket(1, 3, "Especialidad")
            cliente.post.assert_called_with("/api/tickets/1/asignar/", json={"id_tecnico_asignado": 3, "motivo": "Especialidad"})
