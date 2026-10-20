"""Regresiones del contrato DRF, precisión de importes y privacidad de los diálogos."""
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication, QMessageBox, QTableWidget

from siget_desktop.api import services
from siget_desktop.api.client import ApiClient, ServerApiError, ValidationApiError
from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.activos_dialogs import DetalleModificarActivoDialog
from siget_desktop.ui.dialogs.asignaciones_dialogs import DetalleAsignacionDialog, RegistrarDevolucionDialog
from siget_desktop.ui.dialogs.common import SessionDialog, monto_decimal
from siget_desktop.ui.dialogs.solicitudes_dialogs import DetalleSolicitudDialog, RegistrarEntregaDialog
from siget_desktop.ui.dialogs.usuarios_dialogs import DetalleAccesoUsuarioDialog
from siget_desktop.ui.main_window import MainWindow
from siget_desktop.ui.views.solicitudes_view import SolicitudesView

APP = QApplication.instance() or QApplication([])
SOLICITUD = {"id_solicitud": 8, "id_usuario": 3, "solicitante": {"nombres": "Camila", "apellidos": "Rojas", "correo": "camila@example.invalid"},
             "id_categoria": 2, "categoria": {"nombre": "Notebook"}, "id_estado_solicitud": 1, "estado": {"nombre": "Pendiente"}, "motivo": "Trabajo"}
ASIGNACION = {"id_asignacion": 5, "id_activo": 4, "activo": {"codigo_inventario": "ACT-000004", "modelo": "Modelo QA", "numero_serie": "SERIE-QA"},
              "id_solicitud": 8, "solicitud": SOLICITUD, "id_tecnico_entrega": 2, "tecnico_entrega": {"nombres": "Técnico", "apellidos": "QA"},
              "id_estado_asignacion": 1, "estado": {"nombre": "Activa"}, "fecha_finalizacion": None, "fecha_devolucion_prevista": None}


