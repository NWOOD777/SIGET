"""
Vista de Mesa de Ayuda / Tickets de Soporte en PySide6.
Permite consultar incidentes y solicitudes de soporte técnico (GET),
consultar el detalle de incidentes. El registro corresponde al portal Web.
La atención técnica avanzada (diagnósticos y órdenes de trabajo) permanece documentada
a la espera de los correspondientes endpoints en el backend.
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
from siget_desktop.ui.components import (
    configurar_tabla,
    crear_filtros,
    mostrar_mensaje,
    texto_relacion,
)
from siget_desktop.ui.dialogs.tickets_dialogs import (
    DetalleTicketDialog,
)
from siget_desktop.ui.workers import ApiWorker


class TicketsView(QWidget):
    """Módulo de Service Desk y Tickets de Soporte Técnico."""

    COLUMNAS = [
        "Código",
        "Asunto",
        "Solicitante",
        "Estado",
        "Prioridad",
        "Técnico",
        "Fecha",
    ]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._worker: ApiWorker | None = None
        self._tickets_cargados: list[dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Encabezado
        layout_encabezado = QHBoxLayout()
        vbox_titulo = QVBoxLayout()
        lbl_titulo = QLabel("Service Desk — Tickets")
        lbl_titulo.setObjectName("tituloPrincipal")
        vbox_titulo.addWidget(lbl_titulo)
        lbl_desc = QLabel("Gestión de incidentes, solicitudes de soporte y atención técnica")
        lbl_desc.setObjectName("subtitulo")
        lbl_desc.setWordWrap(True)
        vbox_titulo.addWidget(lbl_desc)
        layout_encabezado.addLayout(vbox_titulo)
        layout_encabezado.addStretch()

        self.btn_ver_detalle = QPushButton("Ver detalle")
        self.btn_ver_detalle.setObjectName("btnSecundario")
        self.btn_ver_detalle.setEnabled(False)
        self.btn_ver_detalle.clicked.connect(self._abrir_detalle_ticket)
        layout_encabezado.addWidget(self.btn_ver_detalle)

        self.btn_atender = QPushButton("Atender Ticket")
        self.btn_atender.setEnabled(False)
        self.btn_atender.setToolTip("Atención técnica pendiente de integración de órdenes de trabajo y diagnósticos en el backend")
        layout_encabezado.addWidget(self.btn_atender)

        layout.addLayout(layout_encabezado)

        # Filtros
        barra_filtros, layout_filtros = crear_filtros(self)
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Buscar por código, asunto o descripción...")
        self.input_search.returnPressed.connect(self.cargar_tickets)
        layout_filtros.addWidget(self.input_search, 2)

        self.combo_estado = QComboBox()
        self.combo_estado.addItem("Todos los estados", "")
        self.combo_estado.addItem("Abierto", "Abierto")
        self.combo_estado.addItem("En Proceso", "En Proceso")
        self.combo_estado.addItem("En Espera", "En Espera")
        self.combo_estado.addItem("Resuelto", "Resuelto")
        self.combo_estado.addItem("Cerrado", "Cerrado")
        self.combo_estado.currentIndexChanged.connect(self.cargar_tickets)
        layout_filtros.addWidget(self.combo_estado, 1)

        self.combo_prioridad = QComboBox()
        self.combo_prioridad.addItem("Todas las prioridades", "")
        self.combo_prioridad.addItem("Bajo", "Bajo")
        self.combo_prioridad.addItem("Medio", "Medio")
        self.combo_prioridad.addItem("Alto", "Alto")
        self.combo_prioridad.addItem("Crítico", "Crítico")
        self.combo_prioridad.currentIndexChanged.connect(self.cargar_tickets)
        layout_filtros.addWidget(self.combo_prioridad, 1)

        self.btn_actualizar = QPushButton("Actualizar")
        self.btn_actualizar.setObjectName("btnSecundario")
        self.btn_actualizar.clicked.connect(self.cargar_tickets)
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

        self.btn_reintentar = QPushButton("Reintentar conexión con el backend")
        self.btn_reintentar.setObjectName("btnSecundario")
        self.btn_reintentar.clicked.connect(self.cargar_tickets)
        self.btn_reintentar.hide()
        layout.addWidget(self.btn_reintentar)

        # Tabla de tickets
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(self.COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setAlternatingRowColors(True)
        configurar_tabla(self.tabla, (3, 4))
        self.tabla.itemSelectionChanged.connect(self._on_seleccion_cambiada)
        self.tabla.cellDoubleClicked.connect(lambda _r, _c: self._abrir_detalle_ticket())
        layout.addWidget(self.tabla, 1)

    def actualizar_permisos_ui(self):
        """Ajusta las acciones según los permisos efectivos del usuario."""
        self._on_seleccion_cambiada()

    def _on_seleccion_cambiada(self):
        hay_sel = self.tabla.currentRow() >= 0
        self.btn_ver_detalle.setEnabled(hay_sel)

    def _obtener_ticket_seleccionado(self) -> dict[str, Any] | None:
        fila = self.tabla.currentRow()
        if 0 <= fila < len(self._tickets_cargados):
            return self._tickets_cargados[fila]
        return None

    def _abrir_detalle_ticket(self):
        ticket = self._obtener_ticket_seleccionado()
        if not ticket:
            return
        id_ticket = int(ticket.get("id_ticket") or 0)
        dialogo = DetalleTicketDialog(id_ticket, self)
        dialogo.exec()

    def cargar_tickets(self):
        """Inicia la consulta de tickets al backend."""
        self.actualizar_permisos_ui()
        self.progreso.show()
        self.lbl_mensaje.hide()
        self.btn_reintentar.hide()
        self.btn_actualizar.setEnabled(False)
        self.btn_ver_detalle.setEnabled(False)

        search_text = self.input_search.text().strip() or None
        estado_sel = self.combo_estado.currentData() or None
        prio_sel = self.combo_prioridad.currentData() or None

        self._worker = ApiWorker(listar_tickets, search=search_text, estado=estado_sel, prioridad=prio_sel)
        self._worker.signals.finished.connect(lambda value, generation=current_session.generation, worker=self._worker: self._on_datos_cargados(value, generation) if worker is self._worker else None)
        self._worker.signals.error.connect(lambda value, generation=current_session.generation, worker=self._worker: self._on_error_carga(value, generation) if worker is self._worker else None)
        self._worker.start()

    def _on_datos_cargados(self, tickets: list[dict[str, Any]], request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)
        self._tickets_cargados = tickets

        if not tickets:
            mostrar_mensaje(self.lbl_mensaje, "No se encontraron tickets registrados con los filtros aplicados.", "empty")
            self._on_seleccion_cambiada()
            return

        mostrar_mensaje(self.lbl_mensaje, f"Mostrando {len(tickets)} tickets obtenidos del servidor.", "info")
        self.tabla.setRowCount(len(tickets))
        for row_idx, ticket in enumerate(tickets):
            valores = [
                str(ticket.get("codigo_ticket", "")),
                str(ticket.get("asunto", "")),
                texto_relacion(ticket.get("solicitante") or ticket.get("id_usuario_solicitante")),
                texto_relacion(ticket.get("estado") or ticket.get("id_estado_ticket")),
                texto_relacion(ticket.get("prioridad") or ticket.get("id_prioridad")),
                texto_relacion(ticket.get("tecnico_asignado") or ticket.get("id_tecnico_asignado"), "Sin asignar"),
                str(ticket.get("fecha_creacion", ""))[:10],
            ]
            for col, val in enumerate(valores):
                table_item = QTableWidgetItem(val)
                table_item.setToolTip(val)
                table_item.setFlags(table_item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.tabla.setItem(row_idx, col, table_item)

        self._on_seleccion_cambiada()

    def _on_error_carga(self, exc: Exception, request_generation: int | None = None):
        if not current_session.is_authenticated() or (request_generation is not None and request_generation != current_session.generation):
            return
        self.progreso.hide()
        self.btn_actualizar.setEnabled(True)
        self.tabla.setRowCount(0)
        self._tickets_cargados = []
        mostrar_mensaje(self.lbl_mensaje, f"Error al comunicar con el backend: {exc}", "error")
        self.btn_reintentar.show()
        self._on_seleccion_cambiada()
