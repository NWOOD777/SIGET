"""
Vista de Gestión y Consulta de Activos TI en PySide6.
Demuestra la comunicación real con el endpoint protegido GET /api/activos/ de Django,
gestiona el alta de nuevos equipos (POST) y la consulta/modificación de detalle (GET/PATCH)
respetando los controles RBAC para Administrador y Técnico.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from siget_desktop.api.qr_services import MAX_ETIQUETAS_LOTE
from siget_desktop.api.services import eliminar_activo, listar_activos
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import configurar_tabla, crear_filtros, mostrar_mensaje, notificar_cambio
from siget_desktop.ui.dialogs.activos_dialogs import (
    AdministrarCatalogosActivosDialog,
    DetalleModificarActivoDialog,
    RegistrarActivoDialog,
)
from siget_desktop.ui.dialogs.common import confirmar_operacion
from siget_desktop.ui.dialogs.qr_dialogs import EtiquetasQRDialog
from siget_desktop.ui.workers import ApiWorker


class ActivosView(QWidget):
    """Módulo de inventario y consulta de activos tecnológicos."""

    COLUMNAS = [
        "ID",
        "Código",
        "N.º de serie",
        "Modelo",
        "Categoría",
        "Ubicación",
        "Estado",
        "Valor",
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker: ApiWorker | None = None
        self._worker_mutacion: ApiWorker | None = None
        self._mutacion_en_curso = False
        self._seleccionar_id: int | None = None
        self._init_ui()
        self.actualizar_permisos_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Encabezado con título y acciones
        layout_encabezado = QHBoxLayout()
        vbox_titulo = QVBoxLayout()
        lbl_titulo = QLabel("Gestión de activos")
        lbl_titulo.setObjectName("tituloPrincipal")
        vbox_titulo.addWidget(lbl_titulo)
        lbl_desc = QLabel("Consulta y administración del parque tecnológico de SIGET")
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        vbox_titulo.addWidget(lbl_desc)
        layout_encabezado.addLayout(vbox_titulo)
        layout_encabezado.addStretch()

        self.btn_ver_detalle = QPushButton("Ver detalle")
        self.btn_ver_detalle.setObjectName("btnSecundario")
        self.btn_ver_detalle.setEnabled(False)
        self.btn_ver_detalle.setToolTip("Seleccione un activo para consultar o modificar su información")
        self.btn_ver_detalle.clicked.connect(self._abrir_detalle_seleccionado)
        layout_encabezado.addWidget(self.btn_ver_detalle)

        self.btn_eliminar = QPushButton("Eliminar activo")
        self.btn_eliminar.setObjectName("btnSecundario")
        self.btn_eliminar.setEnabled(False)
        self.btn_eliminar.setToolTip("Eliminar un registro sin movimientos; los activos en uso conservan su historial")
        self.btn_eliminar.clicked.connect(self._eliminar_seleccionado)
        layout_encabezado.addWidget(self.btn_eliminar)

        self.btn_catalogos = QPushButton("Administrar catálogos")
        self.btn_catalogos.setObjectName("btnSecundario")
        self.btn_catalogos.setEnabled(False)
        self.btn_catalogos.setToolTip("Administrar categorías, marcas, modelos y ubicaciones (exclusivo Administrador)")
        self.btn_catalogos.clicked.connect(self._abrir_catalogos)
        layout_encabezado.addWidget(self.btn_catalogos)

        # Botón administrativo (control RBAC en UI)
        self.btn_nuevo_activo = QPushButton("+ Registrar activo")
        self.btn_nuevo_activo.setEnabled(False)
        self.btn_nuevo_activo.setToolTip("Dar de alta un nuevo equipo (exclusivo Administrador)")
        self.btn_nuevo_activo.clicked.connect(self._abrir_registro_activo)
        layout_encabezado.addWidget(self.btn_nuevo_activo)

        layout.addLayout(layout_encabezado)

        # Barra de filtros
        barra_filtros, layout_filtros = crear_filtros(self)
        layout_filtros.setSpacing(10)

        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Buscar por serie, código o modelo...")
        self.input_search.returnPressed.connect(self.cargar_activos)
        layout_filtros.addWidget(self.input_search, 2)

        self.combo_estado = QComboBox()
        self.combo_estado.addItem("Todos los estados", "")
        self.combo_estado.addItem("Disponible", "Disponible")
        self.combo_estado.addItem("Asignado", "Asignado")
        self.combo_estado.addItem("En revisión", "En revisión")
        self.combo_estado.addItem("En reparación", "En reparación")
        self.combo_estado.addItem("Dado de baja", "Dado de baja")
        self.combo_estado.currentIndexChanged.connect(self.cargar_activos)
        layout_filtros.addWidget(self.combo_estado, 1)

        self.btn_buscar = QPushButton("Actualizar")
        self.btn_buscar.setObjectName("btnSecundario")
        self.btn_buscar.clicked.connect(self.cargar_activos)
        layout_filtros.addWidget(self.btn_buscar)

        layout.addWidget(barra_filtros)

        # Barra de estado y progreso
        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout.addWidget(self.progreso)

        # Mensaje informativo / error / lista vacía
        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        # Botón de reintento para errores
        self.btn_reintentar = QPushButton("Reintentar conexión con el backend")
        self.btn_reintentar.setObjectName("btnSecundario")
        self.btn_reintentar.clicked.connect(self.cargar_activos)
        self.btn_reintentar.hide()
        layout.addWidget(self.btn_reintentar)

        self.acciones_qr = QWidget()
        acciones_qr = QHBoxLayout(self.acciones_qr)
        acciones_qr.setContentsMargins(0, 0, 0, 0)
        self.lbl_seleccion_qr = QLabel("Seleccione un activo o varios con Ctrl/Mayús para preparar sus etiquetas.")
        self.lbl_seleccion_qr.setWordWrap(True)
        acciones_qr.addWidget(self.lbl_seleccion_qr, 1)
        self.btn_generar_qr = QPushButton("Generar Etiqueta QR")
        self.btn_generar_qr.setObjectName("btnSecundario")
        self.btn_generar_qr.clicked.connect(lambda: self._abrir_etiquetas(False))
        acciones_qr.addWidget(self.btn_generar_qr)
        self.btn_imprimir_lote = QPushButton("Imprimir Lote")
        self.btn_imprimir_lote.setObjectName("btnSecundario")
        self.btn_imprimir_lote.clicked.connect(lambda: self._abrir_etiquetas(True))
        acciones_qr.addWidget(self.btn_imprimir_lote)
        layout.addWidget(self.acciones_qr)

        # Tabla de activos
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setAlternatingRowColors(True)
        configurar_tabla(self.tabla, (6,))
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_cambiada)
        self.tabla.cellDoubleClicked.connect(lambda _r, _c: self._abrir_detalle_seleccionado())
        layout.addWidget(self.tabla, 1)

    def actualizar_permisos_ui(self):
        """Ajusta las acciones según los permisos efectivos del usuario."""
        es_admin = current_session.is_admin() and not self._mutacion_en_curso
        self.btn_eliminar.setVisible(current_session.is_admin())
        self.btn_nuevo_activo.setVisible(current_session.is_admin())
        self.btn_catalogos.setVisible(current_session.is_admin())
        self.acciones_qr.setVisible(current_session.is_admin())
        self.tabla.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection if current_session.is_admin() else QTableWidget.SelectionMode.SingleSelection
        )
        self._on_seleccion_cambiada()
        self.btn_nuevo_activo.setEnabled(es_admin)
        self.btn_catalogos.setEnabled(es_admin)
        if es_admin:
            self.btn_nuevo_activo.setToolTip("Dar de alta un nuevo equipo tecnológico en inventario")
            self.btn_catalogos.setToolTip("Administrar categorías, marcas, modelos y ubicaciones de activos TI")
        else:
            self.btn_nuevo_activo.setToolTip("El alta de activos está restringida a Administradores del sistema")
            self.btn_catalogos.setToolTip("La administración de catálogos está restringida a Administradores del sistema")

    def _on_seleccion_cambiada(self):
        cantidad = len(self.tabla.selectionModel().selectedRows())
        hay_seleccion = cantidad == 1
        self.btn_ver_detalle.setEnabled(hay_seleccion and not self._mutacion_en_curso)
        self.btn_eliminar.setEnabled(hay_seleccion and current_session.is_admin() and not self._mutacion_en_curso)
        autorizado = current_session.is_admin() and not self._mutacion_en_curso
        self.btn_generar_qr.setEnabled(hay_seleccion and autorizado)
        self.btn_imprimir_lote.setEnabled(1 <= cantidad <= MAX_ETIQUETAS_LOTE and autorizado)
        self.lbl_seleccion_qr.setText(
            f"{cantidad} seleccionado(s). Máximo {MAX_ETIQUETAS_LOTE} etiquetas por lote."
            if cantidad else "Seleccione un activo o varios con Ctrl/Mayús para preparar sus etiquetas."
        )

    def _obtener_id_activo_seleccionado(self) -> int | None:
        filas = self.tabla.selectionModel().selectedRows()
        if len(filas) != 1:
            return None
        fila = filas[0].row()
        item_id = self.tabla.item(fila, 0)
        if item_id and item_id.text().isdigit():
            return int(item_id.text())
        return None

    def _abrir_etiquetas(self, lote: bool):
        if not current_session.is_admin() or self._mutacion_en_curso:
            return
        filas = sorted(indice.row() for indice in self.tabla.selectionModel().selectedRows())
        seleccion = [(self.tabla.item(fila, 0), self.tabla.item(fila, 1)) for fila in filas]
        if any(item is None or codigo is None for item, codigo in seleccion):
            return
        ids = [int(item.text()) for item, _ in seleccion if item is not None]
        if not 1 <= len(ids) <= MAX_ETIQUETAS_LOTE or (not lote and len(ids) != 1):
            return
        codigos = ", ".join(codigo.text() for _, codigo in seleccion if codigo is not None)
        if not confirmar_operacion(self, "Generar etiquetas QR", f"Activos: {codigos}\nSe solicitarán sus etiquetas y se conservará el identificador de cada equipo."):
            return
        dialogo = EtiquetasQRDialog(ids, self)
        dialogo.exec()
        if dialogo.etiquetas:
            notificar_cambio(self)

    def _abrir_catalogos(self):
        if not current_session.is_admin():
            return
        dialogo = AdministrarCatalogosActivosDialog(self)
        dialogo.exec()
        if dialogo.hubo_cambios:
            notificar_cambio(self)
            self.cargar_activos()

    def _abrir_registro_activo(self):
        dialogo = RegistrarActivoDialog(self)
        if dialogo.exec() == RegistrarActivoDialog.DialogCode.Accepted:
            self._seleccionar_id = getattr(dialogo, "activo_registrado", {}).get("id_activo")
            self.input_search.clear()
            self.combo_estado.setCurrentIndex(0)
            notificar_cambio(self)
            self.cargar_activos()

    def _abrir_detalle_seleccionado(self):
        id_activo = self._obtener_id_activo_seleccionado()
        if not id_activo:
            return
        dialogo = DetalleModificarActivoDialog(id_activo, self)
        if dialogo.exec() == DetalleModificarActivoDialog.DialogCode.Accepted:
            notificar_cambio(self)
            self.cargar_activos()

    def limpiar_sesion(self):
        self._worker = None
        self._worker_mutacion = None
        self._mutacion_en_curso = False
        self.tabla.setEnabled(True)
        self.tabla.setRowCount(0)
        self._seleccionar_id = None
        self.progreso.hide()
        self.lbl_mensaje.hide()
        self.actualizar_permisos_ui()

    def _eliminar_seleccionado(self):
        pk = self._obtener_id_activo_seleccionado()
        if not pk or not current_session.is_admin() or self._mutacion_en_curso:
            return
        codigo = self.tabla.item(self.tabla.selectionModel().selectedRows()[0].row(), 1)
        if not confirmar_operacion(
            self, "Eliminar activo",
            f"Activo: {codigo.text() if codigo else pk}\n"
            "Se eliminará permanentemente el registro si no tiene movimientos ni información asociada.",
        ):
            return
        self._mutacion_en_curso = True
        self.tabla.setEnabled(False)
        self.btn_buscar.setEnabled(False)
        self.actualizar_permisos_ui()
        self.progreso.show()
        self._worker_mutacion = ApiWorker(eliminar_activo, id_activo=pk)
        generation = current_session.generation
        worker = self._worker_mutacion
        worker.signals.finished.connect(lambda value: self._terminar_eliminacion(None, generation) if worker is self._worker_mutacion else None)
        worker.signals.error.connect(lambda exc: self._terminar_eliminacion(exc, generation) if worker is self._worker_mutacion else None)
        worker.start()

    def _terminar_eliminacion(self, error: Exception | None, generation: int):
        if not isValid(self) or not current_session.is_authenticated() or generation != current_session.generation:
            return
        self._mutacion_en_curso = False
        self._worker_mutacion = None
        self.tabla.setEnabled(True)
        self.btn_buscar.setEnabled(True)
        self.progreso.hide()
        self.actualizar_permisos_ui()
        if error is not None:
            mostrar_mensaje(self.lbl_mensaje, str(error), "error")
            return
        notificar_cambio(self)
        self.cargar_activos()

    def cargar_activos(self):
        """Inicia la consulta al backend de forma asíncrona para no congelar la UI."""
        if self._mutacion_en_curso:
            return
        self.actualizar_permisos_ui()
        self.progreso.show()
        self.lbl_mensaje.hide()
        self.btn_reintentar.hide()
        self.btn_buscar.setEnabled(False)
        self.btn_ver_detalle.setEnabled(False)
        self.btn_generar_qr.setEnabled(False)
        self.btn_imprimir_lote.setEnabled(False)

        search_text = self.input_search.text().strip() or None
        estado_sel = self.combo_estado.currentData() or None

        self._worker = ApiWorker(listar_activos, search=search_text, estado=estado_sel)
        self._worker.signals.finished.connect(lambda value, generation=current_session.generation, worker=self._worker: self._on_datos_cargados(value, generation) if worker is self._worker else None)
        self._worker.signals.error.connect(lambda value, generation=current_session.generation, worker=self._worker: self._on_error_carga(value, generation) if worker is self._worker else None)
        self._worker.start()

    def _on_datos_cargados(self, activos: list[dict[str, Any]], request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        if self._mutacion_en_curso:
            return
        self.progreso.hide()
        self.btn_buscar.setEnabled(True)
        self.tabla.setRowCount(0)

        if not activos:
            mostrar_mensaje(self.lbl_mensaje, "No se encontraron activos registrados con los filtros aplicados.", "empty")
            return

        mostrar_mensaje(self.lbl_mensaje, f"Mostrando {len(activos)} activos obtenidos del servidor.", "info")

        self.tabla.setRowCount(len(activos))
        for row_idx, activo in enumerate(activos):
            self._insertar_fila(row_idx, activo)
        if self._seleccionar_id is not None:
            for fila, activo in enumerate(activos):
                if activo.get("id_activo") == self._seleccionar_id:
                    self.tabla.selectRow(fila)
                    item = self.tabla.item(fila, 0)
                    if item is not None:
                        self.tabla.scrollToItem(item)
                    break
            self._seleccionar_id = None
        self._on_seleccion_cambiada()

    def _insertar_fila(self, row: int, item: dict[str, Any]):
        valores = [
            str(item.get("id_activo", "")),
            str(item.get("codigo_inventario", "")),
            str(item.get("numero_serie", "")),
            str(item.get("modelo", "—")),
            str(item.get("categoria", "—")),
            str(item.get("ubicacion", "—")),
            str(item.get("estado", "—")),
            f"${float(item.get('valor_adquisicion', 0)):,.0f}".replace(",", "."),
        ]
        for col, val in enumerate(valores):
            table_item = QTableWidgetItem(val)
            table_item.setToolTip(val)
            table_item.setFlags(table_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.tabla.setItem(row, col, table_item)

    def _on_error_carga(self, exc: Exception, request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        if self._mutacion_en_curso:
            return
        self.progreso.hide()
        self.btn_buscar.setEnabled(True)
        self.tabla.setRowCount(0)

        mostrar_mensaje(self.lbl_mensaje, f"Error al comunicar con el backend: {exc}", "error")
        self.btn_reintentar.show()
