"""
Vista de Gestión de Solicitudes y Asignaciones en PySide6.
Aplica controles RBAC diferenciando las acciones de aprobación (Administrador)
y entrega/devolución (Técnico).
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

from siget_desktop.api.services import listar_solicitudes
from siget_desktop.auth.session import current_session
from siget_desktop.ui.components import configurar_tabla, crear_filtros, mostrar_mensaje, texto_relacion
from siget_desktop.ui.workers import ApiWorker


class SolicitudesView(QWidget):
    """Módulo de Solicitudes de asignación y Operaciones de Entrega."""

    COLUMNAS = [
        "ID",
        "Solicitante",
        "Categoría",
        "Estado",
        "Resolutor",
        "Fecha",
        "Motivo",
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker: ApiWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Encabezado
        layout_encabezado = QHBoxLayout()
        vbox_titulo = QVBoxLayout()
        lbl_titulo = QLabel("Solicitudes de asignación")
        lbl_titulo.setObjectName("tituloPrincipal")
        vbox_titulo.addWidget(lbl_titulo)
        lbl_desc = QLabel("Aprobación administrativa y formalización de entregas de equipamiento")
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        vbox_titulo.addWidget(lbl_desc)
        layout_encabezado.addLayout(vbox_titulo)
        layout_encabezado.addStretch()

        # Botones de acción según RBAC
        self.btn_aprobar = QPushButton("Aprobar Solicitud")
        self.btn_aprobar.setToolTip("Aprobar solicitud seleccionada (solo Administrador)")
        self.btn_aprobar.setEnabled(False)
        self.btn_aprobar.setToolTip("Funcionalidad pendiente de una próxima entrega")
        layout_encabezado.addWidget(self.btn_aprobar)

        self.btn_rechazar = QPushButton("Rechazar")
        self.btn_rechazar.setObjectName("btnPeligro")
        self.btn_rechazar.setToolTip("Rechazar solicitud seleccionada (solo Administrador)")
        self.btn_rechazar.setEnabled(False)
        self.btn_rechazar.setToolTip("Funcionalidad pendiente de una próxima entrega")
        layout_encabezado.addWidget(self.btn_rechazar)

        self.btn_entregar = QPushButton("Registrar Entrega")
        self.btn_entregar.setObjectName("btnSecundario")
        self.btn_entregar.setToolTip("Formalizar entrega de activo (solo Técnico)")
        self.btn_entregar.setEnabled(False)
        self.btn_entregar.setToolTip("Funcionalidad pendiente de una próxima entrega")
        layout_encabezado.addWidget(self.btn_entregar)

        layout.addLayout(layout_encabezado)

        # Filtros
        barra_filtros, layout_filtros = crear_filtros(self)
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Buscar por solicitante, motivo o identificador...")
        self.input_search.returnPressed.connect(self.cargar_solicitudes)
        layout_filtros.addWidget(self.input_search, 2)

        self.combo_estado = QComboBox()
        self.combo_estado.addItem("Todas", "")
        self.combo_estado.addItem("Pendiente", "Pendiente")
        self.combo_estado.addItem("Aprobada", "Aprobada")
        self.combo_estado.addItem("Rechazada", "Rechazada")
        self.combo_estado.addItem("Atendida", "Atendida")
        self.combo_estado.currentIndexChanged.connect(self.cargar_solicitudes)
        layout_filtros.addWidget(self.combo_estado, 1)

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.clicked.connect(self.cargar_solicitudes)
        layout_filtros.addWidget(self.btn_actualizar)

        layout.addWidget(barra_filtros)

        # Progreso y mensajes
        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        self.btn_reintentar = QPushButton("Reintentar conexión con el servidor")
        self.btn_reintentar.setObjectName("btnSecundario")
        self.btn_reintentar.clicked.connect(self.cargar_solicitudes)
        self.btn_reintentar.hide()
        layout.addWidget(self.btn_reintentar)

        # Tabla
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setAlternatingRowColors(True)
        configurar_tabla(self.tabla, (3,))
        layout.addWidget(self.tabla, 1)

    def actualizar_permisos_ui(self):
        self.btn_aprobar.setEnabled(False)
        self.btn_aprobar.setToolTip("Funcionalidad pendiente de una próxima entrega")
        self.btn_rechazar.setEnabled(False)
        self.btn_rechazar.setToolTip("Funcionalidad pendiente de una próxima entrega")
        self.btn_entregar.setEnabled(False)
        self.btn_entregar.setToolTip("Funcionalidad pendiente de una próxima entrega")

    def cargar_solicitudes(self):
        self.actualizar_permisos_ui()
        self.progreso.show()
        self.lbl_mensaje.hide()
        self.btn_reintentar.hide()
        self.btn_actualizar.setEnabled(False)

        search_text = self.input_search.text().strip() or None
        estado_sel = self.combo_estado.currentData() or None

        self._worker = ApiWorker(listar_solicitudes, search=search_text, estado=estado_sel)
        self._worker.signals.finished.connect(lambda value, generation=current_session.generation: self._on_datos_cargados(value, generation))
        self._worker.signals.error.connect(lambda value, generation=current_session.generation: self._on_error(value, generation))
        self._worker.start()

    def _on_datos_cargados(self, solicitudes: list[dict[str, Any]], request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)

        if not solicitudes:
            mostrar_mensaje(self.lbl_mensaje, "No hay solicitudes de asignación registradas con los filtros seleccionados.", "empty")
            return

        mostrar_mensaje(self.lbl_mensaje, f"Mostrando {len(solicitudes)} solicitudes.", "info")

        self.tabla.setRowCount(len(solicitudes))
        for row_idx, item in enumerate(solicitudes):
            valores = [
                str(item.get("id_solicitud", "")),
                texto_relacion(item.get("solicitante")),
                texto_relacion(item.get("categoria")),
                texto_relacion(item.get("estado")),
                texto_relacion(item.get("resolutor")),
                str(item.get("fecha_solicitud", "")[:10] if item.get("fecha_solicitud") else "—"),
                str(item.get("motivo", "")),
            ]
            for col_idx, val in enumerate(valores):
                cell = QTableWidgetItem(val)
                cell.setToolTip(val)
                cell.setFlags(cell.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.tabla.setItem(row_idx, col_idx, cell)

    def _on_error(self, exc: Exception, request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)
        mostrar_mensaje(self.lbl_mensaje, f"Error al obtener solicitudes del backend: {exc}", "error")
        self.btn_reintentar.show()
