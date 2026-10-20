"""
Vista de Mesa de Ayuda / Tickets de Soporte en PySide6.
Permite consultar incidentes y solicitudes de soporte técnico.
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

from siget_desktop.api.services import listar_tickets
from siget_desktop.auth.session import current_session
from siget_desktop.ui.workers import ApiWorker


class TicketsView(QWidget):
    """Módulo de Service Desk y Tickets de Soporte Técnico."""

    COLUMNAS = [
        "Código",
        "Asunto",
        "Solicitante",
        "Estado",
        "Prioridad",
        "Técnico Asignado",
        "Fecha Creación",
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
        lbl_titulo = QLabel("Mesa de Ayuda - Tickets")
        lbl_titulo.setObjectName("tituloPrincipal")
        vbox_titulo.addWidget(lbl_titulo)
        lbl_desc = QLabel("Gestión de incidentes, solicitudes de soporte y atención técnica")
        lbl_desc.setObjectName("subtitulo")
        vbox_titulo.addWidget(lbl_desc)
        layout_encabezado.addLayout(vbox_titulo)
        layout_encabezado.addStretch()

        self.btn_atender = QPushButton("Atender Ticket")
        self.btn_atender.setEnabled(False)
        self.btn_atender.setToolTip("Funcionalidad pendiente de una próxima entrega")
        self.btn_atender.setToolTip("Iniciar atención u orden de trabajo técnica (solo Técnico de soporte)")
        layout_encabezado.addWidget(self.btn_atender)

        layout.addLayout(layout_encabezado)

        # Filtros
        layout_filtros = QHBoxLayout()
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Buscar por código, asunto o descripción...")
        self.input_search.returnPressed.connect(self.cargar_tickets)
        layout_filtros.addWidget(self.input_search, 2)

        self.combo_estado = QComboBox()
        self.combo_estado.addItem("Todos los estados", "")
        self.combo_estado.addItem("Abierto", "Abierto")
        self.combo_estado.addItem("En Atención", "En Atención")
        self.combo_estado.addItem("Resuelto", "Resuelto")
        self.combo_estado.addItem("Cerrado", "Cerrado")
        self.combo_estado.currentIndexChanged.connect(self.cargar_tickets)
        layout_filtros.addWidget(self.combo_estado, 1)

        self.combo_prioridad = QComboBox()
        self.combo_prioridad.addItem("Todas las prioridades", "")
        self.combo_prioridad.addItem("Baja", "Baja")
        self.combo_prioridad.addItem("Media", "Media")
        self.combo_prioridad.addItem("Alta", "Alta")
        self.combo_prioridad.addItem("Crítica", "Crítica")
        self.combo_prioridad.currentIndexChanged.connect(self.cargar_tickets)
        layout_filtros.addWidget(self.combo_prioridad, 1)

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.clicked.connect(self.cargar_tickets)
        layout_filtros.addWidget(self.btn_actualizar)

        layout.addLayout(layout_filtros)

        # Progreso y mensajes
        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.setStyleSheet("padding: 8px 12px; border-radius: 6px; font-weight: 500;")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        self.btn_reintentar = QPushButton("Reintentar conexión")
        self.btn_reintentar.setObjectName("btnSecundario")
        self.btn_reintentar.clicked.connect(self.cargar_tickets)
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
        self.tabla.setStyleSheet("QTableWidget { alternate-background-color: #162032; }")
        layout.addWidget(self.tabla, 1)

    def actualizar_permisos_ui(self):
        self.btn_atender.setEnabled(False)
        self.btn_atender.setToolTip("Funcionalidad pendiente de una próxima entrega")

    def cargar_tickets(self):
        self.actualizar_permisos_ui()
        self.progreso.show()
        self.lbl_mensaje.hide()
        self.btn_reintentar.hide()
        self.btn_actualizar.setEnabled(False)

        search_text = self.input_search.text().strip() or None
        estado_sel = self.combo_estado.currentData() or None
        prio_sel = self.combo_prioridad.currentData() or None

        self._worker = ApiWorker(listar_tickets, search=search_text, estado=estado_sel, prioridad=prio_sel)
        self._worker.signals.finished.connect(lambda value, generation=current_session.generation: self._on_datos_cargados(value, generation))
        self._worker.signals.error.connect(lambda value, generation=current_session.generation: self._on_error(value, generation))
        self._worker.start()

    def _on_datos_cargados(self, tickets: list[dict[str, Any]], request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)

        if not tickets:
            self.lbl_mensaje.setText("No hay tickets de soporte registrados con los filtros seleccionados.")
            self.lbl_mensaje.setStyleSheet("""
                background-color: #1e293b; color: #94a3b8;
                border: 1px dashed #334155; padding: 12px; border-radius: 6px;
            """)
            self.lbl_mensaje.show()
            return

        self.lbl_mensaje.setText(f"Mostrando {len(tickets)} tickets.")
        self.lbl_mensaje.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self.lbl_mensaje.show()

        self.tabla.setRowCount(len(tickets))
        for row_idx, item in enumerate(tickets):
            valores = [
                str(item.get("codigo_ticket", "")),
                str(item.get("asunto", "—")),
                str(item.get("solicitante", "—")),
                str(item.get("estado", "—")),
                str(item.get("prioridad", "—")),
                str(item.get("tecnico_asignado") or "Sin asignar"),
                str(item.get("fecha_creacion", "")[:10] if item.get("fecha_creacion") else "—"),
            ]
            for col_idx, val in enumerate(valores):
                cell = QTableWidgetItem(val)
                cell.setFlags(cell.flags() ^ Qt.ItemFlag.ItemIsEditable)
                if col_idx == 3:  # Estado
                    est = val.lower()
                    if "abierto" in est:
                        cell.setForeground(Qt.GlobalColor.cyan)
                    elif "atención" in est:
                        cell.setForeground(Qt.GlobalColor.yellow)
                    elif "resuelto" in est or "cerrado" in est:
                        cell.setForeground(Qt.GlobalColor.green)
                self.tabla.setItem(row_idx, col_idx, cell)

    def _on_error(self, exc: Exception, request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)
        self.lbl_mensaje.setText(f"Error al obtener tickets: {exc}")
        self.lbl_mensaje.setStyleSheet("""
            background-color: #450a0a; color: #fca5a5;
            border: 1px solid #7f1d1d; padding: 12px; border-radius: 6px;
        """)
        self.lbl_mensaje.show()
        self.btn_reintentar.show()
