"""
Vista de Gestión y Consulta de Activos TI en PySide6.
Demuestra la comunicación real con el endpoint protegido GET /api/activos/ de Django,
gestionando estados de carga, listas vacías, errores de red y filtros de búsqueda.
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

from siget_desktop.api.services import listar_activos
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import configurar_tabla, crear_filtros, mostrar_mensaje
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
        self._init_ui()

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

        # Botón administrativo (control RBAC en UI)
        self.btn_nuevo_activo = QPushButton("+ Registrar activo")
        self.btn_nuevo_activo.setEnabled(False)
        self.btn_nuevo_activo.setToolTip("Funcionalidad pendiente de una próxima entrega")
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
        self.combo_estado.addItem("Baja", "Baja")
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

        # Tabla de activos
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setAlternatingRowColors(True)
        configurar_tabla(self.tabla, (6,))
        layout.addWidget(self.tabla, 1)

    def actualizar_permisos_ui(self):
        """Ajusta las acciones según los permisos efectivos del usuario."""
        self.btn_nuevo_activo.setEnabled(False)
        self.btn_nuevo_activo.setToolTip("Funcionalidad pendiente de una próxima entrega")

    def cargar_activos(self):
        """Inicia la consulta al backend de forma asíncrona para no congelar la UI."""
        self.actualizar_permisos_ui()
        self.progreso.show()
        self.lbl_mensaje.hide()
        self.btn_reintentar.hide()
        self.btn_buscar.setEnabled(False)

        search_text = self.input_search.text().strip() or None
        estado_sel = self.combo_estado.currentData() or None

        self._worker = ApiWorker(listar_activos, search=search_text, estado=estado_sel)
        self._worker.signals.finished.connect(lambda value, generation=current_session.generation: self._on_datos_cargados(value, generation))
        self._worker.signals.error.connect(lambda value, generation=current_session.generation: self._on_error_carga(value, generation))
        self._worker.start()

    def _on_datos_cargados(self, activos: list[dict[str, Any]], request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
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
        self.progreso.hide()
        self.btn_buscar.setEnabled(True)
        self.tabla.setRowCount(0)

        mostrar_mensaje(self.lbl_mensaje, f"Error al comunicar con el backend: {exc}", "error")
        self.btn_reintentar.show()
