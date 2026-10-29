"""Cierre técnico de escritorio: UI y HTTP simulado, nunca backend real."""
import ast
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from siget_desktop.api import services
from siget_desktop.api.client import ApiError
from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.cierre_tecnico_dialog import CierreTecnicoDialog, ESPACIOS_CIERRE, puede_cerrar_tecnicamente
from siget_desktop.ui.dialogs.gestionar_repuestos_ot_dialog import GestionarRepuestosOTDialog
from siget_desktop.ui.views.ordenes_trabajo_view import OrdenesTrabajoView
from siget_desktop.ui.workers import ApiWorker

APP = QApplication.instance() or QApplication([])
MODULO = "siget_desktop.ui.dialogs.cierre_tecnico_dialog"
ORDEN = {"id_orden": 1, "codigo_ot": "OT-0001", "estado": "En Reparación", "id_tecnico_responsable": 99}
RESULTADO = {"id_orden": 1, "estado": "Completada", "resultado": "NO_REPARABLE", "id_cierre_tecnico": 3,
             "fecha_cierre": "2026-10-29T14:00:00Z", "id_activo": 2, "estado_activo": "Dado de baja",
             "id_ticket": 4, "estado_ticket": "Resuelto"}


class CierreTecnicoUITests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token-pruebas", 3600)
        current_session.update_user_info({"id_usuario": 2, "roles": ["Técnico de soporte"],
            "permisos": ["OT_GESTIONAR", "TICKET_ATENDER"], "acceso_escritorio": True})
        self.iniciar = patch.object(ApiWorker, "start")
        self.start = self.iniciar.start()
        self.addCleanup(self.iniciar.stop)
        self.ventanas = []

    def tearDown(self):
        current_session.clear()
        for ventana in self.ventanas:
            ventana.close()
            ventana.deleteLater()
        limpiar_widgets()
        for worker in list(ApiWorker._activos):
            if not worker.isRunning(): worker._liberar()

    def dialogo(self, estado="En Reparación"):
        d = CierreTecnicoDialog({**ORDEN, "estado": estado})
        self.ventanas.append(d)
        return d

    def datos_descarte(self, d):
        d.combo_resultado.setCurrentIndex(d.combo_resultado.findData("NO_REPARABLE"))
        d.informe.setPlainText("Placa irreparable")

    def test_resultados_por_estado_y_campos(self):
        for estado in ("En Diagnóstico", "En Reparación", "Pausada", "Completada"):
            d = self.dialogo(estado)
            self.assertEqual(d.combo_resultado.findData("REPARACION_EXITOSA") >= 0, estado == "En Reparación")
            self.assertEqual(d.combo_resultado.findData("NO_REPARABLE") >= 0, estado in ("En Diagnóstico", "En Reparación"))
            self.datos_descarte(d)
            self.assertEqual(d.btn_guardar.isEnabled(), estado in ("En Diagnóstico", "En Reparación"))
        d = self.dialogo()
        d.combo_resultado.setCurrentIndex(1)
        self.assertFalse(d.campos_exito.isHidden())
        self.assertTrue(d.campos_descarte.isHidden())
        d.combo_resultado.setCurrentIndex(2)
        self.assertTrue(d.campos_exito.isHidden())
        self.assertFalse(d.campos_descarte.isHidden())
        self.assertIn("Dado de baja", d.advertencia.text())

    def test_campos_obligatorios_y_espacios_unicode(self):
        d = self.dialogo()
        self.datos_descarte(d)
        with patch(MODULO + ".confirmar_operacion") as confirmar:
            for texto in ("", *ESPACIOS_CIERRE, ESPACIOS_CIERRE):
                d.informe.setPlainText(texto)
                d.guardar()
                self.assertIsNone(d._worker)
            confirmar.assert_not_called()
        d.combo_resultado.setCurrentIndex(1)
        d.solucion.setPlainText("Solución")
        d.pruebas.setPlainText(ESPACIOS_CIERRE)
        d.guardar()
        self.assertIsNone(d._worker)

    def test_politica_unicode_coincide_con_backend(self):
        archivo = Path(__file__).resolve().parents[2] / "siget_web/ordenes_trabajo/validaciones_cierre.py"
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        valor = next(ast.literal_eval(n.value) for n in arbol.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "ESPACIOS_CIERRE" for t in n.targets))
        self.assertEqual(ESPACIOS_CIERRE, valor)

    def test_confirmacion_cancelada_conserva_datos(self):
        d = self.dialogo(); self.datos_descarte(d)
        with patch(MODULO + ".confirmar_operacion", return_value=False) as confirmar:
            d.guardar()
        resumen = confirmar.call_args.args[2]
        self.assertNotIn("NO_REPARABLE", resumen)
        for texto in ("Equipo no reparable", "Completada", "Dado de baja", "Resuelto"):
            self.assertIn(texto, resumen)
        self.assertIsNone(d._worker)
        self.assertEqual(d.informe.toPlainText(), "Placa irreparable")
        d.reject(); self.assertTrue(d._closed)

    def test_doble_clic_payload_y_operacion_en_curso(self):
        d = self.dialogo(); self.datos_descarte(d)
        with patch(MODULO + ".confirmar_operacion", return_value=True) as confirmar:
            d.guardar(); worker = d._worker; d.guardar()
        confirmar.assert_called_once()
        self.assertEqual(worker.kwargs, {"resultado": "NO_REPARABLE", "informe_descarte": "Placa irreparable"})
        self.assertEqual(worker.args, (1,))
        self.assertFalse(d.btn_guardar.isEnabled())
        self.assertIn("Procesando", d.lbl_estado.text())
        d.reject(); self.assertFalse(d._closed)

    def test_payload_exito_no_incluye_informe_anterior(self):
        d = self.dialogo(); self.datos_descarte(d)
        d.combo_resultado.setCurrentIndex(1)
        d.solucion.setPlainText("Solución")
        d.pruebas.setPlainText("Pruebas")
        with patch(MODULO + ".confirmar_operacion", return_value=True): d.guardar()
        self.assertEqual(d._worker.kwargs, {"resultado": "REPARACION_EXITOSA", "solucion_aplicada": "Solución", "pruebas_realizadas": "Pruebas"})

    def test_exito_cierra_dialogo(self):
        d = self.dialogo(); self.datos_descarte(d)
        with patch(MODULO + ".confirmar_operacion", return_value=True): d.guardar()
        d._worker.signals.finished.emit(RESULTADO)
        self.assertEqual(d.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(d.resultado_cierre, RESULTADO)

    def test_errores_conservan_formulario_sin_filtrar_detalles(self):
        d = self.dialogo(); self.datos_descarte(d)
        for codigo in (400, 401, 403, 404, 405, 500, None):
            with self.subTest(codigo=codigo), patch(MODULO + ".confirmar_operacion", return_value=True), patch(MODULO + ".QMessageBox.warning"):
                d.guardar()
                d._worker.signals.error.emit(ApiError("SQL_PRIVADO", status_code=codigo))
                self.assertFalse(d._closed)
                self.assertIsNone(d.resultado_cierre)
                self.assertEqual(d.informe.toPlainText(), "Placa irreparable")
                self.assertNotIn("SQL_PRIVADO", d.lbl_estado.text())
                self.assertTrue(d.btn_guardar.isEnabled())

    def test_cambio_sesion_descarta_resultados_y_cierra(self):
        d = self.dialogo(); self.datos_descarte(d)
        with patch(MODULO + ".confirmar_operacion", return_value=True): d.guardar()
        worker = d._worker
        current_session.clear()
        worker.signals.finished.emit(RESULTADO)
        self.assertIsNone(d.resultado_cierre)
        d._check_session()
        self.assertTrue(d._closed)

    def test_respuesta_incompleta_no_se_presenta_como_exito(self):
        d = self.dialogo(); self.datos_descarte(d)
        with patch(MODULO + ".confirmar_operacion", return_value=True), patch(MODULO + ".QMessageBox.warning"):
            d.guardar()
            d._worker.signals.finished.emit({})
        self.assertFalse(d._closed)
        self.assertIsNone(d.resultado_cierre)
        self.assertEqual(d.informe.toPlainText(), "Placa irreparable")

    def test_permisos_locales_y_sesion(self):
        self.assertTrue(puede_cerrar_tecnicamente())
        d = self.dialogo(); self.datos_descarte(d)
        for campo, valor in (("roles", ["Administrador del sistema"]), ("permisos", ["TICKET_ATENDER"]), ("acceso_escritorio", False)):
            anterior = getattr(current_session, campo)
            setattr(current_session, campo, valor)
            self.assertFalse(puede_cerrar_tecnicamente())
            d.guardar(); self.assertIsNone(d._worker)
            setattr(current_session, campo, anterior)
        current_session.clear()
        self.assertFalse(puede_cerrar_tecnicamente())

    def test_accion_visible_solo_si_corresponde(self):
        vista = OrdenesTrabajoView(); self.ventanas.append(vista)
        for estado in ("En Diagnóstico", "En Reparación", "Pausada", "Completada"):
            with patch.object(vista, "_orden_seleccionada", return_value={**ORDEN, "estado": estado}):
                vista._actualizar_acciones()
                self.assertEqual(not vista.btn_cierre_tecnico.isHidden(), estado in ("En Diagnóstico", "En Reparación"))
        current_session.permisos = []
        vista._actualizar_acciones()
        self.assertTrue(vista.btn_cierre_tecnico.isHidden())

    def test_refresco_tras_cierre_y_repuestos_solo_consulta(self):
        vista = OrdenesTrabajoView(); self.ventanas.append(vista)
        orden = dict(ORDEN)
        recibido = Mock(); vista.cierre_tecnico_completado.connect(recibido)
        with patch.object(vista, "_orden_seleccionada", return_value=orden), patch.object(vista, "actualizar_datos") as refrescar, patch(
            "siget_desktop.ui.views.ordenes_trabajo_view.CierreTecnicoDialog"
        ) as dialogo:
            dialogo.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialogo.return_value.resultado_cierre = RESULTADO
            vista._cerrar_tecnicamente()
            refrescar.assert_called_once()
            recibido.assert_called_once_with(RESULTADO)
            self.assertEqual(orden["estado"], "Completada")
            self.assertFalse(vista.btn_cierre_tecnico.isEnabled())
        repuestos = GestionarRepuestosOTDialog(1, "OT-0001", orden["estado"]); self.ventanas.append(repuestos)
        self.assertTrue(repuestos.formulario.isHidden())
        self.assertTrue(repuestos.btn_anular.isHidden())

    def test_refresco_vistas_relacionadas(self):
        from siget_desktop.ui.main_window import MainWindow
        ventana = Mock()
        MainWindow._refrescar_por_cierre_tecnico(ventana, RESULTADO)
        ventana.view_tickets.cargar_tickets.assert_called_once()
        ventana.view_activos.cargar_activos.assert_called_once()
        ventana.view_dashboard.actualizar_datos.assert_called_once()

    def test_fila_y_detalle_no_quedan_con_estado_anterior(self):
        vista = OrdenesTrabajoView(); self.ventanas.append(vista)
        vista._ordenes_cargadas = [dict(ORDEN)]
        vista._aplicar_filtros()
        vista.tabla.selectRow(0)
        with patch.object(vista, "actualizar_datos"), patch("siget_desktop.ui.views.ordenes_trabajo_view.CierreTecnicoDialog") as dialogo:
            dialogo.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialogo.return_value.resultado_cierre = RESULTADO
            vista._cerrar_tecnicamente()
        self.assertEqual(vista._orden_seleccionada()["estado"], "Completada")
        self.assertEqual(vista._ordenes_cargadas[0]["estado"], "Completada")
        self.assertEqual(vista.tabla.item(0, 4).text(), "Completada")
        self.assertFalse(vista.btn_pausar.isEnabled())
        self.assertFalse(vista.btn_cierre_tecnico.isEnabled())

    def test_worker_asincrono_con_http_simulado(self):
        d = self.dialogo(); self.datos_descarte(d)
        self.iniciar.stop()
        with patch(MODULO + ".confirmar_operacion", return_value=True), patch("siget_desktop.api.services.api_client.post", return_value=RESULTADO) as http:
            d.guardar()
            limite = time.monotonic() + 3
            while not d._closed and time.monotonic() < limite: QTest.qWait(10)
            self.assertTrue(d._closed)
            http.assert_called_once_with("/api/ordenes-trabajo/1/completar/", json={"resultado": "NO_REPARABLE", "informe_descarte": "Placa irreparable"})

    def test_servicio_usa_bearer_sin_campos_sensibles(self):
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = RESULTADO
        with patch("requests.Session.request", return_value=respuesta) as http:
            self.assertEqual(services.completar_orden_trabajo(1, resultado="NO_REPARABLE", informe_descarte="Informe"), RESULTADO)
        self.assertEqual(http.call_args.kwargs["headers"]["Authorization"], "Bearer token-pruebas")
        self.assertEqual(http.call_args.kwargs["json"], {"resultado": "NO_REPARABLE", "informe_descarte": "Informe"})

    def test_http_error_no_se_reintenta(self):
        for codigo in (400, 401, 403, 404, 405, 500):
            current_session.set_tokens("token-pruebas", 3600)
            respuesta = Mock(status_code=codigo); respuesta.json.return_value = {"detail": "Error simulado"}
            with patch("requests.Session.request", return_value=respuesta) as http:
                with self.assertRaises(ApiError): services.completar_orden_trabajo(1, resultado="NO_REPARABLE", informe_descarte="Informe")
            http.assert_called_once()

    def test_id_invalido_no_envia_http(self):
        with patch("siget_desktop.api.services.api_client.post") as http:
            for identificador in (0, True, "1", 2147483648):
                with self.assertRaises(ValueError): services.completar_orden_trabajo(identificador, resultado="NO_REPARABLE")
            http.assert_not_called()