def texto_celda(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


class ContratosEscritorioTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("qa", 3600)
        current_session.update_user_info({"id_usuario": 1, "roles": ["Administrador del sistema"], "acceso_escritorio": True})
        self.widgets = []
        for module in ("activos", "asignaciones", "solicitudes", "tickets", "usuarios"):
            mocked = patch(f"siget_desktop.ui.dialogs.{module}_dialogs.ApiWorker")
            mocked.start()
            self.addCleanup(mocked.stop)

    def tearDown(self):
        for widget in self.widgets:
            widget.deleteLater()
        current_session.clear()
        limpiar_widgets()

    def keep(self, widget):
        self.widgets.append(widget)
        return widget

    def test_solicitudes_habilita_decision_con_estado_separado_del_id(self):
        view = self.keep(SolicitudesView())
        view._on_solicitudes_cargadas([SOLICITUD])
        view.tabla.selectRow(0)
        self.assertTrue(view.btn_aprobar.isEnabled())
        self.assertEqual(texto_celda(view.tabla, 0, 1), "Camila Rojas")
        self.assertEqual(texto_celda(view.tabla, 0, 3), "Pendiente")

    def test_detalle_solicitud_usa_objetos_y_no_identificadores(self):
        dialog = self.keep(DetalleSolicitudDialog(8))
        dialog._on_datos(SOLICITUD)
        self.assertEqual(dialog.lbl_categoria.text(), "Notebook")
        self.assertEqual(dialog.lbl_solicitante.text(), "Camila Rojas")

    @patch("siget_desktop.ui.dialogs.solicitudes_dialogs.ApiWorker")
    def test_entrega_filtra_por_nombre_real_de_categoria(self, worker):
        self.keep(RegistrarEntregaDialog(SOLICITUD))
        self.assertEqual(worker.call_args.kwargs["tipo"], "Notebook")

    def test_asignaciones_renderiza_con_ids_enteros(self):
        view = self.keep(SolicitudesView())
        view._on_asignaciones_cargadas([ASIGNACION])
        self.assertEqual(texto_celda(view.tabla_asignaciones, 0, 1), "ACT-000004")
        self.assertEqual(texto_celda(view.tabla_asignaciones, 0, 3), "Camila Rojas")
        dialog = self.keep(DetalleAsignacionDialog(5))
        dialog._on_datos(ASIGNACION)
        self.assertEqual(dialog.lbl_estado.text(), "Activa")
        self.assertEqual(dialog.lbl_fecha_prevista.text(), "Sin fecha prevista")

    def test_devolucion_rechaza_id_ticket_invalido(self):
        dialog = self.keep(RegistrarDevolucionDialog(ASIGNACION))
        dialog.combo_condicion.setCurrentIndex(1)
        dialog.input_ticket.setText("no-es-id")
        dialog._registrar()
        self.assertIn("identificador", dialog.lbl_mensaje.text())
        self.assertIsNone(dialog._worker)

    def test_acceso_usuario_acepta_roles_como_objetos(self):
        dialog = self.keep(DetalleAccesoUsuarioDialog(1))
        dialog._on_datos({"nombres": "Ana", "apellidos": "QA", "roles": [{"id_rol": 2, "nombre": "Técnico de soporte"}],
                          "permisos_efectivos": [{"id_permiso": 1, "codigo": "CATALOGO_CONSULTAR", "descripcion": "Consultar catálogo"}]})
        self.assertIn("Ana QA", dialog.lbl_titulo.text())
        self.assertIn("Técnico de soporte", dialog.lbl_roles.text())
        self.assertEqual(texto_celda(dialog.tabla_permisos, 0, 1), "CATALOGO_CONSULTAR")

    def test_montos_no_pierden_decimales_ni_aceptan_no_finitos(self):
        for value in ("650000.50", "650.000,50", "650000,50"):
            self.assertEqual(monto_decimal(value), "650000.50")
        self.assertEqual(monto_decimal("650.000"), "650000.00")
        for value in ("nan", "inf", "-1", "1.2345", "99999999999999"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                monto_decimal(value)

    def test_editar_ubicacion_no_cambia_monto_ni_fechas_nulas(self):
        dialog = self.keep(DetalleModificarActivoDialog(4))
        data = {"id_activo": 4, "numero_serie": "QA", "id_modelo": 1, "id_ubicacion": 1, "id_estado_activo": 1,
                "valor_adquisicion": "650000.50", "fecha_compra": None, "fecha_garantia": None, "estado": "Disponible"}
        dialog._on_datos_cargados({"activo": data, "modelos": [{"id_modelo": 1, "nombre": "QA"}], "ubicaciones": [{"id_ubicacion": 1}, {"id_ubicacion": 2}], "estados": [{"id_estado_activo": 1, "nombre": "Disponible"}]})
        self.assertEqual(dialog.input_valor.text(), "650000.50")
        self.assertFalse(dialog.chk_garantia.isChecked())
        dialog.combo_ubicacion.setCurrentIndex(1)
        with patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker") as worker:
            dialog._guardar_cambios()
        self.assertEqual(worker.call_args.kwargs["datos"], {"id_ubicacion": 2})

    def test_errores_de_campos_del_backend_se_muestran_al_usuario(self):
        response = MagicMock(status_code=400)
        response.json.return_value = {"numero_serie": ["Ya existe un activo con esta serie."]}
        with self.assertRaises(ValidationApiError) as error:
            ApiClient()._procesar_respuesta(response)
        self.assertIn("numero_serie", str(error.exception))
        self.assertIn("Ya existe", str(error.exception))

    def test_respuesta_malformada_no_se_convierte_en_exito(self):
        with patch.object(services.api_client, "post", return_value="HTML"):
            with self.assertRaises(ServerApiError):
                services.crear_activo({"numero_serie": "QA"})
        with patch.object(services.api_client, "get", return_value={"error": "no es lista"}):
            with self.assertRaises(ServerApiError):
                services.listar_asignaciones()

    def test_dialogo_descarta_callback_despues_de_cerrar_o_cambiar_sesion(self):
        for change in ("cerrar", "sesion"):
            dialog = self.keep(SessionDialog())
            worker = MagicMock()
            dialog._worker = worker
            callback = MagicMock()
            dialog.conectar_worker(worker, callback, callback)
            dispatch = worker.signals.finished.connect.call_args.args[0]
            if change == "cerrar":
                dialog.reject()
            else:
                current_session.set_tokens("nueva", 3600)
            dispatch({"dato": "privado"})
            callback.assert_not_called()

    def test_cerrar_sesion_limpia_asignaciones_y_caches(self):
        window = self.keep(MainWindow())
        window.view_solicitudes._on_asignaciones_cargadas([ASIGNACION])
        window.view_solicitudes._solicitudes_cargadas = [SOLICITUD]
        window._cerrar_sesion()
        self.assertEqual(window.view_solicitudes.tabla_asignaciones.rowCount(), 0)
        self.assertEqual(window.view_solicitudes._asignaciones_cargadas, [])
        self.assertEqual(window.view_solicitudes._solicitudes_cargadas, [])


    def test_invalidar_consultas_actualiza_listados_relacionados(self):
        window = self.keep(MainWindow())
        window.view_activos.tabla.setRowCount(2)
        window.view_tickets._tickets_cargados = [{"id_ticket": 1}]
        window.view_tickets.tabla.setRowCount(1)
        with patch("siget_desktop.ui.main_window.ApiWorker") as worker:
            window.invalidar_consultas(window.view_solicitudes)
        self.assertEqual(window.view_activos.tabla.rowCount(), 0)
        self.assertEqual(window.view_tickets._tickets_cargados, [])
        self.assertEqual(window.view_tickets.tabla.rowCount(), 0)
        worker.assert_called_once()

    def test_perder_rol_de_escritorio_cierra_sesion(self):
        window = self.keep(MainWindow())
        window._refrescar_perfil({"id_usuario": 1, "roles": ["Usuario solicitante"], "acceso_escritorio": False}, current_session.generation)
        self.assertFalse(current_session.is_authenticated())

    def test_decision_pendiente_no_admite_doble_envio(self):
        view = self.keep(SolicitudesView())
        view._on_solicitudes_cargadas([SOLICITUD])
        view.tabla.selectRow(0)
        with patch("siget_desktop.ui.views.solicitudes_view.ApiWorker") as worker, patch("siget_desktop.ui.views.solicitudes_view.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            view._aprobar_solicitud_seleccionada()
            view._aprobar_solicitud_seleccionada()
        worker.assert_called_once()
        self.assertFalse(view.btn_aprobar.isEnabled())
        self.assertFalse(view.btn_rechazar.isEnabled())
