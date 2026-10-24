"""
Pruebas de interfaz PySide6 de la bitácora de auditoría.
Valida la vista AuditoriaView, visualización de eventos, estados de carga y error,
el mensaje exacto de búsqueda sin coincidencias, inmutabilidad del diálogo de detalle,
seguridad contra concurrencia/cambio de sesión y controles de paginación.
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from unittest.mock import ANY, MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.auditoria_dialogs import DetalleAuditoriaDialog, formatear_fecha_auditoria
from siget_desktop.ui.dialogs.selector_auditoria import SelectorAuditoriaDialog
from siget_desktop.ui.main_window import MainWindow
from siget_desktop.ui.views.auditoria_view import (
    MENSAJE_SIN_COINCIDENCIAS,
    AuditoriaView,
)

_qapp = QApplication.instance() or QApplication(sys.argv)


class AuditoriaUiTests(unittest.TestCase):
    def setUp(self):
        current_session.clear()

    def tearDown(self):
        current_session.clear()
        limpiar_widgets()

    def test_01_bloqueo_rbac_para_tecnico(self):
        current_session.update_user_info({
            "id_usuario": 2,
            "roles": ["Técnico de soporte"],
            "acceso_escritorio": True,
        })
        view = AuditoriaView()
        view.actualizar_permisos_ui()

        self.assertFalse(view.panel_bloqueo.isHidden())
        self.assertTrue(view.contenedor_admin.isHidden())
        self.assertFalse(view.btn_actualizar.isEnabled())

    def test_02_habilitado_para_administrador_autorizado(self):
        current_session.update_user_info({
            "id_usuario": 1,
            "roles": ["Administrador del sistema"],
            "permisos": ["AUDITORIA_CONSULTAR"],
            "acceso_escritorio": True,
        })
        view = AuditoriaView()
        view.actualizar_permisos_ui()

        self.assertTrue(view.panel_bloqueo.isHidden())
        self.assertFalse(view.contenedor_admin.isHidden())
        self.assertTrue(view.btn_actualizar.isEnabled())

    def test_03_columnas_e_insercion_de_datos(self):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 1,
            "roles": ["Administrador del sistema"],
            "permisos": ["AUDITORIA_CONSULTAR"],
            "acceso_escritorio": True,
        })

        view = AuditoriaView()
        self.assertEqual(
            view.COLUMNAS,
            ["Fecha / Hora", "Usuario", "IP", "Acción", "Módulo", "Recurso"],
        )

        mock_payload = {
            "count": 2,
            "page": 1,
            "page_size": 25,
            "total_pages": 1,
            "results": [
                {
                    "id_auditoria": 101,
                    "fecha_evento": "2026-10-23T15:30:00Z",
                    "id_usuario": 1,
                    "usuario": "Carlos Admin",
                    "usuario_correo": "carlos@siget.cl",
                    "direccion_ip": "10.0.0.1",
                    "modulo": "ACTIVOS",
                    "accion": "ACTIVO_CREADO",
                    "entidad_afectada": "activo",
                    "id_registro_afectado": 10,
                    "recurso": "activo #10",
                    "detalle_evento": "Activo ACT-001 creado exitosamente.",
                },
                {
                    "id_auditoria": 100,
                    "fecha_evento": "2026-10-23T14:20:00Z",
                    "id_usuario": None,
                    "usuario": None,
                    "usuario_correo": None,
                    "direccion_ip": None,
                    "modulo": "SISTEMA",
                    "accion": "LIMPIEZA_AUTO",
                    "entidad_afectada": "sistema",
                    "id_registro_afectado": None,
                    "recurso": "sistema",
                    "detalle_evento": "Limpieza de sesiones.",
                },
            ],
        }

        view._on_datos_cargados(mock_payload, query_id=view._query_id, generation=current_session.generation)

        self.assertEqual(view.tabla.rowCount(), 2)

        # Fila 0
        def _get_text(r: int, c: int) -> str:
            item = view.tabla.item(r, c)
            assert item is not None
            return item.text()

        self.assertIn("2026-10-23", _get_text(0, 0))
        self.assertEqual(_get_text(0, 1), "Carlos Admin")
        self.assertEqual(_get_text(0, 2), "10.0.0.1")
        self.assertEqual(_get_text(0, 3), "ACTIVO_CREADO")
        self.assertEqual(_get_text(0, 4), "ACTIVOS")
        self.assertEqual(_get_text(0, 5), "activo #10")

        # Fila 1 (evento automático sin usuario ni IP)
        self.assertEqual(_get_text(1, 1), "Automático")
        self.assertEqual(_get_text(1, 2), "—")

        # Selección activa el botón 'Ver detalle'
        self.assertFalse(view.btn_ver_detalle.isEnabled())
        view.tabla.selectRow(0)
        self.assertTrue(view.btn_ver_detalle.isEnabled())

    def test_04_mensaje_sin_coincidencias_exacto(self):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 1,
            "roles": ["Administrador del sistema"],
            "permisos": ["AUDITORIA_CONSULTAR"],
            "acceso_escritorio": True,
        })

        view = AuditoriaView()
        mock_empty_payload = {
            "count": 0,
            "page": 1,
            "page_size": 25,
            "total_pages": 0,
            "results": [],
        }

        view._on_datos_cargados(mock_empty_payload, query_id=view._query_id, generation=current_session.generation)

        self.assertEqual(view.tabla.rowCount(), 0)
        self.assertFalse(view.lbl_mensaje.isHidden())
        self.assertEqual(
            view.lbl_mensaje.text(),
            "No se encontraron eventos de auditoría coincidentes con los criterios ingresados",
        )
        self.assertEqual(MENSAJE_SIN_COINCIDENCIAS, "No se encontraron eventos de auditoría coincidentes con los criterios ingresados")

    def test_05_detalle_dialog_es_de_solo_lectura_y_sin_botones_escritura(self):
        evento = {
            "id_auditoria": 42,
            "fecha_evento": "2026-10-23T18:00:00Z",
            "id_usuario": 1,
            "usuario": "Carlos Admin",
            "usuario_correo": "carlos@siget.cl",
            "direccion_ip": "192.168.1.50",
            "modulo": "ORDENES_TRABAJO",
            "accion": "OT_PAUSADA",
            "entidad_afectada": "orden_trabajo",
            "id_registro_afectado": 7,
            "recurso": "orden_trabajo #7",
            "detalle_evento": "Pausa por espera de repuesto.",
        }

        dialogo = DetalleAuditoriaDialog(evento)

        # Comprobar que el campo de texto es de solo lectura
        self.assertTrue(dialogo.txt_detalle.isReadOnly())
        self.assertIn("Pausa por espera de repuesto.", dialogo.txt_detalle.toPlainText())

        # Comprobar que NO contiene botones de modificar ni eliminar
        botones = dialogo.findChildren(QPushButton)
        textos_botones = [b.text().strip().lower() for b in botones]
        for texto in textos_botones:
            self.assertNotIn("guardar", texto)
            self.assertNotIn("modificar", texto)
            self.assertNotIn("editar", texto)
            self.assertNotIn("eliminar", texto)
            self.assertNotIn("borrar", texto)

        # Debe tener únicamente botón de Cerrar
        self.assertIn("cerrar", textos_botones)

    def test_06_limpieza_de_sesion(self):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 1,
            "roles": ["Administrador del sistema"],
            "permisos": ["AUDITORIA_CONSULTAR"],
            "acceso_escritorio": True,
        })

        view = AuditoriaView()
        view.input_usuario.setText("admin")
        view.input_activo.setText("ACT-001")
        view.tabla.setRowCount(5)
        view._eventos_cargados = [{"id_auditoria": 1}]
        view._pagina_actual = 3

        view.limpiar_sesion()

        self.assertEqual(view.tabla.rowCount(), 0)
        self.assertEqual(len(view._eventos_cargados), 0)
        self.assertEqual(view.input_usuario.text(), "")
        self.assertEqual(view.input_activo.text(), "")
        self.assertEqual(view._pagina_actual, 1)
        self.assertFalse(view.btn_ver_detalle.isEnabled())

    def test_07_query_id_descarta_respuesta_desactualizada(self):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 1,
            "roles": ["Administrador del sistema"],
            "permisos": ["AUDITORIA_CONSULTAR"],
            "acceso_escritorio": True,
        })

        view = AuditoriaView()
        view._query_id = 1

        # Simular que el usuario hace una segunda búsqueda -> query_id = 2
        view._query_id = 2

        # Llega una respuesta tardía de query_id = 1
        tardia = {
            "count": 1,
            "page": 1,
            "page_size": 25,
            "total_pages": 1,
            "results": [{"id_auditoria": 999, "detalle_evento": "Tardía"}],
        }
        view._on_datos_cargados(tardia, query_id=1, generation=current_session.generation)
        # No debe haber cargado la fila
        self.assertEqual(view.tabla.rowCount(), 0)

        # Llega la respuesta legítima de query_id = 2
        legitima = {
            "count": 1,
            "page": 1,
            "page_size": 25,
            "total_pages": 1,
            "results": [{"id_auditoria": 1000, "detalle_evento": "Legítima"}],
        }
        view._on_datos_cargados(legitima, query_id=2, generation=current_session.generation)
        self.assertEqual(view.tabla.rowCount(), 1)

    def test_08_descarte_de_respuesta_tras_cierre_de_sesion(self):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 1,
            "roles": ["Administrador del sistema"],
            "permisos": ["AUDITORIA_CONSULTAR"],
            "acceso_escritorio": True,
        })

        view = AuditoriaView()
        gen_antigua = current_session.generation

        # Cierre de sesión
        current_session.clear()

        # Respuesta en vuelo que llega después del cierre de sesión
        datos = {
            "count": 1,
            "page": 1,
            "page_size": 25,
            "total_pages": 1,
            "results": [{"id_auditoria": 55, "detalle_evento": "Evento"}],
        }
        view._on_datos_cargados(datos, query_id=view._query_id, generation=gen_antigua)
        self.assertEqual(view.tabla.rowCount(), 0)

    def test_09_navegacion_de_paginas(self):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 1,
            "roles": ["Administrador del sistema"],
            "permisos": ["AUDITORIA_CONSULTAR"],
            "acceso_escritorio": True,
        })

        view = AuditoriaView()
        datos_pag = {
            "count": 50,
            "page": 2,
            "page_size": 25,
            "total_pages": 2,
            "results": [{"id_auditoria": i} for i in range(25)],
        }
        view._on_datos_cargados(datos_pag, query_id=view._query_id, generation=current_session.generation)

        self.assertTrue(view.btn_anterior.isEnabled())
        self.assertFalse(view.btn_siguiente.isEnabled())
        self.assertIn("Página 2 de 2", view.lbl_pagina.text())

    @patch("siget_desktop.ui.views.auditoria_view.ApiWorker")
    def test_10_botones_buscar_y_limpiar(self, mock_worker_cls: MagicMock):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 1,
            "roles": ["Administrador del sistema"],
            "permisos": ["AUDITORIA_CONSULTAR"],
            "acceso_escritorio": True,
        })

        mock_worker_inst = MagicMock()
        mock_worker_cls.return_value = mock_worker_inst

        view = AuditoriaView()
        view.input_usuario.setText("carlos@siget.cl")
        view.input_activo.setText("ACT-005")

        view.btn_buscar.click()
        mock_worker_cls.assert_called_with(
            ANY,
            usuario="carlos@siget.cl",
            activo="ACT-005",
            page=1,
            page_size=25,
        )

        view.btn_limpiar.click()
        self.assertEqual(view.input_usuario.text(), "")
        self.assertEqual(view.input_activo.text(), "")


    def test_permiso_vacio_no_habilita_vista_ni_navegacion(self):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 1, "roles": ["Administrador del sistema"],
            "permisos": [], "acceso_escritorio": True,
        })
        view = AuditoriaView()
        with patch("siget_desktop.ui.views.auditoria_view.ApiWorker") as worker:
            view.cargar_auditoria()
            worker.assert_not_called()
        self.assertTrue(view.contenedor_admin.isHidden())
        win = MainWindow()
        item = win.sidebar.item(6)
        assert item is not None
        self.assertTrue(item.isHidden())
        self.assertEqual(item.flags(), Qt.ItemFlag.NoItemFlags)
        win._cambiar_vista(6)
        self.assertEqual(win.stacked_views.currentIndex(), 0)

    def test_revocar_permiso_limpia_datos_y_descarta_respuesta_en_vuelo(self):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 1, "roles": ["Administrador del sistema"],
            "permisos": ["AUDITORIA_CONSULTAR"], "acceso_escritorio": True,
        })
        view = AuditoriaView()
        payload = {"count": 1, "page": 1, "total_pages": 1,
                   "results": [{"id_auditoria": 99, "detalle_evento": "Privado"}]}
        query = view._query_id
        generation = current_session.generation
        view._on_datos_cargados(payload, query, generation)
        self.assertEqual(view.tabla.rowCount(), 1)
        dialogo = DetalleAuditoriaDialog(payload["results"][0])
        current_session.update_user_info({
            "id_usuario": 1, "roles": ["Administrador del sistema"],
            "permisos": [], "acceso_escritorio": True,
        })
        view._on_datos_cargados(payload, query, generation)
        self.assertTrue(view.contenedor_admin.isHidden())
        self.assertEqual(view.tabla.rowCount(), 0)
        self.assertEqual(view._eventos_cargados, [])
        self.assertFalse(view.btn_ver_detalle.isEnabled())
        with patch.object(dialogo, "reject") as cerrar:
            dialogo._check_session()
            cerrar.assert_called_once()

    def test_fecha_tabla_y_detalle_conservan_instante_y_zona(self):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({
            "id_usuario": 1, "roles": ["Administrador del sistema"],
            "permisos": ["AUDITORIA_CONSULTAR"], "acceso_escritorio": True,
        })
        for fecha in ("2026-10-23T19:40:12+00:00", "2026-10-23T16:40:12-03:00", "2026-10-23T19:40:12Z"):
            with self.subTest(fecha=fecha):
                texto = formatear_fecha_auditoria(fecha)
                interpretada = datetime.fromisoformat(texto)
                self.assertIsNotNone(interpretada.tzinfo)
                self.assertEqual(interpretada.timestamp(), datetime.fromisoformat(fecha).timestamp())
                view = AuditoriaView()
                view.tabla.setRowCount(1)
                view._insertar_fila(0, {"fecha_evento": fecha})
                celda = view.tabla.item(0, 0)
                assert celda is not None
                self.assertEqual(celda.text(), texto)
                dialogo = DetalleAuditoriaDialog({"fecha_evento": fecha})
                self.assertIn(texto, [label.text() for label in dialogo.findChildren(QLabel)])
        self.assertEqual(formatear_fecha_auditoria(None), "—")
        self.assertIn("zona no informada", formatear_fecha_auditoria("2026-10-23T19:40:12"))



    @patch("siget_desktop.ui.views.auditoria_view.ApiWorker")
    @patch("siget_desktop.ui.views.auditoria_view.SelectorAuditoriaDialog")
    def test_selector_envia_id_y_codigo_no_etiquetas(self, selector, worker):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({"id_usuario": 1, "roles": ["Administrador del sistema"],
                                          "permisos": ["AUDITORIA_CONSULTAR"], "acceso_escritorio": True})
        view = AuditoriaView()
        selector.return_value.exec.return_value = 1
        selector.return_value.seleccion = {"id": 7, "etiqueta": "Persona (persona@example.invalid)"}
        view._elegir_filtro("usuario")
        self.assertEqual(worker.call_args.kwargs["id_usuario"], 7)
        self.assertIsNone(worker.call_args.kwargs["usuario"])
        selector.return_value.seleccion = {"codigo": "ACT-123", "etiqueta": "ACT-123 · Modelo · Serie: X"}
        view._elegir_filtro("activo")
        self.assertEqual(worker.call_args.kwargs["activo"], "ACT-123")
        view.input_usuario.setText("otra persona")
        view.cargar_auditoria()
        self.assertNotIn("id_usuario", worker.call_args.kwargs)
        self.assertEqual(worker.call_args.kwargs["usuario"], "otra persona")
        view._limpiar_filtros()
        self.assertIsNone(view._actor_elegido)
        self.assertIsNone(view._activo_elegido)

    @patch("siget_desktop.ui.dialogs.selector_auditoria.ApiWorker")
    def test_dialogo_selector_resultados_vacios_y_eleccion(self, worker):
        current_session.set_tokens("test-token", expires_in=3600)
        current_session.update_user_info({"id_usuario": 1, "roles": ["Administrador del sistema"],
                                          "permisos": ["AUDITORIA_CONSULTAR"], "acceso_escritorio": True})
        dialogo = SelectorAuditoriaDialog("usuario")
        opcion = {"id": 3, "etiqueta": "Persona (persona@example.invalid)"}
        dialogo.mostrar_resultados({"results": [opcion], "has_more": True})
        self.assertIn("20", dialogo.estado.text())
        dialogo.resultados.setCurrentRow(0)
        self.assertTrue(dialogo.btn_elegir.isEnabled())
        dialogo.elegir()
        self.assertEqual(dialogo.seleccion, opcion)
        vacio = SelectorAuditoriaDialog("activo")
        vacio.mostrar_resultados({"results": []})
        self.assertFalse(vacio.btn_elegir.isEnabled())
        self.assertIn("No se encontraron", vacio.estado.text())
        current_session.update_user_info({"id_usuario": 1, "roles": ["Administrador del sistema"],
                                          "permisos": [], "acceso_escritorio": True})
        vacio.mostrar_resultados({"results": [opcion]})
        self.assertEqual(vacio.resultados.count(), 0)


if __name__ == "__main__":
    unittest.main()
