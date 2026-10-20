"""
Consulta detallada de incidentes de soporte.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from siget_desktop.api.services import (
    obtener_ticket,
)
from siget_desktop.ui.components import mostrar_mensaje, texto_relacion
from siget_desktop.ui.dialogs.common import SessionDialog
from siget_desktop.ui.workers import ApiWorker


class DetalleTicketDialog(SessionDialog):
    """Consulta de detalle de un ticket de soporte técnico."""

    def __init__(self, id_ticket: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.id_ticket = id_ticket
        self.setWindowTitle(f"Detalle de ticket #{id_ticket}")
        self.resize(560, 520)
        self._worker: ApiWorker | None = None
        self._init_ui()
        self._cargar_datos()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        self.lbl_titulo = QLabel("Consultando ticket...")
        self.lbl_titulo.setObjectName("sectionTitle")
        layout.addWidget(self.lbl_titulo)

        self.card_info = QFrame()
        self.card_info.setObjectName("filterBar")
        layout_card = QFormLayout(self.card_info)
        layout_card.setSpacing(8)

        self.lbl_codigo = QLabel("—")
        layout_card.addRow("Código ticket:", self.lbl_codigo)

        self.lbl_asunto = QLabel("—")
        layout_card.addRow("Asunto:", self.lbl_asunto)

        self.lbl_solicitante = QLabel("—")
        layout_card.addRow("Solicitante:", self.lbl_solicitante)

        self.lbl_tecnico = QLabel("—")
        layout_card.addRow("Técnico asignado:", self.lbl_tecnico)

        self.lbl_activo = QLabel("—")
        layout_card.addRow("Activo relacionado:", self.lbl_activo)

        self.lbl_estado = QLabel("—")
        layout_card.addRow("Estado actual:", self.lbl_estado)

        self.lbl_prioridad = QLabel("—")
        layout_card.addRow("Prioridad SLA:", self.lbl_prioridad)

        self.lbl_fecha_creacion = QLabel("—")
        layout_card.addRow("Fecha reporte:", self.lbl_fecha_creacion)

        layout.addWidget(self.card_info)

        lbl_desc_title = QLabel("Descripción del problema reportado:")
        lbl_desc_title.setObjectName("sectionTitle")
        layout.addWidget(lbl_desc_title)

        self.lbl_descripcion = QLabel("—")
        self.lbl_descripcion.setWordWrap(True)
        layout.addWidget(self.lbl_descripcion)

        self.progreso = QProgressBar()
        self.progreso.setRange(0, 0)
        self.progreso.setFixedHeight(4)
        self.progreso.setTextVisible(False)
        layout.addWidget(self.progreso)

        self.lbl_mensaje = QLabel("")
        self.lbl_mensaje.hide()
        layout.addWidget(self.lbl_mensaje)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("btnSecundario")
        btn_cerrar.clicked.connect(self.accept)
        btn_layout.addWidget(btn_cerrar)

        layout.addLayout(btn_layout)

    def _cargar_datos(self):
        self.progreso.show()
        self._worker = ApiWorker(obtener_ticket, id_ticket=self.id_ticket)
        self.conectar_worker(self._worker, self._on_datos, self._on_error)
        self._worker.start()

    def _on_datos(self, ticket: dict[str, Any]):
        self.progreso.hide()
        codigo = ticket.get("codigo_ticket", f"TCK-{self.id_ticket}")
        self.lbl_titulo.setText(f"{codigo} — {ticket.get('asunto', '')}")
        self.lbl_codigo.setText(codigo)
        self.lbl_asunto.setText(ticket.get("asunto", "—"))
        self.lbl_solicitante.setText(texto_relacion(ticket.get("solicitante") or ticket.get("id_usuario_solicitante")))
        self.lbl_tecnico.setText(texto_relacion(ticket.get("tecnico_asignado") or ticket.get("id_tecnico_asignado"), "Sin técnico asignado"))

        activo = ticket.get("activo") or ticket.get("id_activo")
        if activo:
            cod = activo.get("codigo_inventario") if isinstance(activo, dict) else f"Activo #{activo}"
            modelo = activo.get("modelo", "") if isinstance(activo, dict) else ""
            self.lbl_activo.setText(f"{cod} {modelo}".strip())
        else:
            self.lbl_activo.setText("Sin activo asociado")

        self.lbl_estado.setText(texto_relacion(ticket.get("estado") or ticket.get("id_estado_ticket")))
        self.lbl_prioridad.setText(texto_relacion(ticket.get("prioridad") or ticket.get("id_prioridad")))
        self.lbl_fecha_creacion.setText(str(ticket.get("fecha_creacion", "—"))[:19])
        self.lbl_descripcion.setText(ticket.get("descripcion", "Sin descripción registrada."))

    def _on_error(self, exc: Exception):
        self.progreso.hide()
        mostrar_mensaje(self.lbl_mensaje, f"Error al cargar ticket: {exc}", "error")
