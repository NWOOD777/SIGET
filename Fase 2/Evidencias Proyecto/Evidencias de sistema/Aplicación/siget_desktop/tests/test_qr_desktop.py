"""Flujo de etiquetas, lotes, cancelación y permisos del escritorio."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from typing import Any
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication

from siget_desktop.api.client import ConnectionApiError, ForbiddenApiError, ServerApiError
from siget_desktop.api.qr_services import generar_etiqueta_qr, generar_etiquetas_qr
from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.activos_dialogs import DetalleModificarActivoDialog
from siget_desktop.ui.dialogs.qr_dialogs import EtiquetasQRDialog
from siget_desktop.ui.qr_labels import guardar_pdf_etiquetas
from siget_desktop.ui.views.activos_view import ActivosView

APP = QApplication.instance() or QApplication([])
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"><path d="M 10 10 H 290 V 290 H 10 Z"/></svg>'


def etiqueta(pk=1):
    return {
        "id_activo": pk,
        "id_qr": pk,
        "codigo_inventario": f"ACT-{pk:04d}",
        "payload_qr": f"ACT-{pk:04d}",
        "numero_serie": f"SERIE-{pk}",
        "marca": "Marca",
        "modelo": "Modelo",
        "formato_imagen": "SVG",
        "fecha_generacion": "2026-10-28T12:00:00Z",
        "veces_reimpreso": 0,
        "svg": SVG,
    }


class EtiquetasDesktopTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()
        current_session.set_tokens("token-prueba", 3600)
        current_session.update_user_info({"roles": ["Administrador del sistema"], "acceso_escritorio": True})
        inicio = patch("siget_desktop.ui.dialogs.qr_dialogs.QTimer.singleShot")
        inicio.start()
        self.addCleanup(inicio.stop)

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def vista(self):
        vista = ActivosView()
        vista._on_datos_cargados([etiqueta(1), etiqueta(2)])
        vista.tabla.selectRow(0)
        return vista

    def test_acciones_qr_ocultas_para_tecnico_y_seleccion_multiple_solo_admin(self):
        vista = self.vista()
        self.assertFalse(vista.acciones_qr.isHidden())
        self.assertTrue(vista.btn_generar_qr.isEnabled())
        current_session.roles = ["Técnico de soporte"]
        vista.actualizar_permisos_ui()
        self.assertTrue(vista.acciones_qr.isHidden())
        with patch("siget_desktop.ui.views.activos_view.EtiquetasQRDialog") as dialogo:
            vista._abrir_etiquetas(False)
            dialogo.assert_not_called()

    def test_seleccion_lote_deshabilita_acciones_individuales_y_envia_ids(self):
        vista = self.vista()
        seleccion = vista.tabla.selectionModel()
        seleccion.select(vista.tabla.model().index(1, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.assertTrue(vista.btn_imprimir_lote.isEnabled())
        self.assertFalse(vista.btn_ver_detalle.isEnabled())
        self.assertFalse(vista.btn_eliminar.isEnabled())
        self.assertFalse(vista.btn_generar_qr.isEnabled())
        with (
            patch("siget_desktop.ui.views.activos_view.confirmar_operacion", return_value=True),
            patch("siget_desktop.ui.views.activos_view.EtiquetasQRDialog") as dialogo,
        ):
            dialogo.return_value.etiquetas = []
            vista._abrir_etiquetas(True)
            self.assertEqual(dialogo.call_args.args[0], [1, 2])

    def test_acciones_individuales_usan_la_fila_seleccionada_aunque_el_foco_este_en_otra(self):
        vista = self.vista()
        seleccion = vista.tabla.selectionModel()
        seleccion.setCurrentIndex(vista.tabla.model().index(1, 0), QItemSelectionModel.SelectionFlag.NoUpdate)
        self.assertEqual(vista.tabla.currentRow(), 1)
        self.assertEqual(vista._obtener_id_activo_seleccionado(), 1)
        with patch("siget_desktop.ui.views.activos_view.confirmar_operacion", return_value=False) as confirmar:
            vista._eliminar_seleccionado()
            self.assertIn("ACT-0001", confirmar.call_args.args[2])

    def test_cancelar_generacion_no_abre_dialogo_ni_consulta_proveedor(self):
        vista = self.vista()
        with (
            patch("siget_desktop.ui.views.activos_view.confirmar_operacion", return_value=False),
            patch("siget_desktop.ui.views.activos_view.EtiquetasQRDialog") as dialogo,
        ):
            vista._abrir_etiquetas(False)
            dialogo.assert_not_called()

    def test_ficha_habilita_reimpresion_solo_si_existe_asociacion(self):
        with patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker"):
            dialogo = DetalleModificarActivoDialog(1)
        dialogo._on_datos_cargados({"activo": etiqueta(), "qr": {"generado": False}})
        self.assertFalse(dialogo.btn_reimprimir_qr.isEnabled())
        dialogo._on_datos_cargados({"activo": etiqueta(), "qr": {"generado": True}})
        self.assertTrue(dialogo.btn_reimprimir_qr.isEnabled())
        with (
            patch("siget_desktop.ui.dialogs.activos_dialogs.confirmar_operacion", return_value=True),
            patch("siget_desktop.ui.dialogs.activos_dialogs.EtiquetasQRDialog") as qr,
        ):
            dialogo._abrir_qr(True)
            self.assertTrue(qr.call_args.kwargs["reimprimir"])

    def test_generacion_api_envia_opcion_y_timeout_por_operacion(self):
        with patch("siget_desktop.api.qr_services.api_client.request", return_value=etiqueta()) as request:
            self.assertEqual(generar_etiqueta_qr(1, reimprimir=True)["payload_qr"], "ACT-0001")
            self.assertEqual(request.call_args.kwargs["json"], {"reimprimir": True})
            self.assertGreaterEqual(request.call_args.kwargs["timeout"], 130)

    def test_lote_conserva_exitos_y_aisla_fallos_por_activo(self):
        with patch(
            "siget_desktop.api.qr_services.generar_etiqueta_qr", side_effect=[etiqueta(1), ConnectionApiError("Sin conexión"), etiqueta(3)]
        ) as generar:
            resultado = generar_etiquetas_qr([1, 2, 3])
        self.assertEqual([e["id_activo"] for e in resultado["etiquetas"]], [1, 3])
        self.assertEqual([e["id_activo"] for e in resultado["errores"]], [2])
        self.assertEqual(generar.call_count, 3)

    def test_cancelar_lote_detiene_solicitudes_pendientes(self):
        cancelacion = Event()

        def generar(pk, **kwargs):
            cancelacion.set()
            return etiqueta(pk)

        with patch("siget_desktop.api.qr_services.generar_etiqueta_qr", side_effect=generar) as funcion:
            resultado = generar_etiquetas_qr([1, 2], cancelacion=cancelacion)
            self.assertEqual(funcion.call_count, 1)
            self.assertEqual(len(resultado["etiquetas"]), 1)
        dialogo = EtiquetasQRDialog([1, 2])
        dialogo.reject()
        self.assertTrue(dialogo._cancelacion.is_set())

    def test_lote_detiene_operaciones_al_perder_autorizacion(self):
        with patch("siget_desktop.api.qr_services.generar_etiqueta_qr", side_effect=ForbiddenApiError("Sin permiso")) as generar:
            with self.assertRaises(ForbiddenApiError):
                generar_etiquetas_qr([1, 2])
            self.assertEqual(generar.call_count, 1)

    def test_lote_rechaza_ids_duplicados_vacios_y_mas_de_cincuenta(self):
        casos: list[Any] = [[], [1, 1], [True], [0], list(range(1, 52))]
        for ids in casos:
            with self.subTest(ids=ids), patch("siget_desktop.api.qr_services.generar_etiqueta_qr") as generar:
                with self.assertRaises(ValueError):
                    generar_etiquetas_qr(ids)
                generar.assert_not_called()

    def test_respuesta_incompleta_o_de_otro_activo_se_rechaza(self):
        for datos in ({}, etiqueta(2), {**etiqueta(), "formato_imagen": "PNG"}, {**etiqueta(), "payload_qr": "OTRO"}):
            with self.subTest(datos=datos), patch("siget_desktop.api.qr_services.api_client.request", return_value=datos):
                with self.assertRaises(ServerApiError):
                    generar_etiqueta_qr(1)

    def test_reintentar_solo_solicita_pendientes_sin_duplicar_exitos(self):
        dialogo = EtiquetasQRDialog([1, 2])
        dialogo._recibir({"etiquetas": [etiqueta(1)], "errores": [{"id_activo": 2, "detail": "Proveedor temporalmente no disponible"}]})
        self.assertTrue(dialogo.btn_reintentar.isEnabled())
        self.assertTrue(dialogo.btn_pdf.isEnabled())
        with (
            patch("siget_desktop.ui.dialogs.qr_dialogs.confirmar_operacion", return_value=True),
            patch("siget_desktop.ui.dialogs.qr_dialogs.ApiWorker") as worker,
        ):
            dialogo._reintentar()
            self.assertEqual(worker.call_args.args[1], [2])
        dialogo._recibir({"etiquetas": [etiqueta(2)], "errores": []})
        self.assertEqual(len(dialogo.etiquetas), 2)
        self.assertEqual(dialogo.combo_etiqueta.count(), 2)
        self.assertTrue(dialogo.btn_reintentar.isHidden())
        self.assertTrue(dialogo.vista_svg.renderer().isValid())

    def test_sesion_cerrada_no_genera_ni_exporta(self):
        dialogo = EtiquetasQRDialog([1])
        dialogo._recibir({"etiquetas": [etiqueta()], "errores": []})
        current_session.clear()
        with (
            patch("siget_desktop.ui.dialogs.qr_dialogs.ApiWorker") as worker,
            patch("siget_desktop.ui.dialogs.qr_dialogs.QFileDialog.getSaveFileName") as guardar,
        ):
            dialogo._generar()
            dialogo._guardar_pdf()
            worker.assert_not_called()
            guardar.assert_not_called()

    def test_pdf_vectorial_y_escritura_atomica_ante_svg_invalido(self):
        with TemporaryDirectory() as tmp:
            salida = Path(tmp) / "etiquetas.pdf"
            guardar_pdf_etiquetas(str(salida), [etiqueta() for _ in range(25)])
            self.assertTrue(salida.read_bytes().startswith(b"%PDF-"))
            self.assertGreater(salida.stat().st_size, 1000)
            original = salida.read_bytes()
            with self.assertRaises(ValueError):
                guardar_pdf_etiquetas(str(salida), [{**etiqueta(), "svg": "incorrecto"}])
            self.assertEqual(salida.read_bytes(), original)
            with self.assertRaises(ValueError):
                guardar_pdf_etiquetas(str(Path(tmp) / "vacio.pdf"), [])
            self.assertFalse((Path(tmp) / "vacio.pdf").exists())
