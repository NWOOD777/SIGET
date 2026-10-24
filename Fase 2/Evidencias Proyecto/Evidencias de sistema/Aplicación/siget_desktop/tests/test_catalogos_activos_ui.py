"""
Pruebas de interfaz PySide6 (offscreen) para el mantenedor de catálogos de Activos TI
y la actualización de selectores / arranque con catálogos vacíos.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QMessageBox

from siget_desktop.api import services
from siget_desktop.api.client import ValidationApiError
from siget_desktop.auth.session import current_session
from siget_desktop.tests.qt_helpers import limpiar_widgets
from siget_desktop.ui.dialogs.activos_dialogs import (
    AdministrarCatalogosActivosDialog,
    DetalleModificarActivoDialog,
    RegistrarActivoDialog,
)
from siget_desktop.ui.views.activos_view import ActivosView

APP = QApplication.instance() or QApplication([])


class CatalogosActivosDesktopTests(unittest.TestCase):
    """Pruebas unitarias e integradas de UI para catálogos maestros de Activos TI."""

    def setUp(self):
        confirmacion = patch("siget_desktop.ui.dialogs.common.QMessageBox.exec", return_value=QMessageBox.StandardButton.Yes)
        confirmacion.start()
        self.addCleanup(confirmacion.stop)
        current_session.clear()
        current_session.set_tokens("token_admin_test", 3600)
        current_session.update_user_info(
            {
                "id_usuario": 1,
                "nombres": "Admin",
                "apellidos": "SIGET",
                "roles": ["Administrador del sistema"],
                "permisos_efectivos": ["CATALOGO_CONSULTAR"],
                "acceso_escritorio": True,
            }
        )
        self.widgets = []
        self._patcher_worker = patch("siget_desktop.ui.dialogs.activos_dialogs.ApiWorker")
        self.mock_worker = self._patcher_worker.start()
        self.addCleanup(self._patcher_worker.stop)

    def tearDown(self):
        for w in self.widgets:
            w.deleteLater()
        current_session.clear()
        limpiar_widgets()

    def keep(self, widget):
        self.widgets.append(widget)
        return widget

    def test_servicios_catalogos_crud_y_busqueda(self):
        with (
            patch.object(services.api_client, "get") as mock_get,
            patch.object(services.api_client, "post") as mock_post,
            patch.object(services.api_client, "patch") as mock_patch,
            patch.object(services.api_client, "delete") as mock_delete,
        ):
            mock_get.return_value = [{"id_categoria": 1, "nombre": "Notebook"}]
            res = services.listar_categorias_activos(search="  Note ")
            mock_get.assert_called_with("/api/activos/categorias/", params={"search": "Note"})
            self.assertEqual(len(res), 1)

            mock_post.return_value = {"id_marca": 2, "nombre": "Dell"}
            creada = services.crear_marca_activo({"nombre": "Dell"})
            self.assertEqual(creada["id_marca"], 2)

            mock_patch.return_value = {"id_modelo": 3, "nombre": "Latitude 5520"}
            actualizado = services.actualizar_modelo_activo(3, {"nombre": "Latitude 5520"})
            self.assertEqual(actualizado["nombre"], "Latitude 5520")

            mock_delete.return_value = {}
            eliminado = services.eliminar_ubicacion_activo(4)
            self.assertEqual(eliminado, {})

    def test_rbac_boton_administrar_catalogos_en_activos_view(self):
        view = self.keep(ActivosView())
        view.actualizar_permisos_ui()
        self.assertTrue(view.btn_catalogos.isEnabled())
        self.assertTrue(view.btn_nuevo_activo.isEnabled())

        # Cambiar a Técnico de soporte: no puede administrar catálogos ni registrar activos
        current_session.update_user_info(
            {
                "id_usuario": 2,
                "roles": ["Técnico de soporte"],
                "permisos_efectivos": ["CATALOGO_CONSULTAR"],
                "acceso_escritorio": True,
            }
        )
        view.actualizar_permisos_ui()
        self.assertFalse(view.btn_catalogos.isEnabled())
        self.assertFalse(view.btn_nuevo_activo.isEnabled())

    def test_mantenedor_carga_vacia_poblar_seleccion_crear_editar_y_confirmar_eliminacion(self):
        dialog = self.keep(AdministrarCatalogosActivosDialog())

        # 1. Estado con catálogos vacíos
        dialog._on_todos_cargados(
            {
                "categorias": [],
                "marcas": [],
                "ubicaciones": [],
                "modelos": [],
                "todas_categorias": [],
                "todas_marcas": [],
            }
        )
        self.assertFalse(dialog.lbl_vacio_categorias.isHidden())
        self.assertFalse(dialog.lbl_vacio_marcas.isHidden())
        self.assertFalse(dialog.lbl_vacio_ubicaciones.isHidden())
        self.assertFalse(dialog.lbl_vacio_modelos.isHidden())
        self.assertFalse(dialog.btn_modelo_guardar.isEnabled())

        # 2. Poblar con datos de los cuatro catálogos
        dialog._on_todos_cargados(
            {
                "categorias": [{"id_categoria": 10, "nombre": "Notebook", "descripcion": "Portátil"}],
                "marcas": [{"id_marca": 20, "nombre": "Lenovo"}],
                "ubicaciones": [
                    {
                        "id_ubicacion": 30,
                        "nombre_area": "Departamento TI",
                        "edificio": "Edificio Central",
                        "piso": "Piso 2",
                    }
                ],
                "modelos": [
                    {
                        "id_modelo": 40,
                        "nombre": "ThinkPad T14",
                        "id_marca": 20,
                        "marca": "Lenovo",
                        "id_categoria": 10,
                        "categoria": "Notebook",
                    }
                ],
                "todas_categorias": [{"id_categoria": 10, "nombre": "Notebook"}],
                "todas_marcas": [{"id_marca": 20, "nombre": "Lenovo"}],
            }
        )
        self.assertTrue(dialog.lbl_vacio_categorias.isHidden())
        self.assertEqual(dialog.tabla_categorias.rowCount(), 1)
        self.assertEqual(dialog.tabla_marcas.rowCount(), 1)
        self.assertEqual(dialog.tabla_ubicaciones.rowCount(), 1)
        self.assertEqual(dialog.tabla_modelos.rowCount(), 1)
        self.assertTrue(dialog.btn_modelo_guardar.isEnabled())

        # Verificar selectores legibles de marca y categoría en modelos (sin escribir IDs)
        self.assertEqual(dialog.combo_modelo_marca.currentText(), "Lenovo")
        self.assertEqual(dialog.combo_modelo_marca.currentData(), 20)
        self.assertEqual(dialog.combo_modelo_categoria.currentText(), "Notebook")
        self.assertEqual(dialog.combo_modelo_categoria.currentData(), 10)

        # 3. Seleccionar fila en tabla de modelos carga formulario para edición
        dialog.tabla_modelos.selectRow(0)
        self.assertEqual(dialog._id_modelo_editando, 40)
        self.assertEqual(dialog.input_modelo_nombre.text(), "ThinkPad T14")
        self.assertEqual(dialog.btn_modelo_guardar.text(), "Guardar cambios")
        self.assertTrue(dialog.btn_modelo_eliminar.isEnabled())

        # Editar modelo dispara actualizar_modelo_activo
        self.mock_worker.reset_mock()
        dialog.input_modelo_nombre.setText("ThinkPad T14 Gen 4")
        dialog._guardar_modelo()
        self.mock_worker.assert_called_once_with(
            services.actualizar_modelo_activo,
            id_modelo=40,
            datos={"nombre": "ThinkPad T14 Gen 4", "id_marca": 20, "id_categoria": 10},
            parcial=True,
        )

        # 4. Confirmación explícita antes de eliminar: No -> no elimina, Yes -> elimina
        self.mock_worker.reset_mock()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            dialog._confirmar_eliminar_modelo()
            self.mock_worker.assert_not_called()

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog._confirmar_eliminar_modelo()
            self.mock_worker.assert_called_once_with(
                services.eliminar_modelo_activo,
                id_modelo=40,
            )

        # 5. Conflicto 409 de referencias o error por campo se muestra claramente
        err = ValidationApiError(
            "No se puede eliminar el modelo 'ThinkPad T14' porque está asociado a 2 activo(s).",
            status_code=409,
        )
        dialog._on_error(err)
        self.assertFalse(dialog.lbl_mensaje.isHidden())
        self.assertIn("asociado a 2 activo(s)", dialog.lbl_mensaje.text())

    def test_carga_captura_filtros_antes_de_ejecutar_el_worker(self):
        dialog = self.keep(AdministrarCatalogosActivosDialog())
        dialog.input_buscar_categoria.setText("Monitor")
        dialog.input_buscar_marca.setText("Marca A")
        dialog.input_buscar_ubicacion.setText("Bodega")
        dialog.input_buscar_modelo.setText("Modelo A")
        dialog.cargar_todos_los_catalogos()
        cargar = self.mock_worker.call_args.args[0]
        # El hilo debe recibir valores capturados en la interfaz, sin leer widgets.
        dialog.input_buscar_categoria.setText("Otra categoría")
        with (
            patch("siget_desktop.ui.dialogs.activos_dialogs.listar_categorias_activos", return_value=[]) as categorias,
            patch("siget_desktop.ui.dialogs.activos_dialogs.listar_marcas_activos", return_value=[]) as marcas,
            patch("siget_desktop.ui.dialogs.activos_dialogs.listar_ubicaciones_activos", return_value=[]) as ubicaciones,
            patch("siget_desktop.ui.dialogs.activos_dialogs.listar_modelos_activos", return_value=[]) as modelos,
        ):
            cargar()
        self.assertEqual(categorias.call_args_list[0].args, ("Monitor",))
        self.assertEqual(marcas.call_args_list[0].args, ("Marca A",))
        ubicaciones.assert_called_once_with("Bodega")
        modelos.assert_called_once_with("Modelo A")

    def test_operacion_pendiente_bloquea_interaccion_y_error_la_rehabilita(self):
        dialog = self.keep(AdministrarCatalogosActivosDialog())
        dialog._on_todos_cargados({})
        dialog.input_marca_nombre.setText("Marca de prueba")
        dialog._guardar_marca()
        self.assertFalse(dialog.tabs.isEnabled())
        self.assertFalse(dialog.btn_refrescar.isEnabled())
        dialog._on_error(ValidationApiError("Nombre duplicado", status_code=400))
        self.assertTrue(dialog.tabs.isEnabled())
        self.assertTrue(dialog.btn_refrescar.isEnabled())
        self.assertEqual(dialog.input_marca_nombre.text(), "Marca de prueba")

    def test_registrar_activo_arranque_vacio_y_recuperacion_tras_cargar_catalogos(self):
        dialog = self.keep(RegistrarActivoDialog())

        # Instalación limpia con catálogos vacíos
        dialog._on_catalogos({"modelos": [], "ubicaciones": []})
        self.assertFalse(dialog.btn_guardar.isEnabled())
        self.assertFalse(dialog.lbl_mensaje.isHidden())
        self.assertIn("Faltan modelos y ubicaciones", dialog.lbl_mensaje.text())

        # El usuario ingresa serie y valor mientras crea los catálogos desde el mantenedor
        dialog.input_serie.setText("SN-PRIMER-ACTIVO-001")
        dialog.input_valor.setText("950000")

        # Al volver del mantenedor / refrescar catálogos se habilita el guardado sin perder campos
        dialog._on_catalogos(
            {
                "modelos": [
                    {
                        "id_modelo": 5,
                        "nombre": "Latitude 5520",
                        "marca": "Dell",
                        "categoria": "Notebook",
                    }
                ],
                "ubicaciones": [
                    {
                        "id_ubicacion": 7,
                        "nombre_area": "Departamento TI",
                        "edificio": "Edificio Central",
                        "piso": "Piso 2",
                    }
                ],
            }
        )
        self.assertTrue(dialog.btn_guardar.isEnabled())
        self.assertTrue(dialog.lbl_mensaje.isHidden())
        self.assertEqual(dialog.input_serie.text(), "SN-PRIMER-ACTIVO-001")
        self.assertEqual(dialog.input_valor.text(), "950.000")
        self.assertEqual(dialog.combo_modelo.currentData(), 5)
        self.assertEqual(dialog.combo_ubicacion.currentData(), 7)
        self.assertIn("Edif. Edificio Central, Piso Piso 2", dialog.combo_ubicacion.currentText())

    def test_refresco_selectores_conserva_id_actualiza_etiqueta_retira_eliminados_y_descarta_tardias(self):
        # 1. RegistrarActivoDialog
        reg = self.keep(RegistrarActivoDialog())
        reg._on_catalogos(
            {
                "modelos": [
                    {"id_modelo": 1, "nombre": "Modelo A", "marca": "Dell", "categoria": "Notebook"},
                    {"id_modelo": 2, "nombre": "Modelo B", "marca": "HP", "categoria": "Notebook"},
                ],
                "ubicaciones": [
                    {"id_ubicacion": 10, "nombre_area": "Bodega 1", "edificio": "A", "piso": "1"},
                    {"id_ubicacion": 20, "nombre_area": "Bodega 2", "edificio": "B", "piso": "2"},
                ],
            }
        )
        reg.combo_modelo.setCurrentIndex(reg.combo_modelo.findData(2))
        reg.combo_ubicacion.setCurrentIndex(reg.combo_ubicacion.findData(20))
        reg.input_serie.setText("SN-KEEP-99")
        reg.input_valor.setText("500000")

        # Simular refresco: Modelo 1 fue eliminado, Modelo 2 fue renombrado a "Modelo B Pro", Ubicación 20 renombrada
        req_actual = reg._catalogos_req_id
        reg._on_catalogos(
            {
                "modelos": [
                    {"id_modelo": 2, "nombre": "Modelo B Pro", "marca": "HP", "categoria": "Notebook"},
                ],
                "ubicaciones": [
                    {"id_ubicacion": 20, "nombre_area": "Bodega Principal", "edificio": "B", "piso": "2"},
                ],
            },
            req_id=req_actual,
        )
        self.assertEqual(reg.combo_modelo.count(), 1)
        self.assertEqual(reg.combo_modelo.currentData(), 2)
        self.assertIn("Modelo B Pro", reg.combo_modelo.currentText())
        self.assertEqual(reg.combo_ubicacion.currentData(), 20)
        self.assertIn("Bodega Principal", reg.combo_ubicacion.currentText())
        self.assertEqual(reg.input_serie.text(), "SN-KEEP-99")
        self.assertEqual(reg.input_valor.text(), "500.000")

        # Respuesta tardía con req_id obsoleto es descartada
        reg._on_catalogos(
            {
                "modelos": [{"id_modelo": 99, "nombre": "Obsoleto", "marca": "Vieja", "categoria": "X"}],
                "ubicaciones": [],
            },
            req_id=req_actual - 1,
        )
        self.assertEqual(reg.combo_modelo.currentData(), 2)
        self.assertIn("Modelo B Pro", reg.combo_modelo.currentText())

        # 2. DetalleModificarActivoDialog
        det = self.keep(DetalleModificarActivoDialog(id_activo=8))
        det._on_datos_cargados(
            {
                "activo": {
                    "id_activo": 8,
                    "codigo_inventario": "ACT-000008",
                    "numero_serie": "SN-DET-8",
                    "id_modelo": 2,
                    "modelo": "Modelo B",
                    "marca": "HP",
                    "categoria": "Notebook",
                    "id_ubicacion": 20,
                    "id_estado_activo": 1,
                    "estado": "Disponible",
                    "valor_adquisicion": "720000.00",
                },
                "modelos": [
                    {"id_modelo": 1, "nombre": "Modelo A", "marca": "Dell", "categoria": "Notebook"},
                    {"id_modelo": 2, "nombre": "Modelo B", "marca": "HP", "categoria": "Notebook"},
                ],
                "ubicaciones": [
                    {"id_ubicacion": 20, "nombre_area": "Bodega 2", "edificio": "B", "piso": "2"},
                ],
                "estados": [{"id_estado_activo": 1, "nombre": "Disponible"}],
            }
        )
        det.input_serie.setText("SN-DET-8-MOD")
        det._on_catalogos_recargados(
            {
                "modelos": [
                    {"id_modelo": 2, "nombre": "Modelo B Renovado", "marca": "HP", "categoria": "Notebook"},
                ],
                "ubicaciones": [
                    {"id_ubicacion": 20, "nombre_area": "Bodega Centralizada", "edificio": "B", "piso": "2"},
                ],
            },
            req_id=det._catalogos_req_id,
        )
        self.assertEqual(det.input_serie.text(), "SN-DET-8-MOD")
        self.assertEqual(det.combo_modelo.currentData(), 2)
        self.assertIn("Modelo B Renovado", det.combo_modelo.currentText())
        self.assertIn("Modelo B Renovado", det.lbl_modelo.text())
        self.assertIn("Bodega Centralizada", det.combo_ubicacion.currentText())
